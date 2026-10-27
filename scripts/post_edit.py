#!/usr/bin/env python3
"""PostToolUse-хук для Edit|Write.

Если изменён файл содержания (course.json / slice.json / demo.json / questions.json /
assignments.json) — прогоняет валидатор и возвращает Claude список нарушений;
если изменён docs/deferred/deferred.json — проверяет формат реестра отложенных решений
(код 2 → Claude видит stderr и исправляет).
"""
import json
import os
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input") or {}).get("file_path", "")
if not path:
    sys.exit(0)

name = os.path.basename(path)
root = os.environ.get("CLAUDE_PROJECT_DIR", ".")

if name in ("course.json", "slice.json", "demo.json", "questions.json", "assignments.json"):
    r = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "validate_content.py"), path],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        sys.exit(2)

if os.path.normpath(path).replace(os.sep, "/").endswith("docs/deferred/deferred.json"):
    r = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "deferred.py"), "validate"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("Реестр отложенных решений:\n" + r.stdout + r.stderr, file=sys.stderr)
        sys.exit(2)

sys.exit(0)
