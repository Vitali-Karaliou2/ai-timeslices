"""Приёмочные тесты оболочки (docs/acceptance.md, пункты 2–5, 7, 8)."""
import re

import pytest

from app.content import ContentError, load_course
from tests.conftest import write_course


def states(client) -> dict[str, str]:
    html = client.get("/").text
    return dict(re.findall(r'data-slice-id="([^"]+)" data-state="([^"]+)"', html))


def order(client) -> list[str]:
    return re.findall(r'data-slice-id="([^"]+)"', client.get("/").text)


# --- п. 2: карта курса ---------------------------------------------------------

def test_course_map_lists_slices_in_course_order(client):
    r = client.get("/")
    assert r.status_code == 200
    assert order(client) == ["ai-overview", "neuron-1943"]
    assert states(client) == {"ai-overview": "Available", "neuron-1943": "Unavailable"}


def test_golden_and_winter_are_distinguishable(client3):
    html = client3.get("/").text
    assert re.search(r'class="slice period-golden[^"]*" data-slice-id="s-one"', html)
    assert re.search(r'class="slice period-winter[^"]*" data-slice-id="s-two"', html)


# --- п. 3: недоступность ---------------------------------------------------------

def test_unavailable_slice_is_closed_by_direct_url(client):
    for url in ("/slices/neuron-1943", "/slices/neuron-1943/pages/1"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 403
        assert "Срез недоступен" in r.text
        assert "Идея" not in r.text  # заголовок первой страницы не показан
    assert client.post("/slices/neuron-1943/done", follow_redirects=False).status_code == 403
    assert states(client)["neuron-1943"] == "Unavailable"


def test_unknown_slice_and_page_are_404(client):
    assert client.get("/slices/no-such-slice").status_code == 404
    assert client.get("/slices/ai-overview/pages/0").status_code == 404
    assert client.get("/slices/ai-overview/pages/9").status_code == 404


# --- п. 4: навигация, Markdown, «Срез пройден» -------------------------------------

def test_page_navigation_and_markdown(client):
    r = client.get("/slices/ai-overview", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/slices/ai-overview/pages/1"

    p1 = client.get("/slices/ai-overview/pages/1").text
    assert "ЧЕРНОВИК" in p1
    assert 'class="next" href="/slices/ai-overview/pages/2"' in p1  # вперёд
    assert "← Назад" not in p1 and "Срез пройден" not in p1

    p2 = client.get("/slices/ai-overview/pages/2").text
    assert "<strong>Что это.</strong>" in p2                     # Markdown отрендерен
    assert 'class="prev" href="/slices/ai-overview/pages/1"' in p2
    assert "Срез пройден" not in p2

    p8 = client.get("/slices/ai-overview/pages/8").text
    assert "<ul>" in p8
    assert "Вперёд →" not in p8
    assert "Срез пройден" in p8                                  # только на последней

    assert states(client)["ai-overview"] == "InProgress"
    # /slices/{id} ведёт на последнюю открытую страницу
    assert client.get("/slices/ai-overview", follow_redirects=False).headers["location"] \
        == "/slices/ai-overview/pages/8"


def test_done_makes_next_slice_available(client):
    client.get("/slices/ai-overview/pages/2")
    r = client.post("/slices/ai-overview/done", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert states(client) == {"ai-overview": "Done", "neuron-1943": "Available"}
    r = client.get("/slices/neuron-1943/pages/1")
    assert r.status_code == 200 and "Идея" in r.text
    assert states(client)["neuron-1943"] == "InProgress"


# --- п. 5: повторное прохождение -----------------------------------------------

def test_reopening_done_slice_keeps_later_states(client3):
    client3.get("/slices/s-one/pages/1")
    client3.post("/slices/s-one/done")
    client3.get("/slices/s-two/pages/1")
    client3.post("/slices/s-two/done")
    client3.get("/slices/s-three/pages/1")
    before = {"s-one": "Done", "s-two": "Done", "s-three": "InProgress"}
    assert states(client3) == before

    # повторно открыть и снова «пройти» первый срез
    for n in (1, 2):
        assert client3.get(f"/slices/s-one/pages/{n}").status_code == 200
    client3.post("/slices/s-one/done")
    assert states(client3) == before


# --- п. 7: новый срез — это папка и строка в course.json --------------------------

def test_content_from_folder_without_code_changes(client3):
    assert order(client3) == ["s-one", "s-two", "s-three"]


def test_content_errors_fail_fast(tmp_path):
    content = write_course(tmp_path, [{"id": "s-one"}])
    (content / "slices" / "s-one" / "pages" / "01-p1.md").unlink()
    with pytest.raises(ContentError, match="не найден"):
        load_course(content)


def test_duplicate_slice_id_fails_fast(tmp_path):
    content = write_course(tmp_path, [{"id": "s-one"}])
    text = (content / "course.json").read_text(encoding="utf-8")
    (content / "course.json").write_text(
        text.replace('"slices": [', '"slices": [{"id": "s-one", "title": "x"}, '),
        encoding="utf-8")
    with pytest.raises(ContentError, match="дублирующийся id"):
        load_course(content)


# --- п. 8: /admin/db ---------------------------------------------------------------

def test_admin_db_lists_tables_and_rows(client):
    client.get("/")  # dev-пользователь и строки состояний
    r = client.get("/admin/db")
    assert r.status_code == 200
    assert "users" in r.text and "user_slice_state" in r.text
    r = client.get("/admin/db/user_slice_state")
    assert r.status_code == 200
    assert "ai-overview" in r.text and "CREATE TABLE" in r.text
    assert "dev" in client.get("/admin/db/users").text
    assert client.get("/admin/db/no_such_table").status_code == 404


# --- крайние случаи состояний --------------------------------------------------------

def test_done_requires_opened_slice(client):
    r = client.post("/slices/ai-overview/done", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/slices/ai-overview"
    assert states(client) == {"ai-overview": "Available", "neuron-1943": "Unavailable"}


def test_repeated_done_is_idempotent(client):
    client.get("/slices/ai-overview/pages/1")
    client.post("/slices/ai-overview/done")
    client.post("/slices/ai-overview/done")
    assert states(client) == {"ai-overview": "Done", "neuron-1943": "Available"}


def test_reordered_course_hides_slice_after_unfinished_one(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.conftest import make_settings

    content = write_course(tmp_path, [{"id": "s-one"}, {"id": "s-two"}])
    with TestClient(create_app(make_settings(tmp_path, content))) as c:
        c.get("/slices/s-one/pages/1")
        c.post("/slices/s-one/done")
    # автор ставит новый срез s-new перед пройденным s-one
    write_course(tmp_path / "v2", [{"id": "s-new"}, {"id": "s-one"}, {"id": "s-two"}])
    with TestClient(create_app(make_settings(tmp_path, tmp_path / "v2" / "content"))) as c:
        assert states(c) == {"s-new": "Available", "s-one": "Unavailable", "s-two": "Unavailable"}
        assert c.get("/slices/s-one/pages/1").status_code == 403
        c.get("/slices/s-new/pages/1")
        c.post("/slices/s-new/done")
        # пройденный ранее s-one снова виден как Done, s-two открыт
        assert states(c) == {"s-new": "Done", "s-one": "Done", "s-two": "Available"}


def test_create_app_fails_fast_on_broken_content(tmp_path):
    from app.main import create_app
    from tests.conftest import make_settings

    content = write_course(tmp_path, [{"id": "s-one"}])
    (content / "slices" / "s-one" / "slice.json").write_text("{", encoding="utf-8")
    with pytest.raises(ContentError, match="JSON"):
        create_app(make_settings(tmp_path, content))


# --- статика содержания: только демо, и только доступного среза ----------------------

def test_content_serves_only_demo_files_of_available_slice(client3):
    base = "/content/slices/s-one/demos/d1"
    assert client3.get(f"{base}/index.html").status_code == 200
    assert client3.get(f"{base}/trace.json").json() == {"points": [], "steps": []}
    assert client3.get(f"{base}/gen/numpy/train.py").status_code == 200
    # страницы и манифесты среза наружу не отдаются
    assert client3.get("/content/slices/s-one/pages/01-p1.md").status_code == 404
    assert client3.get("/content/slices/s-one/slice.json").status_code == 404
    assert client3.get("/content/course.json").status_code == 404
    assert client3.get(f"{base}/../../slice.json").status_code == 404
    assert client3.get("/content/slices/s-one/demos/%2E%2E/slice.json").status_code == 404
    # демо недоступного среза закрыто
    assert client3.get("/content/slices/s-two/demos/d1/index.html").status_code == 403


# --- /admin/db: только имена из инспектора, только Development ------------------------

def test_admin_db_rejects_unknown_table_names(client):
    for name in ("users; DROP TABLE users", "sqlite_master", "users--"):
        assert client.get(f"/admin/db/{name}").status_code == 404
    assert client.get("/admin/db/users").status_code == 200


def test_outside_development_admin_is_closed_and_secret_required(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.conftest import make_settings

    prod = make_settings(tmp_path).model_copy(update={"environment": "Production"})
    with pytest.raises(RuntimeError, match="TIMESLICES_SECRET_KEY"):
        create_app(prod)
    prod = prod.model_copy(update={"secret_key": "s3cret"})
    with TestClient(create_app(prod)) as c:
        assert c.get("/admin/db").status_code == 404
        assert c.get("/").status_code == 401


def test_alembic_ini_is_ascii():
    """Alembic читает alembic.ini в кодировке ОС (cp1252 на Windows): только ASCII."""
    from app.config import ROOT_DIR

    (ROOT_DIR / "alembic.ini").read_bytes().decode("ascii")
