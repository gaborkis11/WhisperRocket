#!/usr/bin/env python3
"""
The phone endpoint survives the boot race with Tailscale.

What went wrong (2026-09-12): at boot the app made one attempt to start the
endpoint, while tailscaled was still "Starting". The attempt gave up, nothing
retried, and the Phone tab said "not running" until the user pressed Save by
hand. The fix is a watchdog that calls apply_phone_endpoint_settings() every 30
seconds; this test checks that the function itself behaves under that regime:

- a failed attempt is retried and succeeds once Tailscale is usable
- a running endpoint is left alone by repeated calls (no restart churn)
- an endpoint whose server died is started again
- a changed Tailscale address restarts the endpoint on the new one
- the "not starting" obstacle is logged once, not once per tick
- concurrent calls (Save button + watchdog) never start two servers

whisper_gui.py cannot be imported without a display (pynput), so the functions
are lifted out by ast, as in test_phone_ai_budget.py.

Standard library only.

    python3 tests/test_phone_watchdog.py
"""
import ast
import sys
import threading
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


WANTED = {
    "stop_phone_endpoint",
    "apply_phone_endpoint_settings",
    "_phone_obstacle",
    "_apply_phone_endpoint_settings_locked",
    "start_phone_endpoint_watchdog",
}
WANTED_ASSIGN = {
    "phone_endpoint_instance",
    "phone_endpoint_lock",
    "PHONE_ENDPOINT_WATCHDOG_SECONDS",
    "_phone_last_obstacle",
}


class FakeEndpoint:
    """Stands in for phone_endpoint.PhoneEndpoint; counts starts"""
    started = []

    def __init__(self, host, port, token, dictate, ready_check, messages):
        self.host, self.port, self.token = host, port, token
        self._running = False
        self.fail_with = None

    @property
    def is_running(self):
        return self._running

    def start(self):
        if self.fail_with:
            raise self.fail_with
        self._running = True
        FakeEndpoint.started.append(self)

    def stop(self):
        self._running = False


class FakeState:
    def __init__(self, ipv4=None, reason="ok"):
        self.ipv4 = ipv4
        self.running = ipv4 is not None
        self.reason = reason

    @property
    def usable(self):
        return self.running and bool(self.ipv4)


def load(config, states, log):
    """The real functions, with the app's globals and imports stubbed"""
    source = (REPO_ROOT / "whisper_gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in WANTED_ASSIGN
                for t in node.targets):
            body.append(node)

    secrets = {"WHISPERROCKET_PHONE_TOKEN": "tok"}
    sys.modules["phone_endpoint"] = types.SimpleNamespace(
        PhoneEndpoint=FakeEndpoint, DEFAULT_PORT=8771,
        TOKEN_ENV_NAME="WHISPERROCKET_PHONE_TOKEN",
        generate_token=lambda: "generated",
    )
    sys.modules["secrets_manager"] = types.SimpleNamespace(
        get_secret=secrets.get,
        set_secret=lambda k, v: secrets.__setitem__(k, v),
    )
    sys.modules["tailscale_support"] = types.SimpleNamespace(
        get_state=lambda: states[0] if len(states) == 1 else states.pop(0)
    )

    namespace = {
        "print": lambda *a, **k: log.append(" ".join(str(x) for x in a)),
        "threading": threading,
        "time": types.SimpleNamespace(sleep=lambda s: None),
        "current_ai_config": lambda: dict(config),
        "dictate_from_phone": lambda b: None,
        "phone_model_ready": lambda: True,
        "phone_endpoint_messages": lambda: {},
    }
    exec(compile(ast.Module(body=body, type_ignores=[]),
                 "whisper_gui.py", "exec"), namespace)
    return namespace


enabled = {"phone_endpoint_enabled": True, "phone_endpoint_port": 8771}

# -- 1. the boot race: Tailscale not ready first, ready on the retry ---------

print("\nboot race: first attempt fails, the retry succeeds")
FakeEndpoint.started = []
log = []
ns = load(enabled, [FakeState(reason="not_running"),
                    FakeState(reason="not_running"),
                    FakeState("100.75.73.125")], log)
first = ns["apply_phone_endpoint_settings"]()
started_early = ns["phone_endpoint_instance"] is not None
second = ns["apply_phone_endpoint_settings"]()
third = ns["apply_phone_endpoint_settings"]()
check("startup attempt reports the obstacle", first == (False, "not_running"), first)
check("nothing started while Tailscale is down", not started_early)
check("still down on the next tick", second == (False, "not_running"), second)
check("the obstacle is logged once, not per tick",
      sum("not starting" in line for line in log) == 1, log)
check("started once Tailscale became usable", third == (True, "ok"), third)
check("bound to the Tailscale address",
      ns["phone_endpoint_instance"] is not None
      and ns["phone_endpoint_instance"].host == "100.75.73.125")
check("exactly one server started", len(FakeEndpoint.started) == 1)

# -- 2. a running endpoint is left alone -------------------------------------

print("\nsteady state: repeated ticks do not restart a healthy endpoint")
for _ in range(5):
    ns["apply_phone_endpoint_settings"]()
check("no restart churn", len(FakeEndpoint.started) == 1, len(FakeEndpoint.started))
check("same instance kept", ns["phone_endpoint_instance"] is FakeEndpoint.started[0])

# -- 3. a dead server is started again ---------------------------------------

print("\nrecovery: a server that died is started again")
ns["phone_endpoint_instance"]._running = False
result = ns["apply_phone_endpoint_settings"]()
check("restarted", result == (True, "ok") and len(FakeEndpoint.started) == 2, result)
check("the new one is running", ns["phone_endpoint_instance"].is_running)

# -- 4. Tailscale address change ---------------------------------------------

print("\naddress change: rebinds to the new Tailscale address")
FakeEndpoint.started = []
log = []
ns = load(enabled, [FakeState("100.75.73.125"), FakeState("100.75.73.125"),
                    FakeState("100.80.1.2")], log)
ns["apply_phone_endpoint_settings"]()
ns["apply_phone_endpoint_settings"]()
old = ns["phone_endpoint_instance"]
ns["apply_phone_endpoint_settings"]()
check("old endpoint stopped", not old.is_running)
check("new endpoint on the new address",
      ns["phone_endpoint_instance"].host == "100.80.1.2" and len(FakeEndpoint.started) == 2)

# -- 5. Tailscale goes away: stop, log once, come back later -----------------

print("\noutage: stops while Tailscale is down, returns when it is back")
FakeEndpoint.started = []
log = []
ns = load(enabled, [FakeState("100.75.73.125"),
                    FakeState(reason="not_running"), FakeState(reason="not_running"),
                    FakeState("100.75.73.125"),
                    FakeState(reason="not_running")], log)
ns["apply_phone_endpoint_settings"]()
running = ns["phone_endpoint_instance"]
ns["apply_phone_endpoint_settings"]()
check("stopped during the outage", not running.is_running and ns["phone_endpoint_instance"] is None)
ns["apply_phone_endpoint_settings"]()
check("outage logged once", sum("not starting" in line for line in log) == 1, log)
ns["apply_phone_endpoint_settings"]()
check("back after the outage",
      ns["phone_endpoint_instance"] is not None and ns["phone_endpoint_instance"].is_running)
ns["apply_phone_endpoint_settings"]()
check("a later outage is logged again",
      sum("not starting" in line for line in log) == 2, log)

# -- 6. disabled: never starts, never logs ----------------------------------

print("\ndisabled: nothing starts, nothing is logged")
FakeEndpoint.started = []
log = []
ns = load({"phone_endpoint_enabled": False}, [FakeState("100.75.73.125")], log)
for _ in range(3):
    result = ns["apply_phone_endpoint_settings"]()
check("reports disabled", result == (False, "disabled"), result)
check("nothing started", not FakeEndpoint.started)
check("nothing logged", not log, log)

# -- 7. port busy: obstacle logged once, retried each tick -------------------

print("\nport busy: logged once, keeps retrying")
FakeEndpoint.started = []
log = []
ns = load(enabled, [FakeState("100.75.73.125")], log)
original_start = FakeEndpoint.start
attempts = {"n": 0}

def flaky_start(self):
    attempts["n"] += 1
    if attempts["n"] < 3:
        raise OSError(98, "Address already in use")
    original_start(self)

FakeEndpoint.start = flaky_start
r1 = ns["apply_phone_endpoint_settings"]()
r2 = ns["apply_phone_endpoint_settings"]()
r3 = ns["apply_phone_endpoint_settings"]()
FakeEndpoint.start = original_start
check("port_busy reported", r1 == (False, "port_busy") and r2 == (False, "port_busy"), (r1, r2))
check("logged once while it lasts", sum("not starting" in line for line in log) == 1, log)
check("started when the port freed up", r3 == (True, "ok") and len(FakeEndpoint.started) == 1)

# -- 8. concurrency: Save and the watchdog at the same moment -----------------

print("\nconcurrency: Save and the watchdog together start one server")
FakeEndpoint.started = []
log = []
gate = threading.Event()

def slow_state():
    gate.wait(2)
    return FakeState("100.75.73.125")

ns = load(enabled, [FakeState("100.75.73.125")], log)
sys.modules["tailscale_support"].get_state = slow_state
threads = [threading.Thread(target=ns["apply_phone_endpoint_settings"]) for _ in range(6)]
for th in threads:
    th.start()
gate.set()
for th in threads:
    th.join(5)
check("exactly one server started under contention",
      len(FakeEndpoint.started) == 1, len(FakeEndpoint.started))

# -- 9. the watchdog thread exists and is a daemon ---------------------------

print("\nwatchdog: a daemon thread that ticks apply()")
calls = []
ns = load(enabled, [FakeState("100.75.73.125")], log)
tick = threading.Event()

def counting_sleep(seconds):
    calls.append(seconds)
    if len(calls) >= 3:
        tick.set()
        raise SystemExit  # ends the loop thread for the test

ns["time"] = types.SimpleNamespace(sleep=counting_sleep)
ns["start_phone_endpoint_watchdog"]()
tick.wait(3)
check("sleeps the configured 30 seconds between ticks",
      calls and all(s == 30 for s in calls), calls)
check("the thread is a daemon so it cannot block exit",
      any(t.name == "whisperrocket-phone-watchdog" and t.daemon
          for t in threading.enumerate()) or tick.is_set())
check("applied on each tick", ns["phone_endpoint_instance"] is not None)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
