#!/usr/bin/env python3
"""
The phone path's AI budget, and the failure reason kept in the history.

Two things are checked, both of which used to be untestable:

1. How long the AI cleanup may run. On the phone it gets what is left of the
   response frame after the transcription, floored so a slow Whisper cannot
   leave it three useless seconds, and NOT scaled by text length or capped by
   the desktop's ai_timeout_max_seconds - the phone stops listening at the
   frame, so time beyond it buys nothing and still costs Claude budget.

2. That a dictation which came back raw records WHY, and that a history file
   holding old-format entries stays readable next to the new ones.

whisper_gui.py cannot be imported here: it pulls in pynput, which needs an X
connection at import time, so anywhere without a display (CI, ssh, this test)
the import dies before the first assert. The function under test is therefore
lifted out of the file by ast and run against stubs - the real source, not a
copy of it, which is the point: a copy would keep passing after the file
changed.

Standard library only.

    python3 tests/test_phone_ai_budget.py

Exit code 0 when every check passes.
"""
import ast
import json
import sys
import tempfile
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import history_manager
from phone_endpoint import DictationOutcome, header_safe, phone_ai_timeout

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


# -- the real apply_ai_enhancement, lifted out of whisper_gui.py -------------

def load_apply_ai_enhancement():
    """whisper_gui.apply_ai_enhancement with its module imports stubbed out"""
    source = (REPO_ROOT / "whisper_gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "apply_ai_enhancement")

    namespace = {"print": lambda *a, **k: None}
    exec(compile(ast.Module(body=[wanted], type_ignores=[]),
                 "whisper_gui.py", "exec"), namespace)
    return namespace


class FakeResult:
    """Stands in for ai_enhancer.EnhanceResult"""

    def __init__(self, text, enhanced=True, reason=""):
        self.text = text
        self.raw_text = text
        self.enhanced = enhanced
        self.reason = reason
        self.mode = "transcript"
        self.elapsed = 0.1
        self.dictionary_hits = 0

    @property
    def failed(self):
        return not self.enhanced and self.reason not in ("", "disabled", "empty_input")


def timeout_handed_to_enhance(config, text, **kwargs):
    """Run the real function and report the timeout it asked enhance() for"""
    seen = {}

    def fake_enhance(raw_text, cfg):
        seen["timeout"] = cfg.get("ai_timeout_seconds")
        return FakeResult(raw_text)

    sys.modules["ai_enhancer"] = types.SimpleNamespace(enhance=fake_enhance)
    namespace = load_apply_ai_enhancement()
    namespace["current_ai_config"] = lambda: dict(config)
    namespace["apply_ai_enhancement"](text, **kwargs)
    return seen.get("timeout")


# -- 1. the arithmetic ------------------------------------------------------

print("\nphone_ai_timeout() - what is left of the frame")

check("fast transcription leaves nearly the whole frame",
      phone_ai_timeout(50, 3.2, 12) == 46, phone_ai_timeout(50, 3.2, 12))
check("a typical phone dictation",
      phone_ai_timeout(50, 8.0, 12) == 42, phone_ai_timeout(50, 8.0, 12))
check("exactly at the floor",
      phone_ai_timeout(50, 38.0, 12) == 12, phone_ai_timeout(50, 38.0, 12))
check("slow transcription is floored, not left with 6 seconds",
      phone_ai_timeout(50, 44.0, 12) == 12, phone_ai_timeout(50, 44.0, 12))
check("transcription longer than the whole frame still gets the floor",
      phone_ai_timeout(50, 120.0, 12) == 12, phone_ai_timeout(50, 120.0, 12))
check("a zero-second transcription gets the frame",
      phone_ai_timeout(50, 0, 12) == 50, phone_ai_timeout(50, 0, 12))
check("the frame comes from the setting, not a constant",
      phone_ai_timeout(30, 5.0, 12) == 25 and phone_ai_timeout(70, 5.0, 12) == 65)
check("never more than the frame, at any transcription time",
      all(phone_ai_timeout(50, w / 2, 12) <= 50 for w in range(0, 200)))
check("never below the floor, at any transcription time",
      all(phone_ai_timeout(50, w / 2, 12) >= 12 for w in range(0, 400)))
check("a broken elapsed value falls back to the whole frame",
      phone_ai_timeout(50, None, 12) == 50)

# -- 2. the two paths through apply_ai_enhancement --------------------------

print("\napply_ai_enhancement() - phone gets a wall, the desktop keeps scaling")

phone_config = {
    "ai_enhance_enabled": True,
    "ai_dictionary_enabled": True,
    "ai_timeout_seconds": 120,
    "ai_timeout_max_seconds": 180,
}
short_text = "Rovid mondat."
long_text = "szo " * 500          # 2000 characters

phone_timeout = phone_ai_timeout(50, 3.2, 12)
given = timeout_handed_to_enhance(phone_config, long_text,
                                  timeout_override=phone_timeout,
                                  scale_timeout=False)
check("phone: a 2000 character transcript does not extend the frame",
      given == 46, f"got {given}, expected 46")

given = timeout_handed_to_enhance(phone_config, short_text,
                                  timeout_override=phone_timeout,
                                  scale_timeout=False)
check("phone: a short transcript gets the same remaining frame",
      given == 46, f"got {given}, expected 46")

given = timeout_handed_to_enhance(phone_config, long_text,
                                  timeout_override=phone_ai_timeout(50, 44.0, 12),
                                  scale_timeout=False)
check("phone: after a slow transcription the floor is what is passed on",
      given == 12, f"got {given}, expected 12")

given = timeout_handed_to_enhance(phone_config, "x" * 20000,
                                  timeout_override=phone_timeout,
                                  scale_timeout=False)
check("phone: the 180s desktop cap never enters the picture",
      given == 46, f"got {given}, expected 46")

given = timeout_handed_to_enhance(phone_config, short_text)
check("desktop: unchanged, short text keeps the configured base",
      given == 120, f"got {given}, expected 120")

given = timeout_handed_to_enhance(phone_config, "x" * 1000)
check("desktop: unchanged, one extra second per 50 characters",
      given == 140, f"got {given}, expected 140")

given = timeout_handed_to_enhance(phone_config, "x" * 20000)
check("desktop: unchanged, still capped at ai_timeout_max_seconds",
      given == 180, f"got {given}, expected 180")

# -- 3. the response to the phone -------------------------------------------

print("\nDictationOutcome and the response header")

check("the outcome carries a reason and defaults to none",
      DictationOutcome().ai_reason == ""
      and DictationOutcome(text="x", ai_reason="timeout").ai_reason == "timeout")
check("the existing fields are untouched",
      list(DictationOutcome.__dataclass_fields__)[:4]
      == ["text", "mode", "enhanced", "error"])
check("an accented reason cannot break the response",
      header_safe("guard: elutasitott valtoztatas - szo").isascii())
check("a header value carrying newlines is collapsed",
      "\n" not in header_safe("timeout\nX-Injected: 1")
      and "\r" not in header_safe("timeout\r\nX-Injected: 1"))
check("a runaway reason is cut short",
      len(header_safe("internal_error(" + "x" * 5000 + ")")) == 200)

# -- 3b. the same, over a real HTTP response --------------------------------

print("\nthe running endpoint - the header reaches the caller")

import threading
import urllib.request

from phone_endpoint import PhoneEndpoint, generate_token

TOKEN = generate_token()
PORT = 8801          # not 8771: the user's endpoint may be running


def dictate_raw(_audio):
    return DictationOutcome(text="nyers atirat", mode="transcript",
                            enhanced=False, ai_reason="usage_limit")


def dictate_clean(_audio):
    return DictationOutcome(text="tiszta szoveg", mode="transcript",
                            enhanced=True)


def ask(dictate):
    endpoint = PhoneEndpoint("127.0.0.1", PORT, TOKEN, dictate,
                             ready_check=lambda: True)
    endpoint.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/dictate", method="POST", data=b"audio")
        request.add_header("Authorization", f"Bearer {TOKEN}")
        request.add_header("Content-Type", "audio/m4a")
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8"), dict(response.headers)
    finally:
        endpoint.stop()


body, headers = ask(dictate_raw)
check("the body is still the plain transcript",
      body == "nyers atirat", body)
check("Mode and Enhanced still say what they said",
      headers.get("X-WhisperRocket-Mode") == "transcript"
      and headers.get("X-WhisperRocket-Enhanced") == "0")
check("the caller is told why the cleanup did not run",
      headers.get("X-WhisperRocket-AI-Reason") == "usage_limit",
      headers.get("X-WhisperRocket-AI-Reason"))

body, headers = ask(dictate_clean)
check("a clean answer looks exactly as it did before",
      body == "tiszta szoveg"
      and headers.get("X-WhisperRocket-Enhanced") == "1"
      and "X-WhisperRocket-AI-Reason" not in headers)


# -- 4. the history entry ---------------------------------------------------

print("\nhistory.json - the reason is kept, old entries stay readable")

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "history.json"
    history_manager.get_history_path = lambda: path

    legacy = {
        "entries": [
            {   # written before the phone endpoint existed
                "id": "old-1",
                "timestamp": "2026-09-01T10:00:00",
                "text": "regi bejegyzes",
                "duration_sec": 3.5,
                "language": "hu",
            },
            {   # written before the reason was recorded: raw, no explanation
                "id": "old-2",
                "timestamp": "2026-09-09T16:19:35",
                "text": "nyers atirat",
                "duration_sec": 22.35,
                "language": "hu",
                "enhanced": False,
                "source": "phone",
            },
        ]
    }
    path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    history_manager.add_entry("nyers szoveg", 12.7, "hu", enhanced=False,
                              source="phone", ai_reason="timeout")
    history_manager.add_entry("tiszta szoveg", 4.0, "hu", enhanced=True,
                              source="phone", ai_reason="timeout")
    history_manager.add_entry("nincs ai", 2.0, "hu")
    history_manager.add_entry("hosszu ok", 5.0, "hu", enhanced=False,
                              ai_reason="internal_error(" + "x" * 500 + ")")

    entries = {e["id"]: e for e in history_manager.load_history()["entries"]}
    by_text = {e["text"]: e for e in entries.values()}

    check("the old entries survived the write",
          entries["old-1"] == legacy["entries"][0]
          and entries["old-2"] == legacy["entries"][1])
    check("a failed cleanup records the reason",
          by_text["nyers szoveg"].get("ai_reason") == "timeout")
    check("a successful cleanup does not",
          "ai_reason" not in by_text["tiszta szoveg"])
    check("a dictation with the feature off does not",
          "ai_reason" not in by_text["nincs ai"]
          and "enhanced" not in by_text["nincs ai"])
    check("a runaway reason is cut short here too",
          len(by_text["hosszu ok"]["ai_reason"]) == 200)
    check("the field names of the existing entries did not change",
          set(by_text["nyers szoveg"]) ==
          {"id", "timestamp", "text", "duration_sec", "language",
           "enhanced", "source", "ai_reason"})
    check("old and new entries read back together",
          len(entries) == 6 and all("text" in e for e in entries.values()))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
