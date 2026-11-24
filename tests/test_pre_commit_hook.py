#!/usr/bin/env python3
"""
Tests for .githooks/pre-commit - the last line before the public repository.

Each case makes a real commit attempt in a throwaway repository that uses the
hook, with a fake .env, so nothing here touches the user's files or secrets.
Standard library and git only:

    python3 tests/test_pre_commit_hook.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".githooks" / "pre-commit"
FAKE_SECRET = "Zx9fakeTokenForHookTest_0123456789abcdefghij"

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


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=test",
                           "-c", "user.email=test@example.invalid", *args],
                          capture_output=True, text=True, env=env)


def attempt(files, rename=None):
    """Stage the files (with -f, as a careless add would) and try to commit"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        hooks = repo / ".githooks"
        hooks.mkdir()
        shutil.copy(HOOK, hooks / "pre-commit")
        (hooks / "pre-commit").chmod(0o755)
        git(repo, "config", "core.hooksPath", ".githooks")
        (repo / "README.md").write_text("base\n")
        git(repo, "add", "-f", ".githooks", "README.md")
        git(repo, "commit", "-q", "--no-verify", "-m", "base")

        env_file = Path(tmp) / "fake.env"
        env_file.write_text(f'WHISPERROCKET_PHONE_TOKEN="{FAKE_SECRET}"\nSHORT=abc\n')
        env = dict(os.environ, WHISPERROCKET_ENV_FILE=str(env_file))

        if rename:
            source, target = rename
            (repo / source).write_text("template\n")
            git(repo, "add", "-f", source)
            git(repo, "commit", "-q", "--no-verify", "-m", "template")
            git(repo, "mv", source, target)
        for name, content in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            git(repo, "add", "-f", name)
        result = git(repo, "commit", "-q", "-m", "attempt", env=env)
        return result.returncode == 0, result.stderr


blocked_names = [
    "style_profile.md", "my_style_profile.md", "dictionary.md", "old_dictionary.txt",
    "dictionary.json.bak", "prompt_transcript.md", "prompt_compose.md", "history.json",
    "phone_history.json", "config.json", "CLAUDE.md", "DEVLOG.md", ".env", "phone.env",
    "tasks/todo.md", ".claude/settings.json", "personal/notes.md", "private/x.txt",
]
for name in blocked_names:
    ok, err = attempt({name: "content\n"})
    check(f"'{name}' is refused", not ok, err[-200:])

allowed_names = ["style_profile.example.md", "dictionary.example.md", "config.example.json",
                 "ai_guard.py", "tests/test_dictionary_hotwords.py", "docs/guide.md"]
for name in allowed_names:
    ok, err = attempt({name: "content\n"})
    check(f"'{name}' is allowed", ok, err[-200:])

ok, err = attempt({}, rename=("style_profile.example.md", "style_profile.md"))
check("renaming a template to a personal name is refused", not ok, err[-200:])

ok, err = attempt({"notes/innocent_name.py": f"TOKEN = '{FAKE_SECRET}'\n"})
check("a real secret from .env is refused in any file", not ok, err[-200:])
check("the secret itself is never printed", FAKE_SECRET not in err)

ok, err = attempt({"code.py": "x = 'abc'\n"})
check("a short .env value does not block ordinary code", ok, err[-200:])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
