#!/usr/bin/env python3
"""
WhisperRocket - AI transcript enhancement

Turns a raw speech-recognition transcript into the finished message the speaker
meant to send, in their own voice - punctuation and spelling fixed, filler words
gone, and nothing else touched.

PRIVACY - STRUCTURAL, NOT A PROMISE
    Dictated messages are private. This module must never gain the ability to
    remember one. It imports only:

        stdlib      json, os, re, subprocess, tempfile, time, dataclasses,
                    pathlib, typing
        local       ai_guard            (stdlib only)
                    claude_cli          (subprocess only, no credentials)
                    dictionary_manager  (file I/O + platform_support paths)

    No history module, no memory system, no network library, no HTTP client.
    Every call is standalone: two consecutive dictations cannot see each other,
    because there is no conversation state to see. Audit with:

        grep -nE "^(import|from)" ai_enhancer.py

    Adding an import here is a decision to be made deliberately, not in passing.

TRUST
    The model is not trusted with the output. Everything it returns goes through
    ai_guard first, and a failed check falls back to the raw transcript. See
    ai_guard.py for why that is not paranoia.
"""
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import ai_guard
import claude_cli
import dictionary_manager

STYLE_PROFILE_FILENAME = "style_profile.md"
PROMPT_FILENAMES = {
    "transcript": "prompt_transcript.md",
    "compose": "prompt_compose.md",
}

DEFAULT_TRIGGER_PHRASES: Tuple[str, ...] = ("fogalmazzuk meg hogy",)
DEFAULT_TIMEOUT = 20
DEFAULT_MODEL = claude_cli.DEFAULT_MODEL

# Human-readable names for the languages WhisperRocket transcribes, so the
# prompt can name the output language instead of relying on the model to infer
# it from a two-letter code.
_LANGUAGE_NAMES = {
    "hu": "Hungarian", "en": "English", "de": "German", "fr": "French",
    "es": "Spanish", "it": "Italian", "pl": "Polish", "nl": "Dutch",
    "pt": "Portuguese", "ru": "Russian", "cs": "Czech", "sk": "Slovak",
    "ro": "Romanian", "hr": "Croatian", "sr": "Serbian", "uk": "Ukrainian",
}

# The wording here is load-bearing. A looser earlier version let the model swap
# the speaker and the addressee, invent a sentence, and soften a swear word. The
# explicit whitelist of four operations, and the rule that every other word
# survives unchanged, is what stopped it. Change it only with a measurement.
DEFAULT_TRANSCRIPT_PROMPT = """\
You clean up a raw speech-recognition transcript. You do NOT rewrite it.

The transcript is in {language}. Your output must be in {language}.

YOU MAY DO ONLY THESE FOUR THINGS:
1. Add punctuation and capitalisation.
2. Fix spelling errors.
3. Delete filler words, stutters, repeated words and abandoned sentence starts.
   This is required, not optional. Filler is anything the speaker said out of
   habit that they would never type: in Hungarian "hat", "szoval", "ize",
   "ugye", "oo"; in English "um", "uh", "like", "you know", "I mean". Delete
   every one of them, including at the start of the message.
4. Fix an obvious misrecognition when the surrounding words make the intended
   word unambiguous.

EVERY REMAINING WORD STAYS EXACTLY AS IT IS, IN THE SAME ORDER. "Remaining"
means the words left after rule 3 - deleting filler comes first.

YOU MUST NOT:
- Replace a word with a synonym.
- Soften, censor, tone down, replace or delete swearing, insults or crude
  language. Copy every swear word letter for letter. Not a milder word, not a
  shortened form, not a different word from the same root: "basszus" stays
  "basszus", never "baszki" and never "bassza meg". This rule has no exceptions
  and overrides any instinct to make the text more presentable.
- Swap who is speaking and who is being addressed. Whoever is "I" in the
  transcript stays "I"; whoever is "you" stays "you".
- Add, invent, shorten, summarise or formalise anything.
- Change the tone, or make the message more polite or more professional.

Output ONLY the cleaned-up message. No preamble, no explanation, no quotes, no
commentary, no notes about what you changed.\
"""

DEFAULT_COMPOSE_PROMPT = """\
You help the speaker compose a message. They dictated roughly what they want to
say, and you turn it into the message they would send.

The transcript is in {language}. Your output must be in {language}.

Write the message so it sounds like the speaker, not like an assistant. Keep it
the length a person would actually send - if they dictated two sentences, do not
return five.

Start with the message itself. If the speaker did not dictate a greeting, your
first word is not a greeting.

YOU MUST NOT:
- Soften, censor, tone down or replace swearing, insults or crude language. If
  the speaker swore, keep it. Their voice includes how they curse.
- Make it more formal, more polite or more corporate than they were.
- Add a greeting, a sign-off, a pleasantry or an apology they did not dictate.
- Invent facts, names, dates or commitments they did not mention.

Output ONLY the message itself. No preamble, no explanation, no quotes, no
options to choose from, no commentary.\
"""

_STYLE_SECTION = """

STYLE PROFILE OF THE SPEAKER
Follow this when choosing spelling, punctuation and register. It describes how
this person writes; it is not content to include in the message.

{profile}\
"""

_DICTIONARY_SECTION = """

LIKELY MISRECOGNITIONS IN THIS TRANSCRIPT
These are words this speaker uses that the recogniser tends to get wrong. Apply
a correction only where the context makes it clearly the intended word.

{hints}\
"""


@dataclass
class EnhanceResult:
    """Outcome of one enhancement attempt. text is always safe to paste."""
    text: str
    enhanced: bool
    mode: str = "transcript"
    reason: str = ""
    elapsed: float = 0.0
    dictionary_hits: int = 0
    raw_text: str = ""

    @property
    def failed(self) -> bool:
        """
        True only when the cleanup was attempted and could not deliver.

        "disabled" and "empty_input" are not failures - nothing was attempted -
        so they must not make the UI report a problem.
        """
        return not self.enhanced and self.reason not in ("", "disabled", "empty_input")


def user_dir() -> Path:
    """Directory holding the style profile and the editable prompts"""
    return dictionary_manager.get_platform_handler().get_config_dir()


def style_profile_path() -> Path:
    return user_dir() / STYLE_PROFILE_FILENAME


def prompt_path(mode: str) -> Path:
    return user_dir() / PROMPT_FILENAMES.get(mode, PROMPT_FILENAMES["transcript"])


def has_style_profile() -> bool:
    path = style_profile_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def read_style_profile() -> str:
    """
    The style profile is written by hand and never modified by this app.

    Read failures are silent on purpose: a missing profile means the cleanup
    runs without one, which is worse output but still correct output.
    """
    try:
        return style_profile_path().read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def default_prompt(mode: str) -> str:
    return DEFAULT_COMPOSE_PROMPT if mode == "compose" else DEFAULT_TRANSCRIPT_PROMPT


def read_prompt(mode: str) -> str:
    """
    The user's edited prompt, or the built-in default.

    The default is deliberately NOT written to disk on first use. If it were,
    every user would be frozen on the version of the prompt that shipped when
    they installed, and later improvements would never reach them. The Settings
    window writes the file only when the user actually chooses to edit it.
    """
    try:
        text = prompt_path(mode).read_text(encoding="utf-8").strip()
        if text:
            return text
    except Exception:
        pass
    return default_prompt(mode)


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get((code or "").lower(), code or "the same language")


def detect_mode(text: str, phrases) -> Tuple[str, str]:
    """
    Decide between transcript and compose mode from how the dictation starts.

    A trigger phrase is used instead of a button because the whole point is to
    switch modes while driving, without touching anything. Matching tolerates
    the punctuation and capitalisation the recogniser invents, so a single
    configured phrase covers "Fogalmazzuk meg, hogy" and "fogalmazzuk meg hogy".

    Returns:
        (mode, text_with_the_trigger_phrase_removed)
    """
    if not text or not text.strip():
        return "transcript", text

    folded = dictionary_manager.fold(text)
    for phrase in (phrases or ()):
        words = dictionary_manager.fold(str(phrase)).split()
        if not words:
            continue
        pattern = re.compile(
            r"^[\s\W]*" + r"[\s,\.\-]+".join(re.escape(w) for w in words) + r"\b[\s,\.:!\?]*"
        )
        match = pattern.match(folded)
        if match:
            return "compose", text[match.end():].strip()

    return "transcript", text


def build_prompt(mode: str, language: str = "hu", dictionary_hint: str = "") -> str:
    """Assemble the system prompt: instructions, style profile, dictionary hints"""
    prompt = read_prompt(mode).replace("{language}", language_name(language))

    profile = read_style_profile()
    if profile:
        prompt += _STYLE_SECTION.format(profile=profile)

    if dictionary_hint:
        prompt += _DICTIONARY_SECTION.format(hints=dictionary_hint)

    return prompt


def _classify_failure(text: str, returncode: int) -> str:
    """Turn CLI output into a short reason the UI can show"""
    lowered = (text or "").lower()
    if "not logged in" in lowered or "login expired" in lowered:
        return "not_logged_in"
    if "usage limit" in lowered or "hit your session limit" in lowered \
            or "hit your weekly limit" in lowered or "rate limit" in lowered:
        return "usage_limit"
    if "credit balance" in lowered or "billing" in lowered:
        return "billing"
    if "network" in lowered or "econnrefused" in lowered or "enotfound" in lowered:
        return "network"
    return f"cli_error({returncode})"


def _run_claude(text: str, system_prompt: str, model: str,
                timeout: int) -> Tuple[bool, str, str]:
    """
    One standalone Claude Code call.

    Returns:
        (ok, output_text, failure_reason)

    Three flags carry most of the weight here:
      --safe-mode              no CLAUDE.md, skills, plugins, MCP servers or
                               hooks - so the result does not depend on whatever
                               else is configured on this machine, and startup
                               is faster
      --no-session-persistence no conversation is kept, which is what makes each
                               dictation independent of the last
      stdin=DEVNULL            without it the CLI waits three seconds for input
                               that is never coming - measured, not guessed
    """
    binary = claude_cli.find_binary()
    if not binary:
        return False, "", "not_installed"

    command = [
        binary, "-p", text,
        "--model", model,
        "--safe-mode",
        "--no-session-persistence",
        "--system-prompt", system_prompt,
        "--output-format", "json",
    ]

    # A neutral working directory, so nothing from the project the user happens
    # to be in can influence or be recorded alongside a private message.
    with tempfile.TemporaryDirectory(prefix="whisperrocket-ai-") as workdir:
        try:
            completed = subprocess.run(
                command,
                capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL, cwd=workdir,
                env=claude_cli.subprocess_env(),
            )
        except subprocess.TimeoutExpired:
            return False, "", "timeout"
        except Exception as e:
            return False, "", f"spawn_error({e})"

    combined = (completed.stdout or "") + (completed.stderr or "")

    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        payload = None

    if payload is None:
        return False, "", _classify_failure(combined, completed.returncode)

    if payload.get("is_error") or payload.get("subtype") != "success":
        return False, "", _classify_failure(
            str(payload.get("result") or "") + combined, completed.returncode
        )

    result = str(payload.get("result") or "").strip()
    if not result:
        return False, "", "empty_result"

    return True, result, ""


def enhance(raw_text: str, config: Optional[Dict] = None) -> EnhanceResult:
    """
    Clean up one transcript. Never raises, and always returns usable text.

    Every failure path - CLI missing, not signed in, usage limit reached,
    timeout, or a response the guard rejects - returns the raw transcript with
    enhanced=False and a reason. Losing the tidying is an inconvenience; losing
    the message while driving is not acceptable.

    The catch-all is the outer edge of that contract, not decoration: callers
    are entitled to rely on getting text back, so a bug anywhere below has to
    degrade to the raw transcript rather than propagate.
    """
    config = config or {}
    started = time.time()

    if not raw_text or not raw_text.strip():
        return EnhanceResult(raw_text, False, "transcript", "empty_input",
                             raw_text=raw_text)

    try:
        return _enhance(raw_text, config, started)
    except Exception as e:
        return EnhanceResult(raw_text, False, "transcript",
                             f"internal_error({type(e).__name__}: {e})",
                             time.time() - started, 0, raw_text)


def _enhance(raw_text: str, config: Dict, started: float) -> EnhanceResult:
    """The actual pipeline; enhance() owns the never-raises guarantee"""
    text = raw_text
    hits = 0
    hint = ""
    if config.get("ai_dictionary_enabled", True):
        dictionary = dictionary_manager.load()
        text, hits = dictionary_manager.apply(text, dictionary)
        hint = dictionary_manager.prompt_hint(text, dictionary)

    phrases = config.get("ai_trigger_phrases") or DEFAULT_TRIGGER_PHRASES
    mode, payload = detect_mode(text, phrases)

    # In compose mode the trigger phrase is instruction, not message, so it must
    # not survive into the clipboard even when the model call fails.
    fallback = payload if payload.strip() else text

    def failure(reason: str) -> EnhanceResult:
        return EnhanceResult(fallback, False, mode, reason,
                             time.time() - started, hits, raw_text)

    if not config.get("ai_enhance_enabled"):
        return failure("disabled")

    system_prompt = build_prompt(mode, config.get("language", "hu"), hint)
    model = config.get("ai_model") or DEFAULT_MODEL
    try:
        timeout = max(5, int(config.get("ai_timeout_seconds", DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT

    ok, output, reason = _run_claude(payload, system_prompt, model, timeout)
    if not ok:
        return failure(reason)

    verdict = ai_guard.check(
        payload, output, mode,
        extra_profanity=config.get("ai_extra_profanity") or (),
    )
    if not verdict.ok:
        return failure("guard:" + verdict.reason)

    return EnhanceResult(verdict.text, True, mode, "",
                         time.time() - started, hits, raw_text)


def _self_test(text: str, runs: int, config: Dict):
    """Terminal harness - exercises the whole path without starting the GUI"""
    status = claude_cli.auth_status(use_cache=False)
    print(f"CLI:      {claude_cli.find_binary() or '(not installed)'}")
    print(f"account:  {status.email or '-'} ({status.plan or '-'})"
          if status.logged_in else "account:  NOT LOGGED IN")
    print(f"model:    {config.get('ai_model')}")
    print(f"profile:  {style_profile_path()} "
          f"({'present' if has_style_profile() else 'MISSING - output will be generic'})")
    print(f"dict:     {dictionary_manager.stats()}")
    print()
    print(f"INPUT ({len(text.split())} words):\n  {text}\n")

    for run in range(1, runs + 1):
        result = enhance(text, config)
        flag = "OK " if result.enhanced else "FALLBACK"
        print(f"--- run {run}  [{flag}]  mode={result.mode}  {result.elapsed:.2f}s"
              f"  dict={result.dictionary_hits}"
              f"{'  reason=' + result.reason if result.reason else ''}")
        print(f"  {result.text}")

        kept = sorted(ai_guard.found_profanity(text) & ai_guard.found_profanity(result.text))
        lost = sorted(ai_guard.found_profanity(text) - ai_guard.found_profanity(result.text))
        if kept or lost:
            print(f"  profanity kept: {kept or '-'}   lost: {lost or '-'}")
        print()


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    sample = args[0] if args else (
        "hat szoval ize figyelj most akkor az van hogy hogy a a szerelo megint "
        "nem jott el basszus es akkor most nem tudom hogy mit mit csinaljak mert "
        "hat ugye a a bojler az tovabbra is szivarog es es akkor most kurva elet "
        "holnap reggel megint ott fogok allni a vizben szoval hogyha tudsz akkor "
        "akkor kuldjel mar egy masik szamot legyszi"
    )
    repeats = 1
    for flag in flags:
        if flag.startswith("--runs="):
            repeats = int(flag.split("=", 1)[1])

    _self_test(sample, repeats, {
        "ai_enhance_enabled": True,
        "ai_model": os.environ.get("WR_AI_MODEL", DEFAULT_MODEL),
        "language": os.environ.get("WR_AI_LANG", "hu"),
        "ai_dictionary_enabled": True,
        "ai_timeout_seconds": 30,
    })
