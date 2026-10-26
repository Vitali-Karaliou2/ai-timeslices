# Сессия 01_ИИ. Скелет оболочки

Ветка: `session-01-ai-skeleton`. Ожидаемый результат — PR в `main`, который можно
установить, запустить и прогнать тесты в облачной сессии и на локальной машине.

## Задача
Создать скелет FastAPI-оболочки по CLAUDE.md, docs/spec/shell-spec.md и
docs/spec/content-schema.md. Содержания — ровно столько, чтобы работала навигация:
два фиктивных среза.

## Шаги
1. Каркас: пакет `app/` (main.py, config.py, models.py, content.py, db.py, templates/,
   static/), `tests/`, `.gitignore` для Python (+ `app.db`, `.venv/`), `alembic init`
   с SQLite; `pytest.ini`/`pyproject.toml` — минимально.
2. Dev-пользователь: создаётся при старте в Development, автовход (cookie-сессия);
   никаких форм логина и ролей на 0→1.
3. Загрузка содержания: `app/content.py` читает `content/course.json` и `slice.json`
   срезов, проверяет уникальность id и существование файлов страниц; при ошибке —
   fail fast с понятным сообщением.
4. Модели SQLAlchemy: `users`, `user_slice_state` (state: Unavailable/Available/
   InProgress/Done; last_page); первая миграция Alembic.
5. Страницы по shell-spec: `/` (карта курса с состояниями; golden/winter различимы),
   `/slices/{id}` → редирект, `/slices/{id}/pages/{n}` (Markdown-рендер, навигация
   ←/→/оглавление, «Срез пройден» на последней), `POST /slices/{id}/done`,
   `/admin/db` (read-only инспектор: таблицы, строки limit 200).
6. Фиктивное содержание: срезы `ai-overview` (2 страницы: overview, history) и
   `neuron-1943` (2 страницы: idea, math) с текстами-заглушками `ЧЕРНОВИК`.
   Демо в этой сессии НЕ делать — оно в сессии 02 (`neuron-line` по скиллу `new-demo`).
7. Тесты (pytest + httpx) по docs/acceptance.md: порядок срезов; недоступность среза
   при непройденном предыдущем (и по прямому URL); «Срез пройден» открывает следующий;
   повторное прохождение не ломает состояния; /admin/db отвечает и показывает таблицы.
8. `pytest` зелёный. Коммит, пуш, PR. Отчёт по скиллу `session-report`.

## Не делать в этой сессии
Демо и трассы; вопросы и задания; реальные тексты срезов; оформление сверх читаемого
минимума; live-режим; PyTorch.
