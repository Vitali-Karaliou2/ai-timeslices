"""Общие фикстуры: временная БД SQLite и (по желанию) временное содержание курса."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT_DIR, Settings
from app.main import create_app


def make_settings(tmp_path: Path, content_dir: Path | None = None) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        content_dir=content_dir or ROOT_DIR / "content",
    )


def write_course(root: Path, slices: list[dict]) -> Path:
    """Создаёт минимальное содержание: slices — [{id, period?, pages?}], по порядку курса."""
    content = root / "content"
    (content / "slices").mkdir(parents=True)
    (content / "course.json").write_text(json.dumps({
        "title": "Тестовый курс",
        "slices": [{"id": s["id"], "title": f"Срез {s['id']}"} for s in slices],
    }), encoding="utf-8")
    for s in slices:
        sdir = content / "slices" / s["id"]
        (sdir / "pages").mkdir(parents=True)
        pages = []
        for j in range(1, s.get("pages", 2) + 1):
            f = f"pages/{j:02d}-p{j}.md"
            (sdir / f).write_text(f"---\ntitle: Страница {j}\n---\n\nЧЕРНОВИК: текст {j}\n",
                                  encoding="utf-8")
            pages.append({"id": f"p{j}", "type": "idea", "file": f})
        (sdir / "slice.json").write_text(json.dumps({
            "id": s["id"], "title": f"Срез {s['id']}", "yearFrom": 1950, "yearTo": 1960,
            "track": "genai", "period": s.get("period", "golden"),
            "summary": "ЧЕРНОВИК: тест", "pages": pages, "status": "draft",
        }), encoding="utf-8")
        if s.get("demo"):
            ddir = sdir / "demos" / "d1"
            (ddir / "gen" / "numpy").mkdir(parents=True)
            (ddir / "index.html").write_text("<p>плеер</p>", encoding="utf-8")
            (ddir / "trace.json").write_text('{"points": [], "steps": []}', encoding="utf-8")
            (ddir / "gen" / "numpy" / "train.py").write_text("# генератор\n", encoding="utf-8")
            (ddir / "demo.json").write_text(json.dumps({
                "id": "d1", "title": "Демо", "entry": "index.html", "trace": "trace.json",
                "gen": {"numpy": "gen/numpy/train.py"},
            }), encoding="utf-8")
    return content


@pytest.fixture
def client(tmp_path):
    """Клиент на реальном содержании репозитория (content/) и временной БД."""
    with TestClient(create_app(make_settings(tmp_path))) as c:
        yield c


@pytest.fixture
def client3(tmp_path):
    """Клиент на временном курсе из трёх срезов: golden, winter, golden."""
    content = write_course(tmp_path, [
        {"id": "s-one", "demo": True}, {"id": "s-two", "period": "winter", "demo": True},
        {"id": "s-three"},
    ])
    with TestClient(create_app(make_settings(tmp_path, content))) as c:
        yield c
