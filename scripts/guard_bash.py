#!/usr/bin/env python3
"""PreToolUse-хук для Bash: блокирует необратимые или запрещённые действия.

Хук получает JSON с tool_name и tool_input на stdin.
Код выхода 2 = заблокировать; текст в stderr возвращается Claude как объяснение.
Это детерминированная страховка поверх правил CLAUDE.md: правило в промпте
модель выполняет «как правило», хук — всегда.
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = (data.get("tool_input") or {}).get("command", "")

BLOCKED = [
    (r"\bgit\s+push\b.*(--force|-f\b|--force-with-lease)", "force-push запрещён (CLAUDE.md: необратимое)"),
    (r"\bgit\s+push\b[^|&;]*\s(\S+\s+)?(HEAD:)?main(\s|$|:)", "push прямо в main запрещён: работай в ветке сессии и открой PR"),
    (r"\bgit\s+reset\s+--hard", "git reset --hard запрещён"),
    (r"\bgit\s+branch\s+-D\b", "удаление веток запрещено"),
    (r"\brm\s+-rf?\s+/(\s|$)", "rm -rf / запрещён"),
    (r"\brm\s+-rf?\s+\.\s*(\s|$)", "rm -rf . запрещён"),
    (r"\brm\s+(-\S+\s+)*\S*app\.db", "удаление app.db запрещено: это рабочая БД автора"),
    (r"\bpip3?\s+install\b(?!\s+(--upgrade\s+pip\b|-r\s+requirements(-ml)?\.txt\b))",
     "новые pip-пакеты только через requirements.txt и с согласия автора (CLAUDE.md)"),
    (r"\bnpm\s+(install|i|add)\s+\S", "npm-пакеты в этом проекте не используются (фронтенд без сборщиков)"),
    (r"\balembic\s+downgrade\b", "alembic downgrade запрещён: откат схемы БД — только решением автора"),
]

for pattern, reason in BLOCKED:
    if re.search(pattern, cmd):
        print(f"ЗАБЛОКИРОВАНО хуком guard_bash.py: {reason}. Команда: {cmd}", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
