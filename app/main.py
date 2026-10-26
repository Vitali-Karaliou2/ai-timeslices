"""Оболочка TimeSlices-AI: маршруты FastAPI (аналог Razor Pages) и сборка приложения."""
from collections.abc import Iterator
from contextlib import asynccontextmanager

import markdown
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

ADMIN_ROW_LIMIT = 200

templates = Jinja2Templates(directory=str(ROOT_DIR / "app" / "templates"))


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
        page = read_page(s.pages[n - 1])
        body_html = markdown.markdown(page.body_md, extensions=["fenced_code", "tables"])
        toc = [p.title for p in s.pages]
        return templates.TemplateResponse(request, "page.html", {
            "slice": s, "n": n, "total": len(s.pages), "page": page,
            "page_type": s.pages[n - 1].type, "body_html": body_html, "toc": toc,
            "state": row.state,
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

    @app.get("/content/slices/{slice_id}/demos/{path:path}")
    def demo_file(slice_id: str, path: str, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
        """Статика демо (index.html, player.js, trace.json, gen/). Страницы и манифесты
        срезов наружу не отдаются; демо недоступного среза закрыто так же, как его страницы."""
        s = get_slice_or_404(slice_id)
        states = progress.sync_states(db, course, user.id)
        if progress.effective_state(course, states, s.id) == SliceState.Unavailable:
            return _unavailable(request, s)
        demos_dir = (s.dir / "demos").resolve()
        target = (demos_dir / path).resolve()
        if not target.is_relative_to(demos_dir) or not target.is_file():
            raise HTTPException(status_code=404, detail="Файл демо не найден")
        return FileResponse(target)

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
