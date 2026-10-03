from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"

INK = (34, 30, 42)
MUTED = (120, 112, 130)
LINE = (232, 226, 236)
WHITE = (255, 255, 255)
ACCENT = (240, 84, 110)
ACCENT_2 = (255, 154, 98)
BG_TOP = (255, 238, 232)
BG_BOTTOM = (234, 230, 255)
BOKEH = ((255, 170, 185), (255, 200, 150), (195, 185, 255), (165, 220, 230))
CONFETTI = (ACCENT, ACCENT_2, (110, 190, 255), (130, 215, 150), (255, 205, 80), (185, 145, 255))

_WEIGHTS = {
    "regular": "Poppins-Regular.ttf",
    "medium": "Poppins-Medium.ttf",
    "semibold": "Poppins-SemiBold.ttf",
    "bold": "Poppins-Bold.ttf",
}
_ICON_FONT = "MaterialIconsRound-Regular.otf"


@lru_cache(maxsize=64)
def font(size: int, weight: str = "regular") -> pygame.font.Font:
    try:
        return pygame.font.Font(FONTS / _WEIGHTS[weight], size)
    except (OSError, FileNotFoundError):
        log.warning("Bundled font missing, using system font")
        return pygame.font.SysFont("dejavusans,arial", size, bold=weight in ("semibold", "bold"))


@lru_cache(maxsize=512)
def render(s: str, size: int, color: tuple, weight: str = "regular") -> pygame.Surface:
    return font(size, weight).render(s, True, color)


def text(surf: pygame.Surface, s: str, size: int, color: tuple = INK, weight: str = "regular",
         alpha: int = 255, **pos) -> pygame.Rect:
    img = render(s, size, color, weight)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    rect = img.get_rect(**pos)
    surf.blit(img, rect)
    return rect


def wrap(s: str, size: int, width: int, weight: str = "regular") -> list[str]:
    lines: list[str] = []
    line = ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if font(size, weight).size(trial)[0] <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


@lru_cache(maxsize=1)
def _codepoints() -> dict[str, str]:
    path = FONTS / "MaterialIconsRound-Regular.codepoints"
    pairs = (line.split() for line in path.read_text().splitlines() if line.strip())
    return {name: chr(int(code, 16)) for name, code in pairs}


@lru_cache(maxsize=16)
def _icon_font(size: int) -> pygame.font.Font:
    return pygame.font.Font(FONTS / _ICON_FONT, size)


@lru_cache(maxsize=256)
def icon(name: str, size: int, color: tuple) -> pygame.Surface:
    """Material Icons Round glyph, e.g. icon("photo_camera", 24, WHITE)."""
    return _icon_font(size).render(_codepoints()[name], True, color)
