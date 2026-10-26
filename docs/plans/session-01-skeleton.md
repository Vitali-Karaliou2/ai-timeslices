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

## Итог
1. **Сделано**
   - Оболочка `app/`: config (переменные окружения `TIMESLICES_*`), db (Alembic
     `upgrade head` при старте), models (`users`, `user_slice_state`), content (загрузка
     course.json/slice.json/demo.json, fail fast), progress (состояния срезов), main
     (маршруты shell-spec), шаблоны Jinja2 и минимальный CSS (golden/winter различимы).
   - Dev-пользователь создаётся при старте в Development, автовход через cookie-сессию.
   - Первая миграция Alembic `878d1e49ea4d` (users, user_slice_state).
   - Фиктивные срезы `ai-overview` и `neuron-1943` (по 2 страницы, тексты `ЧЕРНОВИК:`).
   - 18 тестов pytest: порядок, недоступность (страницы, POST, демо-статика), навигация
     и Markdown, Done → следующий срез, повторное прохождение, перестановка срезов,
     fail fast содержания, /admin/db, закрытие вне Development.
   - По ревью: `/content` отдаёт только `demos/` доступного среза; «Срез пройден»
     только из InProgress/Done.
2. **Сознательно не сделано и почему**
   - Демо, трассы, iframe для страниц `type: demo`, рендер `type: questions` — сессия 02
     (план: «демо в этой сессии НЕ делать»). Поэтому acceptance п. 6 пока не покрыт.
   - Гонка при первом параллельном обращении (UniqueConstraint в user_slice_state → 500
     у одного из запросов) — не исправлена: один dev-пользователь, риск мал.
   - `pydantic-settings` (упомянут в shell-spec) не используется: его нет в списке
     разрешённых зависимостей; хватает pydantic + os.environ. Спецификацию не правил.
   - Предупреждение Starlette «httpx в TestClient устарел, ставьте httpx2» — не трогал:
     httpx2 вне разрешённого списка.
3. **Проверка**
   - `pytest -q` → `18 passed, 1 warning`.
   - `python3 scripts/validate_content.py` для course.json и обоих slice.json → OK.
   - `alembic revision --autogenerate` + `alembic upgrade head` → таблицы созданы.
   - `uvicorn app.main:app --port 8000` на отдельной БД (scratchpad): `/` → 200 (ai-overview
     Available, neuron-1943 Unavailable); `/slices/neuron-1943/pages/1` → 403;
     `/slices/ai-overview/pages/2` → 200; `/admin/db/user_slice_state` → 200. Браузером
     страницы не смотрел.
   - code-reviewer: 2 блокирующих замечания (утечка через /content; Done без открытия) —
     исправлены, тесты добавлены; повторно рецензент не запускался.
4. **Допущения, принятые за автора**
   - Годы и метаданные фиктивных срезов: `ai-overview` 1943–2026, `neuron-1943` 1943–1943;
     оба `genai`/`golden`. ПРОВЕРИТЬ ДАТУ: 1943 — год модели нейрона Мак-Каллока и Питтса.
     ПРОВЕРИТЬ ДАТУ: границы обзорного среза 1943–2026.
   - Заголовки страниц-заглушек («Обзор курса», «Идея», …) — без пометки ЧЕРНОВИК
     (пометка стоит в теле страницы и в summary).
   - Нумерация страниц в URL с 1; недоступный срез → 403 со страницей «Срез недоступен».
   - «Срез пройден» на неоткрытом срезе — редирект на срез (а не ошибка).
   - Вне Development /admin/db отдаёт 404, а старт без TIMESLICES_SECRET_KEY невозможен.
   - Перестановка срезов: сохранённые InProgress/Done не теряются, но показываются как
     Unavailable, пока не пройдены новые предшественники.
5. **Черновик ADR**: `docs/decisions/0004-content-static-demos-only.md` (proposed) —
   `/content` отдаёт только `demos/` доступного среза вместо всей папки `content/`.
6. **Следующая сессия**: 02 — демо `neuron-line` по скиллу `new-demo` в срезе
   `neuron-1943`; заодно iframe и код генератора на странице `type: demo` (acceptance п. 6).
