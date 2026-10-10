#!/usr/bin/env python3
"""
The Whisper model leaves the GPU ten seconds after its last use and comes back on the
next use - without ever being pulled out from under a running transcription.

Stdlib only: a fake loader and a fake clock stand in for faster-whisper.

    python3 tests/test_warm_model.py
"""
import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warm_model  # noqa: E402

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


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Loader:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def __call__(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("model file missing")
        return f"model#{self.calls}"


IDLE = warm_model.IDLE_RELEASE_SECONDS

# --- 1. the defaults the user asked for -------------------------------------
check("released ten seconds after the last use", IDLE == 10, str(IDLE))
check("checked often enough to land close to it",
      warm_model.IDLE_CHECK_SECONDS <= IDLE / 2, str(warm_model.IDLE_CHECK_SECONDS))

# --- 2. lazy load, one load for many uses ------------------------------------
clock, loader = Clock(), Loader()
wm = warm_model.WarmModel(loader, clock=clock)
check("nothing is loaded before the first use", not wm.is_loaded and loader.calls == 0)
check("not usable before a load succeeded", not wm.usable)

events = []
with wm.use(events.append) as model:
    check("use() hands over the loaded model", model == "model#1", str(model))
check("on_loading brackets the load", events == [True, False], str(events))
check("usable once loaded", wm.usable and wm.is_loaded)

events.clear()
with wm.use(events.append) as model:
    pass
check("a warm model is not loaded again", loader.calls == 1 and model == "model#1")
check("no loading signal without a load", events == [], str(events))

# --- 3. the idle release -----------------------------------------------------
clock.now += IDLE - 1
check("kept just before the idle time", not wm.release_if_idle() and wm.is_loaded)
clock.now += 1
check("released at the idle time", wm.release_if_idle() and not wm.is_loaded)
check("still usable after the release (one load away)", wm.usable)
check("a second release is a no-op", not wm.release_if_idle())

events.clear()
with wm.use(events.append) as model:
    pass
check("the next use loads it back", model == "model#2" and loader.calls == 2, str(model))
check("and says so", events == [True, False], str(events))

# A use resets the idle clock: the time is counted from the END of the use
clock.now += IDLE - 10
with wm.use():
    clock.now += 20  # a long transcription
check("idle time counts from the end of the last use", not wm.release_if_idle())

# --- 4. never released from under a running transcription --------------------
clock.now += IDLE * 2
inside = threading.Event()
leave = threading.Event()


def long_transcription():
    with wm.use():
        inside.set()
        leave.wait(5)


worker = threading.Thread(target=long_transcription)
worker.start()
inside.wait(5)
check("no release while a use holds the model", not wm.release_if_idle() and wm.is_loaded)
leave.set()
worker.join(5)
check("and the use just ended counts as activity", not wm.release_if_idle())

# --- 5. a load and a use never overlap ---------------------------------------
slow_loads = []


def slow_loader():
    slow_loads.append(True)
    time.sleep(0.2)
    return "slow-model"


wm2 = warm_model.WarmModel(slow_loader, clock=Clock())
results = []


def user():
    with wm2.use() as m:
        results.append(m)


pair = [threading.Thread(target=user) for _ in range(2)]
for t in pair:
    t.start()
for t in pair:
    t.join(5)
check("two callers racing for an unloaded model share one load",
      results == ["slow-model", "slow-model"] and len(slow_loads) == 1,
      f"{results} loads={len(slow_loads)}")

# --- 6. a failed load --------------------------------------------------------
clock3, loader3 = Clock(), Loader()
loader3.fail = True
wm3 = warm_model.WarmModel(loader3, clock=clock3)
events = []
try:
    with wm3.use(events.append):
        pass
    raised = False
except RuntimeError:
    raised = True
check("a failed load raises to the caller", raised)
check("the loading signal is closed even on failure", events == [True, False], str(events))
check("not usable after a failed first load", not wm3.usable and not wm3.is_loaded)
loader3.fail = False
with wm3.use() as model:
    pass
check("the next use tries again", model == "model#2" and wm3.usable, str(model))

# --- 7. GPU cache: torch only when it is already there -----------------------
sys.modules.pop("torch", None)
warm_model.free_gpu_cache()
check("torch is never imported just to empty its cache", "torch" not in sys.modules)

emptied = []
sys.modules["torch"] = types.SimpleNamespace(cuda=types.SimpleNamespace(
    is_available=lambda: True, empty_cache=lambda: emptied.append(True)))
warm_model.free_gpu_cache()
check("torch's cache is emptied when diarization loaded it", emptied == [True])
sys.modules["torch"] = types.SimpleNamespace(cuda=types.SimpleNamespace(
    is_available=lambda: True, empty_cache=lambda: 1 / 0))
warm_model.free_gpu_cache()
check("a torch error does not break the release", True)
del sys.modules["torch"]

# --- 8. the background watch -------------------------------------------------
clock4 = Clock()
wm4 = warm_model.WarmModel(Loader(), clock=clock4)
wm4.preload()
check("preload loads without a transcription", wm4.is_loaded)
clock4.now += IDLE
wm4.start_idle_watch(check_seconds=0.01)
deadline = time.time() + 2
while wm4.is_loaded and time.time() < deadline:
    time.sleep(0.01)
wm4.stop_idle_watch()
check("the watch thread releases the idle model on its own", not wm4.is_loaded)

# --- 9. kept warm while a recording runs -------------------------------------
clock6 = Clock()
state = {"recording": True}
wm6 = warm_model.WarmModel(Loader(), clock=clock6, keep_warm=lambda: state["recording"])
wm6.preload()  # what prewarm_model() does when a recording starts
clock6.now += IDLE * 6  # a one-minute dictation
check("not released while the recording runs", not wm6.release_if_idle() and wm6.is_loaded)
state["recording"] = False
clock6.now += 1
check("not released in the gap between the stop and the transcription",
      not wm6.release_if_idle() and wm6.is_loaded)
clock6.now += IDLE
check("released once idle after the recording", wm6.release_if_idle())

# --- 10. the wiring in whisper_gui.py -----------------------------------------
#
# whisper_gui cannot be imported here (pynput needs a display), so the real
# functions are lifted out of its source, as tests/test_phone_watchdog.py does.
import ast  # noqa: E402

source = (Path(__file__).resolve().parent.parent / "whisper_gui.py").read_text(encoding="utf-8")
wanted = {"phone_model_ready", "run_whisper", "prewarm_model"}
nodes = [n for n in ast.parse(source).body
         if isinstance(n, ast.FunctionDef) and n.name in wanted]
check("whisper_gui still defines the wired functions", len(nodes) == len(wanted))


class FakeWhisper:
    def transcribe(self, path, **kwargs):
        return iter([types.SimpleNamespace(text=" szia ")]), None


clock5 = Clock()
wm5 = warm_model.WarmModel(FakeWhisper, clock=clock5)
namespace = {
    "whisper_model": wm5,
    "whisper_backend": "faster-whisper",
    "config": {"language": "hu"},
    "current_hotwords": lambda: None,
    "dictionary_manager": types.SimpleNamespace(hotwords_options=lambda h: {}),
    "transcript_filter": types.SimpleNamespace(filter_transcript=lambda text: text),
    "print": lambda *a, **k: None,
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "whisper_gui.py", "exec"), namespace)

check("phone: not ready before the first load", not namespace["phone_model_ready"]())
events = []
text = namespace["run_whisper"]("x.wav", on_loading=events.append)
check("run_whisper loads the model through use()", text == "szia" and wm5.is_loaded, repr(text))
check("run_whisper passes on_loading to the load", events == [True, False], str(events))
clock5.now += IDLE
wm5.release_if_idle()
check("phone: still ready after an idle release", namespace["phone_model_ready"]() and not wm5.is_loaded)
events.clear()
check("run_whisper brings the released model back",
      namespace["run_whisper"]("x.wav", on_loading=events.append) == "szia" and events == [True, False])

# prewarm_model: loads silently, and a failure never reaches the recording
wm7 = warm_model.WarmModel(FakeWhisper, clock=Clock())
namespace["whisper_model"] = wm7
namespace["prewarm_model"]()
check("prewarm loads the model when a recording starts", wm7.is_loaded)
broken = Loader()
broken.fail = True
namespace["whisper_model"] = warm_model.WarmModel(broken, clock=Clock())
try:
    namespace["prewarm_model"]()
    swallowed = True
except Exception:
    swallowed = False
check("a failed prewarm does not break the recording", swallowed)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
