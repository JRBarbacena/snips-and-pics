from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image

from booth.config import PrinterConfig

log = logging.getLogger(__name__)


class PrinterError(Exception):
    pass


class Printer:
    name = "none"

    def print_image(self, img: Image.Image) -> None:
        raise PrinterError("No printer configured")


class ThermalPrinter(Printer):
    """58mm ESC/POS printer over USB. Connects per job so unplugging is harmless."""

    name = "thermal"

    def __init__(self, cfg: PrinterConfig):
        self.cfg = cfg

    def print_image(self, img: Image.Image) -> None:
        try:
            from escpos.printer import Usb

            p = Usb(self.cfg.usb_vendor_id, self.cfg.usb_product_id)
        except Exception as exc:
            raise PrinterError(f"Printer not found: {exc}") from exc
        try:
            p.image(img, impl="bitImageRaster")
            p.text("\n" * self.cfg.feed_lines)
        except Exception as exc:
            raise PrinterError(f"Print failed: {exc}") from exc
        finally:
            p.close()


class FilePrinter(Printer):
    """Desktop stand-in: writes what the thermal printer would print."""

    name = "file"

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir

    def print_image(self, img: Image.Image) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"print_{time.strftime('%Y%m%d_%H%M%S')}.png"
        img.save(path)
        log.info("Print preview saved to %s", path)


def create_printer(cfg: PrinterConfig, data_dir: Path) -> Printer:
    backend = cfg.backend
    if backend == "thermal":
        return ThermalPrinter(cfg)
    if backend == "file":
        return FilePrinter(data_dir / "print_preview")
    return Printer()
