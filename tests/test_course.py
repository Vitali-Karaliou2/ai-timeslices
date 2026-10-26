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
    assert client.get("/slices/ai-overview/pages/3").status_code == 404


# --- п. 4: навигация, Markdown, «Срез пройден» -------------------------------------

def test_page_navigation_and_markdown(client):
    r = client.get("/slices/ai-overview", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/slices/ai-overview/pages/1"

    p1 = client.get("/slices/ai-overview/pages/1").text
    assert "ЧЕРНОВИК" in p1
    assert "<strong>Трек</strong>" in p1                        # Markdown отрендерен
    assert 'href="/slices/ai-overview/pages/2"' in p1           # вперёд и оглавление
    assert "← Назад" not in p1 and "Срез пройден" not in p1

    p2 = client.get("/slices/ai-overview/pages/2").text
    assert "<table>" in p2
    assert 'class="prev" href="/slices/ai-overview/pages/1"' in p2
    assert "Вперёд →" not in p2
    assert "Срез пройден" in p2                                  # только на последней

    assert states(client)["ai-overview"] == "InProgress"
    # /slices/{id} ведёт на последнюю открытую страницу
    assert client.get("/slices/ai-overview", follow_redirects=False).headers["location"] \
        == "/slices/ai-overview/pages/2"


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
