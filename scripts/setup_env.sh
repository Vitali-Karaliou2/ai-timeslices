#!/bin/bash
# SessionStart-хук: готовит окружение Python в облачной сессии Claude Code.
# Локально (на вашей машине) ничего не делает: CLAUDE_CODE_REMOTE там не равен "true".
# В облачной VM python3 предустановлен; pypi.org и download.pytorch.org доступны
# из стандартного списка разрешённых доменов (PyPI). torch — отдельно, см. requirements-ml.txt.

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

if [ ! -d .venv ]; then
  echo "Создаю .venv ..."
  python3 -m venv .venv || exit 0
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null 2>&1 || true

if [ -f requirements.txt ]; then
  echo "Устанавливаю зависимости из requirements.txt ..."
  pip install -r requirements.txt || true
fi
# PyTorch сюда сознательно не входит (тяжёлый): когда план сессии потребует —
# pip install -r requirements-ml.txt

# Автоактивация venv для всех последующих bash-команд сессии.
grep -q 'TimeSlices-AI venv' "$HOME/.bashrc" 2>/dev/null || {
  echo "# TimeSlices-AI venv" >> "$HOME/.bashrc"
  echo "[ -f \"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/activate\" ] && source \"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/activate\"" >> "$HOME/.bashrc"
}

echo "Окружение готово: $(python --version 2>/dev/null)"
exit 0
