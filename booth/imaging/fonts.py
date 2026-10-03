from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont

_CANDIDATES = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf")


@lru_cache(maxsize=32)
def bold(size: int) -> ImageFont.FreeTypeFont:
    for name in _CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)
