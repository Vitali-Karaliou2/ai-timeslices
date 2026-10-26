# Спецификация оболочки, стадия 0→1

Оболочка — одно FastAPI-приложение с server-side рендерингом (Jinja2), архитектурно
эквивалентное ASP.NET Core Razor Pages. Соответствия, чтобы переносить интуицию
из предыдущего проекта:

| ASP.NET Core            | Здесь                               |
|-------------------------|--------------------------------------|
| Kestrel                 | uvicorn                              |
| Razor Pages (.cshtml)   | маршруты FastAPI + шаблоны Jinja2    |
| EF Core                 | SQLAlchemy (ORM)                     |
| EF Migrations           | Alembic                              |
| appsettings.json        | app/config.py (pydantic-settings)    |
| Identity                | один dev-пользователь, автовход в Development (роли не нужны на 0→1) |
| wwwroot                 | app/static + content/ (отдаётся как статические файлы) |

## Маршруты
- `GET /` — карта курса: срезы в линейном порядке, каждый с состоянием для текущего
  пользователя (Unavailable / Available / InProgress / Done) и периодом (golden/winter
  различимы визуально — это несёт смысл «смен надежд и разочарований»).
- `GET /slices/{slice_id}` — редирект на первую (или последнюю открытую) страницу среза.
- `GET /slices/{slice_id}/pages/{n}` — страница n среза: отрендеренный Markdown;
  для `type: demo` — дополнительно iframe на `entry` демо и код генератора рядом;
  для `type: questions` — вопросы с раскрываемыми ответами (details/summary);
  навигация: ← предыдущая, → следующая, оглавление среза.
  На последней странице — кнопка «Срез пройден».
- `POST /slices/{slice_id}/done` — пометить срез пройденным; следующий срез становится
  Available.
- `GET /content/...` — статика содержания (демо, трассы).
- `GET /admin/db` — read-only инспектор БД: список таблиц (SQLAlchemy inspector),
  по клику — строки таблицы (limit 200) и DDL. Аналог Object Explorer; никакого ввода SQL.

## Состояния и БД
Таблицы (SQLAlchemy, SQLite `app.db`):
- `users` — на 0→1 один dev-пользователь, создаётся при старте.
- `user_slice_state` — user_id × slice_id × state (Unavailable/Available/InProgress/Done)
  × last_page × updated_at.
Правила: первый срез Available; срез недоступен, пока предыдущий не Done; открытие
Available-среза переводит его в InProgress; «Срез пройден» → Done; повторное открытие
пройденного среза состояний не ломает.

## Загрузка содержания
`app/content.py` читает `content/course.json` и `slice.json` каждого среза при старте,
проверяет: id уникальны, файлы страниц существуют, демо-манифесты валидны. Ошибка
содержания — понятное сообщение и отказ стартовать (fail fast).
