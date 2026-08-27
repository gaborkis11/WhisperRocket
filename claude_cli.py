#!/usr/bin/env python3
"""
WhisperRocket - Claude Code CLI wrapper

The AI enhancement feature runs through the user's own, unmodified Claude Code
CLI. This module is the only place that talks to that binary.

It deliberately handles NO credentials. Anthropic's policy is explicit:

    "Developers may not collect, store, or intermediate Claude.ai credentials
    or session tokens - sign-in to a Claude account must complete through
    Anthropic's own flow."

    "Nor does it prevent an end user from signing in to the unmodified Claude
    Code binary with their own Claude subscription."

So sign-in is delegated to `claude auth login`, which runs Anthropic's own
browser flow and stores the credential in Claude Code's own store. WhisperRocket
never sees a token, never writes one, and has no field to paste one into.

Installation goes through Anthropic's published installer for the same reason:
the binary must be exactly what Anthropic ships.
"""
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Official installer, from https://code.claude.com/docs/en/setup
INSTALL_URL = "https://claude.ai/install.sh"
INSTALL_COMMAND = f"curl -fsSL {INSTALL_URL} | bash"

# The tray app is often started from an autostart .desktop entry, which gets a
# minimal PATH that usually excludes ~/.local/bin - where the native installer
# puts the launcher. Looking only at shutil.which() would report "not installed"
# on a machine that has it, so the explicit list is not optional.
_CANDIDATE_PATHS = (
    "~/.local/bin/claude",
    "/usr/local/bin/claude",
    "/usr/bin/claude",
    "/opt/homebrew/bin/claude",
    "~/.claude/local/claude",
)

# Models offered in Settings. Sonnet is the default: it is enough for cleaning
# up a transcript, and it is what this feature was measured against.
AVAILABLE_MODELS: Tuple[Tuple[str, str], ...] = (
    ("sonnet", "Sonnet"),
    ("opus", "Opus"),
    ("haiku", "Haiku"),
)
DEFAULT_MODEL = "sonnet"

_status_cache: Optional[Tuple[float, "AuthStatus"]] = None
_STATUS_TTL = 3.0


@dataclass
class AuthStatus:
    """What `claude auth status --json` reports, plus whether the CLI exists"""
    installed: bool = False
    logged_in: bool = False
    method: str = ""          # "claude.ai" / "console" / ...
    email: str = ""
    plan: str = ""            # "max" / "pro" / "team" / ...
    provider: str = ""        # "firstParty" / "bedrock" / ...
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.installed and self.logged_in


def find_binary() -> Optional[str]:
    """Absolute path to the claude CLI, or None if it is not installed"""
    found = shutil.which("claude")
    if found:
        return found

    for candidate in _CANDIDATE_PATHS:
        path = Path(candidate).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def is_installed() -> bool:
    return find_binary() is not None


def subprocess_env() -> dict:
    """
    Environment for spawned claude processes.

    Adds ~/.local/bin to PATH for the same autostart reason as above, so the CLI
    can find its own helpers even when the app inherited a minimal PATH.
    """
    env = os.environ.copy()
    local_bin = str(Path("~/.local/bin").expanduser())
    if local_bin not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
    return env


def version() -> Optional[str]:
    """Installed CLI version string, or None"""
    binary = find_binary()
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, timeout=15,
            stdin=subprocess.DEVNULL, env=subprocess_env(),
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _parse_json_blob(text: str) -> Optional[dict]:
    """Pull the JSON object out of CLI output that may have extra lines around it"""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def auth_status(use_cache: bool = True) -> AuthStatus:
    """
    Current authentication state, read from Anthropic's own CLI.

    Never touches ~/.claude/.credentials.json or the keychain - the CLI reports
    its own state, and no credential material passes through here.
    """
    global _status_cache
    if use_cache and _status_cache and (time.time() - _status_cache[0]) < _STATUS_TTL:
        return _status_cache[1]

    binary = find_binary()
    if not binary:
        status = AuthStatus(installed=False)
        _status_cache = (time.time(), status)
        return status

    try:
        result = subprocess.run(
            [binary, "auth", "status", "--json"],
            capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL, env=subprocess_env(),
        )
        data = _parse_json_blob(result.stdout)
        if data is None:
            status = AuthStatus(
                installed=True,
                error=(result.stderr or result.stdout or "no JSON in output").strip()[:200],
            )
        else:
            status = AuthStatus(
                installed=True,
                logged_in=bool(data.get("loggedIn")),
                method=str(data.get("authMethod") or ""),
                email=str(data.get("email") or ""),
                plan=str(data.get("subscriptionType") or ""),
                provider=str(data.get("apiProvider") or ""),
            )
    except subprocess.TimeoutExpired:
        status = AuthStatus(installed=True, error="timeout")
    except Exception as e:
        status = AuthStatus(installed=True, error=str(e)[:200])

    _status_cache = (time.time(), status)
    return status


def invalidate_status_cache():
    """Call after a login or install so the next read is fresh"""
    global _status_cache
    _status_cache = None


def start_login(console: bool = False) -> Optional[subprocess.Popen]:
    """
    Start Anthropic's own browser sign-in flow.

    Returns the running process so the caller can wait on it, or None if the CLI
    is not installed. The caller should poll auth_status(use_cache=False) until
    it reports logged_in - the flow completes in the browser, not here.
    """
    binary = find_binary()
    if not binary:
        return None

    args = [binary, "auth", "login", "--console" if console else "--claudeai"]
    try:
        return subprocess.Popen(
            args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True,
            env=subprocess_env(),
        )
    except Exception:
        return None


def logout() -> bool:
    """Sign out through the CLI's own command"""
    binary = find_binary()
    if not binary:
        return False
    try:
        subprocess.run(
            [binary, "auth", "logout"],
            capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL, env=subprocess_env(),
        )
        invalidate_status_cache()
        return True
    except Exception:
        return False


def install_prerequisites_missing() -> List[str]:
    """Which tools the official installer needs but this machine lacks"""
    return [tool for tool in ("curl", "bash") if not shutil.which(tool)]


def install(on_output: Optional[Callable[[str], None]] = None,
            timeout: int = 600) -> Tuple[bool, str]:
    """
    Run Anthropic's published installer.

    This installs the unmodified binary exactly as a user would by hand; the
    caller MUST confirm with the user first, showing INSTALL_COMMAND, because
    this downloads and executes a script from the network.

    Args:
        on_output: called with each output line, for a live log in the UI
        timeout: seconds before the installer is killed

    Returns:
        (success, message)
    """
    missing = install_prerequisites_missing()
    if missing:
        return False, "missing: " + ", ".join(missing)

    def emit(line: str):
        if on_output:
            on_output(line)

    emit(f"$ {INSTALL_COMMAND}")
    try:
        process = subprocess.Popen(
            ["bash", "-c", INSTALL_COMMAND],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, bufsize=1,
            env=subprocess_env(),
        )
    except Exception as e:
        return False, str(e)

    deadline = time.time() + timeout
    try:
        for line in process.stdout:
            emit(line.rstrip("\n"))
            if time.time() > deadline:
                process.kill()
                return False, "timeout"
        process.wait(timeout=max(1, int(deadline - time.time())))
    except subprocess.TimeoutExpired:
        process.kill()
        return False, "timeout"
    except Exception as e:
        return False, str(e)

    invalidate_status_cache()

    if process.returncode != 0:
        return False, f"installer exited with {process.returncode}"

    binary = find_binary()
    if not binary:
        return False, "installer finished but the claude binary was not found"

    emit(f"OK: {binary}")
    return True, binary


def available_models() -> Tuple[Tuple[str, str], ...]:
    return AVAILABLE_MODELS


if __name__ == "__main__":
    status = auth_status(use_cache=False)
    print(f"binary:    {find_binary() or '(not installed)'}")
    print(f"version:   {version() or '-'}")
    print(f"installed: {status.installed}")
    print(f"logged in: {status.logged_in}")
    if status.logged_in:
        print(f"account:   {status.email} ({status.plan}, {status.method}, {status.provider})")
    if status.error:
        print(f"error:     {status.error}")
