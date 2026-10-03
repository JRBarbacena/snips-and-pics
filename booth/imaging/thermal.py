from __future__ import annotations

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from booth.imaging import fonts
from booth.share.qr import make_qr


def render_thermal(strip: Image.Image, width: int, qr_url: str | None = None) -> Image.Image:
    """1-bit, dithered, printer-width image of the strip, plus an optional QR footer."""
    img = strip.convert("L")
    if img.width > img.height:
        img = img.rotate(-90, expand=True)
    img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    # Thermal heads print dark; lift mids so faces don't turn to mud.
    img = ImageEnhance.Brightness(img).enhance(1.12)

    if qr_url:
        qr_size = width * 3 // 5
        footer = Image.new("L", (width, qr_size + 60), 255)
        qr = make_qr(qr_url).convert("L").resize((qr_size, qr_size), Image.NEAREST)
        footer.paste(qr, ((width - qr_size) // 2, 10))
        ImageDraw.Draw(footer).text(
            (width // 2, qr_size + 35), "Scan for your digital copy",
            font=fonts.bold(18), fill=0, anchor="mm",
        )
        joined = Image.new("L", (width, img.height + footer.height), 255)
        joined.paste(img, (0, 0))
        joined.paste(footer, (0, img.height))
        img = joined

    return img.convert("1")  # Floyd-Steinberg dithering
