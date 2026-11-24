#!/usr/bin/env python3
"""
WhisperRocket - Lasting record of failed phone dictations

A phone dictation that fails before it has text - model still loading, no
speech heard, endpoint busy, wrong token, recording too large, a crash - never
reaches history.json, and the app's stdout log (/tmp/whisper_stdout.log) is
overwritten on every start. So until 2026-11-24 "it did not work in the car
yesterday" could not be traced at all.

This file keeps one line per such failure, next to history.json:

    2026-11-24 09:41:07  503 not_ready  100.64.0.7

Only the status, the error key, the client's Tailscale address and, for a
crash, the exception. Never the audio, the transcript or the token. Rotated
at LOG_MAX_BYTES with one backup, so it cannot grow without bound.
"""
import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "phone_errors.log"
LOG_MAX_BYTES = 256 * 1024
LOG_BACKUPS = 1

_lock = threading.Lock()
_loggers = {}  # one per directory, so the tests can point it at a temp dir


def _get_logger(config_dir: Path) -> logging.Logger:
    key = str(config_dir.resolve())
    with _lock:
        if key not in _loggers:
            config_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(config_dir / LOG_FILENAME,
                                          maxBytes=LOG_MAX_BYTES,
                                          backupCount=LOG_BACKUPS,
                                          encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s",
                                                   "%Y-%m-%d %H:%M:%S"))
            logger = logging.getLogger(f"whisperrocket.phone:{key}")
            logger.propagate = False
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            _loggers[key] = logger
        return _loggers[key]


def record(config_dir: Path, status: int, key: str, client: str = "",
           detail: str = "") -> None:
    """Append one failure line. Never raises: the phone's answer matters more."""
    try:
        line = f"{status} {key}  {client}".rstrip()
        if detail:
            # One line per failure, whatever the exception text holds
            line += "  " + " ".join(detail.split())[:300]
        _get_logger(Path(config_dir)).info(line)
    except Exception as error:
        print(f"[PHONE] could not write {LOG_FILENAME}: {error}")
