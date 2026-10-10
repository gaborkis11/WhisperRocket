#!/usr/bin/env python3
"""
The model the running app uses cannot be deleted, even after the config was
switched to another one without a restart: the app reloads it from disk after
every idle release (warm_model.py), and a deleted one would be downloaded
again, silently, by the next dictation.

Stdlib only: the model list and the config are faked, nothing is deleted.

    python3 tests/test_model_protection.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import model_manager  # noqa: E402

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


GB = 1024 ** 3

# Config already says medium (saved, not restarted); the app still runs large-v3
model_manager.get_active_model = lambda: "medium"
model_manager.get_downloaded_models = lambda: [
    {"name": "large-v3", "size": 3 * GB},
    {"name": "medium", "size": 1 * GB},
    {"name": "small", "size": GB // 2},
]
model_manager.get_current_device = lambda: "cuda"
model_manager.get_local_model_path = lambda name, device=None: f"/nonexistent/{name}"
model_manager.get_cache_path = lambda name, device=None: f"/nonexistent/cache/{name}"

check("before startup only the configured model is protected",
      model_manager.is_protected("medium") and not model_manager.is_protected("large-v3"))

model_manager.set_running_model("large-v3")
check("the running model is protected", model_manager.is_protected("large-v3"))
check("the configured model stays protected", model_manager.is_protected("medium"))
check("any other model is not", not model_manager.is_protected("small"))

ok, message = model_manager.delete_model("large-v3")
check("delete_model refuses the running model",
      not ok and message == "active_model_cannot_delete", message)

check("the freeable size leaves the running model out",
      model_manager.get_freeable_size() == GB // 2, str(model_manager.get_freeable_size()))

tried = []
model_manager.delete_model = lambda name, device=None: (tried.append(name), (True, ""))[1]
model_manager.delete_all_unused()
check("delete all unused skips the running and the configured model",
      tried == ["small"], str(tried))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
