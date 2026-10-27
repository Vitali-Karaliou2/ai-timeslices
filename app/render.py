"""Рендеринг Markdown страницы в HTML с рисунками среза (ADR 0005).

В тексте страницы рисунок — обычная Markdown-картинка с путём внутри среза:
`![Рисунок 1](figures/fig1_nested.png)`. Текст не знает URL оболочки: путь
`figures/<file>` переписывается здесь на маршрут `/content/slices/{id}/figures/<file>`.
Картинка, стоящая отдельным абзацем, становится `<figure>` с подписью из
`slice.json.figures` (если подпись там есть).
Рисунки рисуются с двойной плотностью пикселей (dpi 200 при кегле подписей ~11 pt),
поэтому естественный размер на экране — половина размера PNG в пикселях: он задаётся
атрибутами width/height, а CSS только ограничивает ширину колонкой.
"""
import struct
import xml.etree.ElementTree as etree
from pathlib import Path

import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from app.content import FIGURE_RE, Slice


def png_display_size(path: Path) -> tuple[int, int] | None:
    """Размер PNG для показа (половина пикселей, см. выше); None — не PNG или не читается."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return max(1, w // 2), max(1, h // 2)


def figure_url(slice_id: str, ref: str) -> str:
    """"figures/<file>" → URL маршрута рисунков среза."""
    return f"/content/slices/{slice_id}/{ref}"


class _FigureProcessor(Treeprocessor):
    def __init__(self, md, s: Slice):
        super().__init__(md)
        self.slice = s

    def run(self, root: etree.Element) -> None:
        for parent in root.iter():
            for child in parent:
                if child.tag == "img":
                    self._rewrite(child)
            # Абзац из одной картинки → <figure> с подписью.
            if (parent.tag == "p" and len(parent) == 1 and parent[0].tag == "img"
                    and not (parent.text or "").strip() and not (parent[0].tail or "").strip()):
                ref = parent[0].get("data-figure")
                if ref is not None:
                    parent.tag = "figure"
                    caption = self.slice.captions.get(ref)
                    if caption:
                        etree.SubElement(parent, "figcaption").text = caption
        for img in root.iter("img"):
            img.attrib.pop("data-figure", None)

    def _rewrite(self, img: etree.Element) -> None:
        ref = img.get("src", "")
        if FIGURE_RE.match(ref):
            img.set("src", figure_url(self.slice.id, ref))
            img.set("data-figure", ref)
            size = png_display_size(self.slice.dir / ref)
            if size:
                img.set("width", str(size[0]))
                img.set("height", str(size[1]))


class _FigureExtension(Extension):
    def __init__(self, s: Slice):
        super().__init__()
        self.slice = s

    def extendMarkdown(self, md):
        md.treeprocessors.register(_FigureProcessor(md, self.slice), "slice_figures", 5)


def render_markdown(body_md: str, s: Slice) -> str:
    return markdown.markdown(body_md, extensions=["fenced_code", "tables", _FigureExtension(s)])
