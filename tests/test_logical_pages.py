"""Логическая страница из нескольких физических и закреплённый рисунок (ADR 0005)."""
import json
import re
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT_DIR
from app.content import ContentError, load_course, read_page
from app.main import create_app
from tests.conftest import make_settings, write_course

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
FIG1 = "/content/slices/ai-overview/figures/fig1_nested.png"
FIG2 = "/content/slices/ai-overview/figures/fig2_timeline.png"


def grouped_course(root, pages=3, groups=None, pinned=None, figures=True):
    """Курс из двух срезов; в s-one страницы pages, группы — groups[j] для страницы j."""
    content = write_course(root, [{"id": "s-one", "pages": pages}, {"id": "s-two"}])
    for sid in ("s-one", "s-two"):
        sdir = content / "slices" / sid
        (sdir / "figures").mkdir()
        (sdir / "figures" / "f1.png").write_bytes(PNG)
    sdir = content / "slices" / "s-one"
    path = sdir / "slice.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    groups = groups or ["g"] * pages
    d["groups"] = {g: {"title": f"Группа {g}"} for g in groups if g}
    if figures:
        d["figures"] = {"f1.png": {"caption": "Рисунок 1. Подпись"}}
    for j, p in enumerate(d["pages"]):
        if groups[j]:
            p["group"] = groups[j]
        if pinned and j in pinned:
            p["pinned"] = pinned[j]
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return content, path


def validate_script(path):
    r = subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "validate_content.py"),
                        str(path)], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout


# --- валидатор и загрузчик: fail fast ------------------------------------------------

def test_valid_grouped_slice_passes(tmp_path):
    content, path = grouped_course(tmp_path, pinned={1: "figures/f1.png"})
    load_course(content)
    assert validate_script(path)[0] == 0


def test_broken_group_is_rejected(tmp_path):
    content, path = grouped_course(tmp_path, groups=["g", None, "g"])
    with pytest.raises(ContentError, match="разорвана"):
        load_course(content)
    code, out = validate_script(path)
    assert code == 1 and "разорвана" in out


def test_missing_pinned_figure_is_rejected(tmp_path):
    content, path = grouped_course(tmp_path, pinned={0: "figures/no-such.png"})
    with pytest.raises(ContentError, match="не найден"):
        load_course(content)
    code, out = validate_script(path)
    assert code == 1 and "no-such.png" in out


def test_pinned_figure_needs_caption_and_safe_path(tmp_path):
    content, path = grouped_course(tmp_path, pinned={0: "figures/f1.png"}, figures=False)
    with pytest.raises(ContentError, match="нет подписи"):
        load_course(content)
    assert validate_script(path)[0] == 1
    content, path = grouped_course(tmp_path / "b", pinned={0: "figures/../slice.json"})
    with pytest.raises(ContentError, match="figures/<file>"):
        load_course(content)
    assert validate_script(path)[0] == 1


def test_missing_figure_in_page_text_is_rejected(tmp_path):
    content, path = grouped_course(tmp_path)
    page = content / "slices" / "s-one" / "pages" / "02-p2.md"
    page.write_text(page.read_text(encoding="utf-8") + "\n![Рис](figures/nope.png)\n",
                    encoding="utf-8")
    with pytest.raises(ContentError, match="nope.png"):
        load_course(content)
    code, out = validate_script(path)
    assert code == 1 and "nope.png" in out


# --- оболочка на реальном содержании: срез ai-overview ----------------------------------

def test_group_page_shows_pinned_figure(client):
    for n in (2, 3, 4, 5, 6):
        html = client.get(f"/slices/ai-overview/pages/{n}").text
        pinned = re.search(r'<aside class="pinned">(.*?)</aside>', html, re.S)
        assert pinned, n
        assert f'src="{FIG1}"' in pinned.group(1)
        assert "<figcaption>Рисунок 1. Области ИИ" in pinned.group(1)
        assert "О чём этот курс" in html  # заголовок группы
    assert client.get(FIG1).headers["content-type"] == "image/png"


def test_figures_in_text_without_pinning(client):
    p1 = client.get("/slices/ai-overview/pages/1").text
    assert 'class="pinned"' not in p1
    assert re.search(rf'<figure>\s*<img alt="Рисунок 1" src="{FIG1}"\s*/?>\s*'
                     r"<figcaption>Рисунок 1\. Области ИИ", p1)
    p7 = client.get("/slices/ai-overview/pages/7").text
    assert 'class="pinned"' not in p7
    assert f'src="{FIG2}"' in p7 and "<figcaption>Рисунок 2. Появление" in p7
    p8 = client.get("/slices/ai-overview/pages/8").text
    assert "<img" not in p8


def test_toc_shows_group_with_subitems(client):
    html = client.get("/slices/ai-overview/pages/3").text
    toc = re.search(r'<aside class="toc">(.*?)</aside>', html, re.S).group(1)
    group = re.search(r'<li class="toc-group current-group">\s*<a href="[^"]+">О чём этот курс</a>'
                      r"\s*<ol>(.*?)</ol>", toc, re.S)
    assert group
    subitems = re.findall(r'<li[^>]*><a href="/slices/ai-overview/pages/(\d)">([^<]+)</a>',
                          group.group(1))
    assert [int(n) for n, _ in subitems] == list(range(1, 9))
    assert subitems[2][1] == "2. Машинное обучение (Machine Learning, ML)"
    assert '<li class="current"><a href="/slices/ai-overview/pages/3">' in group.group(1)


def test_physical_navigation_and_done_on_last_page(client):
    for n in range(1, 9):
        html = client.get(f"/slices/ai-overview/pages/{n}").text
        assert f"Страница {n} из 8" in html
        assert ("Срез пройден" in html) == (n == 8)
        if n < 8:
            assert f'class="next" href="/slices/ai-overview/pages/{n + 1}"' in html
    r = client.post("/slices/ai-overview/done", follow_redirects=False)
    assert r.status_code == 303
    r = client.get("/slices/neuron-1943/pages/1")
    assert r.status_code == 200


# --- маршрут рисунков: правило доступа как у демо (ADR 0004) ------------------------------

def test_figures_of_unavailable_slice_are_403(tmp_path):
    content, _ = grouped_course(tmp_path)
    with TestClient(create_app(make_settings(tmp_path, content))) as c:
        assert c.get("/content/slices/s-one/figures/f1.png").content == PNG
        assert c.get("/content/slices/s-two/figures/f1.png").status_code == 403
        assert c.get("/content/slices/s-one/figures/missing.png").status_code == 404
        assert c.get("/content/slices/s-one/figures/../slice.json").status_code == 404
        assert c.get("/content/slices/s-one/figures/%2E%2E/slice.json").status_code == 404
        assert c.get("/content/slices/s-one/figures/f1%00.png").status_code == 404


# --- содержание дословно совпадает с источником ----------------------------------------

def test_page_11_text_matches_source_verbatim():
    """Сборка 8 физических страниц обратно (без «ЧЕРНОВИК:», рисунки → [[РИСУНОК N]]
    и подписи из slice.json) даёт текст источника 11.v2 дословно."""
    src = (ROOT_DIR / "docs" / "content-sources" / "11" / "11.v2.About_this_course.md")\
        .read_text(encoding="utf-8")
    src = src[src.index("-->") + 3:].strip()
    s = load_course(ROOT_DIR / "content").get("ai-overview")
    parts = ["# " + s.groups["about"]]
    for k, page in enumerate(s.pages):
        body = read_page(page).body_md.strip()
        assert body.startswith("ЧЕРНОВИК:\n\n")
        body = body.removeprefix("ЧЕРНОВИК:\n\n")
        for num, ref in (("1", "figures/fig1_nested.png"), ("2", "figures/fig2_timeline.png")):
            body = body.replace(f"![Рисунок {num}]({ref})",
                                f"[[РИСУНОК {num}]]\n\n*{s.captions[ref]}*")
        if k:
            parts.append("## " + page.title)
        parts.append(body)
    assert "\n\n".join(parts) == src


def test_validator_and_loader_use_same_figure_patterns():
    """scripts/validate_content.py автономен (не импортирует app) — регулярки дублируются."""
    import importlib.util

    import app.content as content
    spec = importlib.util.spec_from_file_location(
        "validate_content", ROOT_DIR / "scripts" / "validate_content.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    assert v.FIGURE_RE.pattern == content.FIGURE_RE.pattern
    assert v.FIGURE_REF_RE.pattern == content.FIGURE_REF_RE.pattern


def test_non_string_group_is_content_error(tmp_path):
    content, path = grouped_course(tmp_path)
    d = json.loads(path.read_text(encoding="utf-8"))
    d["pages"][0]["group"] = ["g"]
    path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ContentError, match="group"):
        load_course(content)
    assert validate_script(path)[0] == 1
