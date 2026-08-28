#!/usr/bin/env python3
"""
The security invariant of the phone endpoint, kept as a test.

phone_endpoint.py is the only code a remote machine can reach, and its defence
is structural: it imports nothing from the rest of the application, so there is
no path through which a request could touch the user's settings, history,
dictionary or style profile. A comment can drift; an import list can be checked.

    python3 tests/test_stdlib_guarantee.py
"""
import ast
import sys
from pathlib import Path

source = (Path(__file__).resolve().parent.parent / "phone_endpoint.py").read_text()

modules = set()
for node in ast.walk(ast.parse(source)):
    if isinstance(node, ast.Import):
        modules.update(alias.name.split(".")[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        modules.add(node.module.split(".")[0])

outside = sorted(name for name in modules if name not in sys.stdlib_module_names)

print("imported modules:", ", ".join(sorted(modules)))
if outside:
    print(f"FAIL  phone_endpoint.py imports outside the standard library: {outside}")
    print("      That breaks the module's security guarantee - see its docstring.")
    sys.exit(1)

print("PASS  phone_endpoint.py imports only the standard library")
