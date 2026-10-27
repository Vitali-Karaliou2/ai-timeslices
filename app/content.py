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
# Рисунок среза: файл прямо в папке figures/ (без подпапок) — так путь безопасен сам по себе.
FIGURE_RE = re.compile(r"^figures/[A-Za-z0-9][A-Za-z0-9._-]*$")
# Ссылка на рисунок в тексте страницы — обычная Markdown-картинка с путём figures/<file>.
FIGURE_REF_RE = re.compile(r"!\[[^\]]*\]\(\s*<?(figures/[^)\s>]*)")
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
    group: str | None = None   # id логической страницы (ADR 0005)
    pinned: str | None = None  # закреплённый рисунок: "figures/<file>"


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
    groups: dict[str, str] = field(default_factory=dict)    # id группы → заголовок
    captions: dict[str, str] = field(default_factory=dict)  # "figures/<file>" → подпись

    def toc(self) -> list["TocItem"]:
        """Оглавление: страница без группы — пункт; группа — один пункт с подпунктами.
        Номера n — физические (1-based), как в URL /slices/{id}/pages/{n}."""
        items: list[TocItem] = []
        for n, p in enumerate(self.pages, start=1):
            if p.group is None:
                items.append(TocItem(title=p.title, n=n))
            elif items and items[-1].group == p.group:
                items[-1].children.append(TocItem(title=p.title, n=n))
            else:
                items.append(TocItem(title=self.groups[p.group], n=n, group=p.group,
                                     children=[TocItem(title=p.title, n=n)]))
        return items


@dataclass
class TocItem:
    title: str
    n: int  # физическая страница, на которую ведёт пункт
    group: str | None = None
    children: list["TocItem"] = field(default_factory=list)


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


def _check_figure(slice_dir: Path, ref: object, ctx: str) -> str:
    if not isinstance(ref, str) or not FIGURE_RE.match(ref):
        raise ContentError(f"{ctx}: рисунок '{ref}' — ожидается путь вида figures/<file>")
    if not (slice_dir / ref).is_file():
        raise ContentError(f"{ctx}: рисунок '{ref}' не найден в папке среза")
    return ref


def _load_captions(slice_dir: Path, d: dict, ctx: str) -> dict[str, str]:
    """slice.json.figures: {"<file>": {"caption": "..."}} — подписи рисунков из figures/."""
    figures = d.get("figures", {})
    if not isinstance(figures, dict):
        raise ContentError(f"{ctx}: 'figures' — объект {{\"<file>\": {{\"caption\": ...}}}}")
    captions: dict[str, str] = {}
    for name, entry in figures.items():
        ref = _check_figure(slice_dir, f"figures/{name}", f"{ctx}: figures")
        entry = _require(entry, ["caption"], f"{ctx}: figures.{name}")
        if not isinstance(entry["caption"], str) or not entry["caption"].strip():
            raise ContentError(f"{ctx}: figures.{name}.caption — непустая строка")
        captions[ref] = entry["caption"]
    return captions


def _load_groups(d: dict, ctx: str) -> dict[str, str]:
    groups = d.get("groups", {})
    if not isinstance(groups, dict):
        raise ContentError(f"{ctx}: 'groups' — объект {{\"<group-id>\": {{\"title\": ...}}}}")
    titles: dict[str, str] = {}
    for gid, g in groups.items():
        _check_id(gid, f"{ctx}: groups")
        g = _require(g, ["title"], f"{ctx}: groups.{gid}")
        if not isinstance(g["title"], str) or not g["title"].strip():
            raise ContentError(f"{ctx}: groups.{gid}.title — непустая строка")
        titles[gid] = g["title"]
    return titles


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

    groups = _load_groups(d, ctx)
    captions = _load_captions(slice_dir, d, ctx)
    pages: list[Page] = []
    seen: set[str] = set()
    closed_groups: set[str] = set()  # группы, которые уже закончились: повтор = разрыв
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
        parsed = parse_page(page_path.read_text(encoding="utf-8"))
        title = parsed.meta.get("title")
        if not title:
            raise ContentError(f"{pctx}: в front-matter страницы '{p['file']}' нет title")
        for ref in FIGURE_REF_RE.findall(parsed.body_md):
            _check_figure(slice_dir, ref, f"{pctx}: текст страницы '{p['file']}'")

        group = p.get("group")
        if group is not None:
            if not isinstance(group, str):
                raise ContentError(f"{pctx}: group — строка (id группы)")
            if group not in groups:
                raise ContentError(f"{pctx}: группа '{group}' не описана в 'groups'")
            if group in closed_groups:
                raise ContentError(
                    f"{pctx}: группа '{group}' разорвана — страницы одной группы идут подряд")
        prev_group = pages[-1].group if pages else None
        if prev_group is not None and prev_group != group:
            closed_groups.add(prev_group)

        pinned = p.get("pinned")
        if pinned is not None:
            _check_figure(slice_dir, pinned, f"{pctx}: pinned")
            if pinned not in captions:
                raise ContentError(
                    f"{pctx}: у закреплённого рисунка '{pinned}' нет подписи в 'figures'")
        pages.append(Page(id=page_id, type=p["type"], path=page_path, title=title,
                          group=group, pinned=pinned))

    unused = set(groups) - {pg.group for pg in pages}
    if unused:
        raise ContentError(f"{ctx}: группы {sorted(unused)} описаны в 'groups', но ни одна "
                           "страница к ним не относится")

    _load_demos(slice_dir)
    return Slice(
        id=slice_id, title=d["title"], year_from=d["yearFrom"], year_to=d["yearTo"],
        track=d["track"], period=d["period"], summary=d["summary"], status=d["status"],
        pages=pages, dir=slice_dir, groups=groups, captions=captions,
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
