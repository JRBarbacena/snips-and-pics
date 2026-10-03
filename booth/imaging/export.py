from __future__ import annotations

from PIL import Image

from booth.imaging.templates import PAPER


def print_sheet_4x6(strip: Image.Image) -> Image.Image:
    """Two copies of the strip on one 4x6 sheet at 300 dpi; cut down the middle."""
    w, h = strip.size
    if w < h:
        sheet = Image.new("RGB", (w * 2, h), PAPER)
        sheet.paste(strip, (0, 0))
        sheet.paste(strip, (w, 0))
    else:
        sheet = Image.new("RGB", (w, h * 2), PAPER)
        sheet.paste(strip, (0, 0))
        sheet.paste(strip, (0, h))
    return sheet
