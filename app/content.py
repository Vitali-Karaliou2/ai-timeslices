"""Загрузка содержания курса: content/course.json и slice.json срезов.

Оболочка читает только манифесты (course.json, slice.json, demo.json) и файлы страниц.
Любая ошибка содержания — ContentError с понятным сообщением; приложение не стартует
(fail fast). Схема — docs/spec/content-schema.md.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TRACKS = {"genai", "xai"}
PERIODS = {"golden", "winter"}
STATUSES = {"draft", "approved"}
PAGE_TYPES = {
    "overview", "winter-overview", "idea", "math", "library", "code-example",
    "demo", "history", "summary", "questions", "assignments",
}


class ContentError(Exception):
    """Содержание курса не соответствует схеме."""


@dataclass(frozen=True)
class Page:
    id: str
    type: str
    path: Path
    title: str  # из front-matter; читается при загрузке для оглавления


@dataclass(frozen=True)
class Slice:
    id: str
    title: str
    year_from: int
    year_to: int
    track: str
    period: str
    summary: str
    status: str
    pages: list[Page]
    dir: Path


@dataclass(frozen=True)
class Course:
    title: str
    slices: list[Slice]
    _by_id: dict[str, int] = field(default_factory=dict, repr=False)

    def index_of(self, slice_id: str) -> int | None:
        return self._by_id.get(slice_id)

    def get(self, slice_id: str) -> Slice | None:
        i = self.index_of(slice_id)
        return None if i is None else self.slices[i]


@dataclass(frozen=True)
class RenderedPage:
    title: str
    meta: dict[str, str]
    body_md: str


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise ContentError(f"{path}: файл не найден")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContentError(f"{path}: не читается как JSON: {e}") from e


def _require(obj: object, keys: list[str], ctx: str) -> dict:
    if not isinstance(obj, dict):
        raise ContentError(f"{ctx}: ожидается JSON-объект")
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ContentError(f"{ctx}: нет обязательных полей {missing}")
    return obj


def _check_id(value: object, ctx: str) -> str:
    if not isinstance(value, str) or not ID_RE.match(value):
        raise ContentError(f"{ctx}: id '{value}' должен быть kebab-case (a-z, 0-9, -)")
    return value


def _load_demos(slice_dir: Path) -> None:
    """Проверяет демо-манифесты среза (сами демо оболочка не исполняет)."""
    demos_dir = slice_dir / "demos"
    if not demos_dir.is_dir():
        return
    for demo_dir in sorted(p for p in demos_dir.iterdir() if p.is_dir()):
        path = demo_dir / "demo.json"
        d = _require(_read_json(path), ["id", "title", "entry", "trace", "gen"], str(path))
        if _check_id(d["id"], str(path)) != demo_dir.name:
            raise ContentError(f"{path}: id '{d['id']}' не совпадает с именем папки")
        for k in ("entry", "trace"):
            if not (demo_dir / d[k]).is_file():
                raise ContentError(f"{path}: '{k}' указывает на несуществующий файл '{d[k]}'")
        gen = d["gen"]
        if not isinstance(gen, dict) or not gen or not set(gen) <= {"numpy", "torch"}:
            raise ContentError(f"{path}: 'gen' — объект с ключами numpy и/или torch")
        for lib, f in gen.items():
            if not (demo_dir / f).is_file():
                raise ContentError(f"{path}: gen.{lib} указывает на несуществующий файл '{f}'")


def _load_slice(content_dir: Path, slice_id: str) -> Slice:
    slice_dir = content_dir / "slices" / slice_id
    path = slice_dir / "slice.json"
    ctx = str(path)
    d = _require(
        _read_json(path),
        ["id", "title", "yearFrom", "yearTo", "track", "period", "summary", "pages", "status"],
        ctx,
    )
    if d["id"] != slice_id:
        raise ContentError(f"{ctx}: id '{d['id']}' не совпадает с id в course.json '{slice_id}'")
    for k in ("yearFrom", "yearTo"):
        if not isinstance(d[k], int):
            raise ContentError(f"{ctx}: {k} должен быть целым числом")
    if d["yearFrom"] > d["yearTo"]:
        raise ContentError(f"{ctx}: yearFrom > yearTo")
    if d["track"] not in TRACKS:
        raise ContentError(f"{ctx}: track '{d['track']}' не из {sorted(TRACKS)}")
    if d["period"] not in PERIODS:
        raise ContentError(f"{ctx}: period '{d['period']}' не из {sorted(PERIODS)}")
    if d["status"] not in STATUSES:
        raise ContentError(f"{ctx}: status '{d['status']}' не из {sorted(STATUSES)}")
    if not isinstance(d["pages"], list) or not d["pages"]:
        raise ContentError(f"{ctx}: 'pages' — непустой упорядоченный список страниц")

    pages: list[Page] = []
    seen: set[str] = set()
    for i, p in enumerate(d["pages"]):
        pctx = f"{ctx}: pages[{i}]"
        p = _require(p, ["id", "type", "file"], pctx)
        page_id = _check_id(p["id"], pctx)
        if page_id in seen:
            raise ContentError(f"{pctx}: дублирующийся id страницы '{page_id}'")
        seen.add(page_id)
        if p["type"] not in PAGE_TYPES:
            raise ContentError(f"{pctx}: type '{p['type']}' не входит в типологию страниц")
        page_path = slice_dir / p["file"]
        if not page_path.is_file():
            raise ContentError(f"{pctx}: файл страницы '{p['file']}' не найден")
        title = parse_page(page_path.read_text(encoding="utf-8")).meta.get("title")
        if not title:
            raise ContentError(f"{pctx}: в front-matter страницы '{p['file']}' нет title")
        pages.append(Page(id=page_id, type=p["type"], path=page_path, title=title))

    _load_demos(slice_dir)
    return Slice(
        id=slice_id, title=d["title"], year_from=d["yearFrom"], year_to=d["yearTo"],
        track=d["track"], period=d["period"], summary=d["summary"], status=d["status"],
        pages=pages, dir=slice_dir,
    )


def load_course(content_dir: Path) -> Course:
    path = content_dir / "course.json"
    d = _require(_read_json(path), ["title", "slices"], str(path))
    if not isinstance(d["slices"], list) or not d["slices"]:
        raise ContentError(f"{path}: 'slices' — непустой упорядоченный список срезов")
    slices: list[Slice] = []
    by_id: dict[str, int] = {}
    for i, s in enumerate(d["slices"]):
        sctx = f"{path}: slices[{i}]"
        s = _require(s, ["id", "title"], sctx)
        slice_id = _check_id(s["id"], sctx)
        if slice_id in by_id:
            raise ContentError(f"{sctx}: дублирующийся id среза '{slice_id}'")
        by_id[slice_id] = i
        slices.append(_load_slice(content_dir, slice_id))
    return Course(title=d["title"], slices=slices, _by_id=by_id)


def read_page(page: Page) -> RenderedPage:
    return parse_page(page.path.read_text(encoding="utf-8"), default_title=page.title)


def parse_page(text: str, default_title: str = "") -> RenderedPage:
    """Разбирает Markdown-страницу с front-matter (`---` / `key: value` / `---`).

    Front-matter у страниц плоский (title, demo), поэтому полный YAML-парсер не нужен.
    """
    meta: dict[str, str] = {}
    body = text
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for line in lines[1:j]:
                    key, sep, value = line.partition(":")
                    if sep:
                        meta[key.strip()] = value.strip().strip("\"'")
                body = "\n".join(lines[j + 1:])
                break
    return RenderedPage(title=meta.get("title", default_title), meta=meta, body_md=body)
