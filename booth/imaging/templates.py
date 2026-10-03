"""Strip layouts at 300 dpi.

Portrait strips are 2x6 in (600x1800); two fit side by side on 4x6 photo paper.
The landscape strip is 6x2 in (1800x600); two stack on 6x4 paper.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageOps

from booth.imaging import fonts
from booth.imaging.designs import DEFAULT as DEFAULT_DESIGN
from booth.imaging.designs import Design, load_asset

PAPER = (255, 255, 255)
PLACEHOLDER = (210, 210, 210)


@dataclass(frozen=True)
class Slot:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class TextItem:
    kind: str  # "brand" | "date" | "brand_date"
    x: int     # center
    y: int     # center
    size: int
    rotate: int = 0


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    size: tuple[int, int]
    slots: tuple[Slot, ...]
    texts: tuple[TextItem, ...]

    @property
    def photo_count(self) -> int:
        return len(self.slots)

    @property
    def landscape(self) -> bool:
        return self.size[0] > self.size[1]


def _stack(x: int, w: int, h: int, top: int, gap: int, n: int) -> tuple[Slot, ...]:
    return tuple(Slot(x, top + i * (h + gap), w, h) for i in range(n))


TEMPLATES: tuple[Template, ...] = (
    Template(
        id="classic3",
        name="Classic 3",
        size=(600, 1800),
        slots=_stack(x=40, w=520, h=390, top=100, gap=20, n=3),
        texts=(TextItem("brand", 300, 55, 30), TextItem("date", 300, 1745, 24)),
    ),
    Template(
        id="classic4",
        name="Classic 4",
        size=(600, 1800),
        slots=_stack(x=40, w=520, h=390, top=100, gap=20, n=4),
        texts=(TextItem("brand", 300, 55, 30), TextItem("date", 300, 1760, 24)),
    ),
    Template(
        id="fullbleed3",
        name="Full Bleed",
        size=(600, 1800),
        slots=_stack(x=0, w=600, h=450, top=180, gap=15, n=3),
        texts=(TextItem("brand", 300, 1660, 32), TextItem("date", 300, 1715, 24)),
    ),
    Template(
        id="landscape3",
        name="Landscape",
        size=(1800, 600),
        slots=tuple(Slot(40 + i * 550, 105, 520, 390) for i in range(3)),
        texts=(TextItem("brand_date", 1730, 300, 24, rotate=90),),
    ),
)

BY_ID = {t.id: t for t in TEMPLATES}


def _text_for(kind: str, brand: str, date: str) -> str:
    return {"brand": brand, "date": date, "brand_date": f"{brand}  \u00b7  {date}"}[kind]


def _draw_text(canvas: Image.Image, item: TextItem, text: str, ink: tuple) -> None:
    font = fonts.bold(item.size)
    if item.rotate == 0:
        ImageDraw.Draw(canvas).text((item.x, item.y), text, font=font, fill=ink, anchor="mm")
        return
    left, top, right, bottom = font.getbbox(text)
    layer = Image.new("RGBA", (right - left + 8, bottom - top + 8), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((4 - left, 4 - top), text, font=font, fill=ink)
    layer = layer.rotate(item.rotate, expand=True)
    canvas.paste(layer, (item.x - layer.width // 2, item.y - layer.height // 2), layer)


def compose(
    template: Template,
    photos: list[Image.Image] | None,
    brand: str,
    date: str,
    design: Design = DEFAULT_DESIGN,
) -> Image.Image:
    """Lay photos into the template. photos=None renders gray placeholders."""
    canvas = Image.new("RGB", template.size, design.paper)
    if background := design.asset_path(template.id, "background"):
        bg = load_asset(background, template.size)
        canvas.paste(bg, (0, 0), bg)
    draw = ImageDraw.Draw(canvas)
    for i, slot in enumerate(template.slots):
        if photos is None:
            draw.rectangle((slot.x, slot.y, slot.x + slot.w - 1, slot.y + slot.h - 1), fill=PLACEHOLDER)
            continue
        fitted = ImageOps.fit(photos[i].convert("RGB"), (slot.w, slot.h), Image.LANCZOS)
        canvas.paste(fitted, (slot.x, slot.y))
    if overlay := design.asset_path(template.id, "overlay"):
        ov = load_asset(overlay, template.size)
        canvas.paste(ov, (0, 0), ov)
    for item in template.texts:
        _draw_text(canvas, item, _text_for(item.kind, brand, date), design.ink)
    return canvas
