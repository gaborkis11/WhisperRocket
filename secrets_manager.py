#!/usr/bin/env python3
"""
WhisperRocket - Secrets Manager

API tokens are stored OUTSIDE the project directory so they can never end up in
a git commit. They live in ~/.config/whisperrocket/.env with mode 0600.

Lookup order for any secret:
  1. A real environment variable (e.g. `export HF_TOKEN=...`) - always wins
  2. ~/.config/whisperrocket/.env

config.json is never used for secrets.
"""
import os
import tempfile
from typing import Dict, Optional

from platform_support import get_platform_handler

ENV_FILENAME = ".env"

_ENV_HEADER = [
    "# WhisperRocket secrets - DO NOT COMMIT, DO NOT SHARE",
    "# Managed by the app; one KEY=VALUE per line.",
    "# A real environment variable of the same name takes precedence.",
    "",
]

# Set once the .env file has been merged into os.environ
_env_loaded = False


def get_env_path() -> str:
    """Path to the secrets file (never inside the project directory)"""
    return str(get_platform_handler().get_config_dir() / ENV_FILENAME)


def _parse_env(text: str) -> Dict[str, str]:
    """Parse KEY=VALUE lines, tolerating `export`, quotes, comments"""
    values: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()

        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def _read_all() -> Dict[str, str]:
    """Read every secret from the .env file (empty dict if there is none)"""
    try:
        with open(get_env_path(), "r", encoding="utf-8") as f:
            return _parse_env(f.read())
    except Exception:
        return {}


def _write_all(values: Dict[str, str]) -> None:
    """Atomically rewrite the .env file, never leaving it world-readable"""
    config_dir = get_platform_handler().get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    path = get_env_path()

    content = "\n".join(_ENV_HEADER + [f"{k}={v}" for k, v in sorted(values.items())]) + "\n"

    fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), prefix=".env.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise


def load_env_file(force: bool = False) -> None:
    """
    Merge the .env file into os.environ.

    Existing environment variables are never overwritten, so a token exported in
    the shell always beats the stored one.
    """
    global _env_loaded
    if _env_loaded and not force:
        return
    _env_loaded = True

    for key, value in _read_all().items():
        if value and key not in os.environ:
            os.environ[key] = value


def get_secret(name: str) -> Optional[str]:
    """Read a secret from the environment, falling back to the .env file"""
    value = os.environ.get(name)
    if value:
        return value

    load_env_file()
    value = os.environ.get(name)
    return value or None


def set_secret(name: str, value: str) -> None:
    """Persist a secret to the .env file and make it visible to this process"""
    values = _read_all()
    values[name] = value
    _write_all(values)
    os.environ[name] = value


def delete_secret(name: str) -> None:
    """Remove a secret from the .env file and from this process"""
    values = _read_all()
    if values.pop(name, None) is not None:
        _write_all(values)
    os.environ.pop(name, None)
