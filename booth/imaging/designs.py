"""Card designs (the paper and artwork around the photos).

A design is colors plus optional artwork per template, looked up by convention:

    assets/designs/<design_id>/<template_id>_background.png   drawn under the photos
    assets/designs/<design_id>/<template_id>_overlay.png      drawn over the photos (transparent holes)

Artwork must match the template size (600x1800 portrait, 1800x600 landscape) and
is stretched if it doesn't. Add a Design to DESIGNS and drop the PNGs in to ship one.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

DESIGNS_DIR = Path(__file__).resolve().parents[2] / "assets" / "designs"


@dataclass(frozen=True)
class Design:
    id: str
    name: str
    tagline: str = ""
    paper: tuple[int, int, int] = (255, 255, 255)
    ink: tuple[int, int, int] = (30, 30, 30)

    def asset_path(self, template_id: str, kind: str) -> Path | None:
        path = DESIGNS_DIR / self.id / f"{template_id}_{kind}.png"
        return path if path.is_file() else None


@lru_cache(maxsize=32)
def load_asset(path: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    return img if img.size == size else img.resize(size, Image.LANCZOS)


DESIGNS: tuple[Design, ...] = (
    Design("plain_white", "Plain White", "Classic and clean"),
)

BY_ID = {d.id: d for d in DESIGNS}
DEFAULT = DESIGNS[0]
