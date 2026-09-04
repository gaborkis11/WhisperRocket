#!/usr/bin/env python3
"""
Tests for the recogniser-side vocabulary (hotwords).

The dictionary used to act only after recognition - as text replacement and
as a word list in the AI prompt - so a name Whisper mishears ("Sonny" for
"Sanyi") was already lost by the time anything looked at it. faster-whisper's
`hotwords` feeds the list into decoding itself, but silently cuts everything
past 223 tokens. These tests pin down the selection: the user marks the words
that must get through with a leading "!", the rest fill what is left, and
whatever does not fit is reported instead of vanishing.

Standard library only, never touches ~/.config/whisperrocket/.

    python3 tests/test_dictionary_hotwords.py
"""
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import dictionary_manager as dm  # noqa: E402
import transcription_engine  # noqa: E402

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


def word_tokens(text):
    """Fake tokenizer: one token per whitespace-separated word."""
    return len(text.split())


# --- parse: the "!" marker ---------------------------------------------------

terms = dm.parse("!Sanyi\nTomi\n! Zsófi\n!Tailscale: tail scale\n!\n")
by_name = {t["correct"]: t for t in terms}

check("marked term keeps its spelling without the marker",
      "Sanyi" in by_name and by_name["Sanyi"].get("priority") is True, str(terms))
check("unmarked term is not priority",
      by_name.get("Tomi", {}).get("priority") is False, str(by_name.get("Tomi")))
check("space after the marker is tolerated",
      by_name.get("Zsófi", {}).get("priority") is True, str(by_name.get("Zsófi")))
check("marker combines with literal corrections",
      by_name.get("Tailscale", {}).get("priority") is True
      and by_name["Tailscale"]["heard"] == ["tail scale"], str(by_name.get("Tailscale")))
check("a lone marker is not a word", "" not in by_name and len(terms) == 4, str(terms))

dup = dm.parse("Sanyi\n!Sanyi\n")
check("duplicate lines: marked wins regardless of order",
      len(dup) == 1 and dup[0]["priority"] is True, str(dup))

from translations import t as _t  # noqa: E402
for lang in ("en", "hu"):
    template = _t("ai_dict_template", lang)
    check(f"the {lang} template is comments only, so a fresh install has no words",
          dm.parse(template) == [], str(dm.parse(template)))
    check(f"the {lang} template no longer advertises the hotwords marker",
          "!" not in template, template)
    advanced = _t("ai_dict_dialog_advanced", lang)
    check(f"the {lang} advanced note says the marker does nothing now",
          "!" in advanced, advanced)

check("vocabulary() never shows the marker",
      dm.vocabulary(terms) == ["Sanyi", "Tomi", "Zsófi", "Tailscale"], str(dm.vocabulary(terms)))
fixed, n = dm.apply("we use tail scale", terms)
check("apply() still replaces on a marked term", fixed == "we use Tailscale" and n == 1, fixed)

rendered = dm.render(terms)
check("render() round-trips the marker",
      rendered == "!Sanyi\nTomi\n!Zsófi\n!Tailscale: tail scale\n", repr(rendered))
check("render() then parse() is stable", dm.parse(rendered) == terms)

# --- hotword_candidates: marked first, then the rest, file order kept ---------

order = dm.parse("Alpha\n!Bravo\nCharlie\n!Delta\n")
check("candidates: marked words first in file order, unmarked after",
      dm.hotword_candidates(order) == ["Bravo", "Delta", "Alpha", "Charlie"],
      str(dm.hotword_candidates(order)))
check("candidates of an empty dictionary is an empty list", dm.hotword_candidates([]) == [])

# --- pack_hotwords: fill the budget, report the rest ---------------------------

pack = dm.pack_hotwords(["Sanyi", "Tomi", "Berkes Annamária"], word_tokens, budget=4)
check("everything fits: comma-separated, nothing dropped",
      pack.text == "Sanyi, Tomi, Berkes Annamária" and pack.dropped == [] and pack.tokens == 4,
      str(pack))

pack = dm.pack_hotwords(["Sanyi", "Tomi", "Berkes Annamária"], word_tokens, budget=3)
check("over budget: the word that does not fit is dropped and named",
      pack.text == "Sanyi, Tomi" and pack.dropped == ["Berkes Annamária"]
      and pack.included == ["Sanyi", "Tomi"], str(pack))

pack = dm.pack_hotwords(["A", "Big Long Name", "C"], word_tokens, budget=2)
check("a word that does not fit does not block a later one that does",
      pack.text == "A, C" and pack.dropped == ["Big Long Name"], str(pack))

pack = dm.pack_hotwords([], word_tokens)
check("no words: empty text, nothing included", pack.text == "" and pack.included == [] and pack.tokens == 0)

pack = dm.pack_hotwords(["Far Too Long For This"], word_tokens, budget=2)
check("a single word over the whole budget is dropped", pack.text == "" and pack.dropped == ["Far Too Long For This"])

seen = []


def spying_tokens(text):
    seen.append(text)
    return word_tokens(text)


pack = dm.pack_hotwords(["Sanyi", "Tomi"], spying_tokens, budget=10)
check("the counter sees exactly what faster-whisper encodes (leading space, stripped list)",
      seen and all(s.startswith(" ") and not s.startswith("  ") for s in seen)
      and pack.text == "Sanyi, Tomi", str(seen))


# --- HotwordsProvider: reload, repack only on change, log the drop ------------

logged = []
provider = dm.HotwordsProvider(word_tokens, budget=3, log=logged.append)
t1 = dm.parse("!Sanyi\nTomi\nBerkes Annamária\n")

text = provider.current(t1)
check("provider returns the packed string", text == "Sanyi, Tomi", repr(text))
check("provider logs once, naming what was dropped and the budget use",
      len(logged) == 1 and "Berkes Annamária" in logged[0]
      and "2/3 words" in logged[0] and "2/3 tokens" in logged[0], str(logged))

provider.current(t1)
check("unchanged dictionary: no repack, no new log line", len(logged) == 1, str(logged))

t2 = dm.parse("!Sanyi\n!Berkes Annamária\nTomi\n")
text = provider.current(t2)
check("changed dictionary: repacked with the new priorities",
      text == "Sanyi, Berkes Annamária" and len(logged) == 2, f"{text!r} {logged}")

check("empty dictionary yields None so the caller passes hotwords=None",
      provider.current([]) is None)

# --- TranscriptionEngine forwards hotwords to the model ----------------------

calls = []


class FakeModel:
    def transcribe(self, file_path, **kwargs):
        calls.append(kwargs)
        return iter([]), types.SimpleNamespace(duration=1.0)


import threading  # noqa: E402

engine = transcription_engine.TranscriptionEngine(FakeModel(), "faster-whisper", threading.Lock())
engine.transcribe_file("x.wav", "hu", hotwords="Sanyi, Tomi")
check("transcribe_file passes hotwords through to model.transcribe",
      calls and calls[-1].get("hotwords") == "Sanyi, Tomi", str(calls))
engine.transcribe_file("x.wav", "hu")
check("without hotwords the model gets None (library default)",
      calls[-1].get("hotwords") is None, str(calls[-1]))

# --- Decode options: the hint must not starve the decoder --------------------
#
# faster-whisper builds the decoder prompt as sot_prev + hotwords (<= 223) +
# the previous window's text (<= 223, condition_on_previous_text is on by
# default) + sot_sequence (3), against a hard max_length of 448. With a full
# hint that prompt reaches 449 from the fourth 30 s window and generate()
# raises "The maximum decoding length must be > 0"; from the second window
# only a few dozen tokens are left and the text ends mid-word. Seen on real
# 70-93 s dictations on 2026-09-02/03 - every one of them was lost.

opts = dm.hotwords_options("Sanyi, Tomi")
check("with a hint, the previous window's text stays out of the prompt",
      opts == {"hotwords": "Sanyi, Tomi", "condition_on_previous_text": False}, str(opts))
check("without a hint the library defaults are untouched",
      dm.hotwords_options(None) == {"hotwords": None}, str(dm.hotwords_options(None)))
check("an empty hint counts as no hint",
      dm.hotwords_options("") == {"hotwords": None}, str(dm.hotwords_options("")))

room = dm.WHISPER_MAX_LENGTH - dm.HOTWORDS_PROMPT_OVERHEAD - dm.HOTWORDS_TOKEN_BUDGET
check("a full hint leaves the decoder more than half of max_length for one window",
      room > dm.WHISPER_MAX_LENGTH // 2, f"room={room}")
check("the budget stays under the library's silent cut-off",
      dm.HOTWORDS_TOKEN_BUDGET < 448 // 2 - 1, str(dm.HOTWORDS_TOKEN_BUDGET))

engine.transcribe_file("x.wav", "hu", hotwords="Sanyi, Tomi")
check("transcribe_file keeps the previous window out of the prompt when there is a hint",
      calls[-1].get("condition_on_previous_text") is False, str(calls[-1]))
engine.transcribe_file("x.wav", "hu")
check("transcribe_file leaves condition_on_previous_text alone without a hint",
      "condition_on_previous_text" not in calls[-1], str(calls[-1]))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
