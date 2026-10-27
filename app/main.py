"""Оболочка TimeSlices-AI: маршруты FastAPI (аналог Razor Pages) и сборка приложения."""
import hashlib
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import progress
from app.config import DEV_SECRET_KEY, ROOT_DIR, Settings, get_settings
from app.content import Course, load_course, read_page
from app.db import make_engine, make_session_factory, upgrade_to_head
from app.models import SliceState, User
from app.render import figure_url, render_markdown

ADMIN_ROW_LIMIT = 200

templates = Jinja2Templates(directory=str(ROOT_DIR / "app" / "templates"))
# Версия стилей в URL (/static/style.css?v=...): браузер не берёт устаревший файл из кеша
# после обновления оболочки (так Edge показывал страницы по стилям до сессии 02).
templates.env.globals["static_v"] = hashlib.sha1(
    (ROOT_DIR / "app" / "static" / "style.css").read_bytes()).hexdigest()[:10]


def _ensure_dev_user(session_factory, settings: Settings) -> None:
    with session_factory() as db:
        if db.scalar(select(User).where(User.name == settings.dev_user_name)) is None:
            db.add(User(name=settings.dev_user_name))
            db.commit()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if not settings.is_development and settings.secret_key == DEV_SECRET_KEY:
        raise RuntimeError("Вне Development задайте TIMESLICES_SECRET_KEY")
    # Fail fast: битое содержание — отказ стартовать с понятным сообщением.
    course = load_course(settings.content_dir)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        upgrade_to_head(settings.database_url)
        if settings.is_development:
            _ensure_dev_user(session_factory, settings)
        yield
        engine.dispose()

    app = FastAPI(title="TimeSlices-AI", lifespan=lifespan)
    app.state.settings = settings
    app.state.course = course
    app.state.engine = engine
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key,
                       session_cookie="timeslices_session")
    app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "app" / "static")), name="static")

    def get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    def get_course() -> Course:
        return course

    def current_user(request: Request, db: Session = Depends(get_db)) -> User:
        """Один dev-пользователь, автовход через cookie-сессию (только Development)."""
        user_id = request.session.get("user_id")
        user = db.get(User, user_id) if user_id is not None else None
        if user is None:
            if not settings.is_development:
                raise HTTPException(status_code=401, detail="Вход есть только в Development")
            user = db.scalar(select(User).where(User.name == settings.dev_user_name))
            if user is None:
                raise HTTPException(status_code=500, detail="dev-пользователь не создан")
            request.session["user_id"] = user.id
        return user

    def get_slice_or_404(slice_id: str):
        s = course.get(slice_id)
        if s is None:
            raise HTTPException(status_code=404, detail=f"Срез '{slice_id}' не найден")
        return s

    @app.get("/", response_class=HTMLResponse)
    def course_map(request: Request, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
        states = progress.sync_states(db, course, user.id)
        items = [(s, progress.effective_state(course, states, s.id)) for s in course.slices]
        return templates.TemplateResponse(request, "index.html", {
            "course": course, "items": items, "user": user,
        })

    @app.get("/slices/{slice_id}")
    def slice_entry(slice_id: str, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
        s = get_slice_or_404(slice_id)
        states = progress.sync_states(db, course, user.id)
        if progress.effective_state(course, states, s.id) == SliceState.Unavailable:
            return _unavailable(request, s)
        n = min(max(states[s.id].last_page, 1), len(s.pages))
        return RedirectResponse(f"/slices/{s.id}/pages/{n}", status_code=303)

    @app.get("/slices/{slice_id}/pages/{n}", response_class=HTMLResponse)
    def slice_page(slice_id: str, n: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
        s = get_slice_or_404(slice_id)
        if not 1 <= n <= len(s.pages):
            raise HTTPException(status_code=404, detail=f"В срезе нет страницы {n}")
        states = progress.sync_states(db, course, user.id)
        if progress.effective_state(course, states, s.id) == SliceState.Unavailable:
            return _unavailable(request, s)
        row = states[s.id]
        progress.open_page(db, row, n)
        meta = s.pages[n - 1]
        page = read_page(meta)
        pinned = None
        if meta.pinned:
            pinned = {"src": figure_url(s.id, meta.pinned), "caption": s.captions[meta.pinned]}
        return templates.TemplateResponse(request, "page.html", {
            "slice": s, "n": n, "total": len(s.pages), "page": page,
            "page_type": meta.type, "body_html": render_markdown(page.body_md, s),
            "toc": s.toc(), "group_title": s.groups.get(meta.group) if meta.group else None,
            "pinned": pinned, "state": row.state,
        })

    @app.post("/slices/{slice_id}/done")
    def slice_done(slice_id: str, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
        s = get_slice_or_404(slice_id)
        states = progress.sync_states(db, course, user.id)
        if progress.effective_state(course, states, s.id) == SliceState.Unavailable:
            return _unavailable(request, s)
        if not progress.mark_done(db, course, user.id, states[s.id]):
            # Неоткрытый срез сначала надо открыть: Available → InProgress → Done.
            return RedirectResponse(f"/slices/{s.id}", status_code=303)
        return RedirectResponse("/", status_code=303)

    def _slice_file(slice_id: str, folder: str, path: str, request: Request, db: Session,
                    user: User):
        """Файл из папки folder среза — только для доступного среза (ADR 0004, 0005),
        с защитой от выхода за папку. Страницы и манифесты срезов наружу не отдаются."""
        s = get_slice_or_404(slice_id)
        states = progress.sync_states(db, course, user.id)
        if progress.effective_state(course, states, s.id) == SliceState.Unavailable:
            return _unavailable(request, s)
        base = (s.dir / folder).resolve()
        try:
            target = (base / path).resolve()
        except (ValueError, OSError):  # например, нулевой байт в пути
            raise HTTPException(status_code=404, detail="Файл не найден")
        if not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(status_code=404, detail="Файл не найден")
        return FileResponse(target)

    @app.get("/content/slices/{slice_id}/demos/{path:path}")
    def demo_file(slice_id: str, path: str, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
        """Статика демо (index.html, player.js, trace.json, gen/)."""
        return _slice_file(slice_id, "demos", path, request, db, user)

    @app.get("/content/slices/{slice_id}/figures/{path:path}")
    def figure_file(slice_id: str, path: str, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
        """Рисунки среза (figures/<file>): в тексте страниц и закреплённые."""
        return _slice_file(slice_id, "figures", path, request, db, user)

    def _unavailable(request: Request, s):
        i = course.index_of(s.id)
        prev = course.slices[i - 1] if i else None
        return templates.TemplateResponse(request, "unavailable.html",
                                          {"slice": s, "prev": prev}, status_code=403)

    def development_only() -> None:
        # Инспектор БД — инструмент разработки: вне Development его нет.
        if not settings.is_development:
            raise HTTPException(status_code=404)

    @app.get("/admin/db", response_class=HTMLResponse, dependencies=[Depends(development_only)])
    def admin_db(request: Request):
        insp = inspect(engine)
        tables = [(t, len(insp.get_columns(t))) for t in insp.get_table_names()]
        return templates.TemplateResponse(request, "admin_db.html", {"tables": tables})

    @app.get("/admin/db/{table}", response_class=HTMLResponse,
             dependencies=[Depends(development_only)])
    def admin_table(table: str, request: Request):
        insp = inspect(engine)
        # Имя таблицы берётся только из списка инспектора: никакого ввода SQL.
        if table not in insp.get_table_names():
            raise HTTPException(status_code=404, detail=f"Таблицы '{table}' нет")
        columns = [c["name"] for c in insp.get_columns(table)]
        quoted = engine.dialect.identifier_preparer.quote(table)
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT * FROM {quoted} LIMIT {ADMIN_ROW_LIMIT}")).all()
            total = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
            ddl = None
            if engine.dialect.name == "sqlite":
                ddl = conn.execute(
                    text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
                    {"n": table},
                ).scalar_one_or_none()
        return templates.TemplateResponse(request, "admin_table.html", {
            "table": table, "columns": columns, "rows": rows, "total": total,
            "limit": ADMIN_ROW_LIMIT, "ddl": ddl,
        })

    return app


app = create_app()
