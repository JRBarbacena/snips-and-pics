from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from booth.imaging.export import print_sheet_4x6

log = logging.getLogger(__name__)

SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{8,16}$")
STRIP = "strip.jpg"
SHEET = "print_4x6.jpg"


@dataclass
class Session:
    id: str
    dir: Path

    def path(self, name: str) -> Path:
        return self.dir / name

    def photo_names(self) -> list[str]:
        return sorted(p.name for p in self.dir.glob("photo_*.jpg"))


class SessionStore:
    def __init__(self, root: Path, keep: int):
        self.root = root
        self.keep = keep
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self) -> Session:
        sid = secrets.token_urlsafe(8)[:10]
        d = self.root / sid
        d.mkdir(parents=True)
        return Session(sid, d)

    def get(self, sid: str) -> Session | None:
        if not SESSION_ID.match(sid):
            return None
        d = self.root / sid
        return Session(sid, d) if d.is_dir() else None

    def save(self, session: Session, photos: list[Image.Image], strip: Image.Image) -> None:
        for i, photo in enumerate(photos, 1):
            photo.save(session.path(f"photo_{i}.jpg"), quality=92)
        strip.save(session.path(STRIP), quality=95, dpi=(300, 300))
        print_sheet_4x6(strip).save(session.path(SHEET), quality=95, dpi=(300, 300))

    def cleanup(self) -> None:
        dirs = sorted((d for d in self.root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
        for d in dirs[: max(0, len(dirs) - self.keep)]:
            shutil.rmtree(d, ignore_errors=True)


def find_removable_media(roots: list[str]) -> list[Path]:
    """Mounted card readers / USB drives, e.g. /media/<user>/<label> on Pi OS."""
    found: list[Path] = []
    for root in map(Path, roots):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            candidates = [child] + ([c for c in child.iterdir() if c.is_dir()] if child.is_dir() else [])
            found.extend(c for c in candidates if os.path.ismount(c))
    return found


def _next_dcf_name(folder: Path) -> str:
    numbers = [int(m.group(1)) for p in folder.glob("SNIP*.JPG") if (m := re.match(r"SNIP(\d{4})", p.name))]
    return f"SNIP{(max(numbers, default=0) + 1) % 10000:04d}.JPG"


@dataclass
class ExportResult:
    cards: list[Path]
    downloads: Path | None = None


def export_session(session: Session, export_dir: Path, media_roots: list[str],
                   downloads_dir: Path | None = None) -> ExportResult:
    """Copy the 4x6 print sheet locally and onto every mounted card.

    Cards get a camera-style DCIM/100SNIPS/SNIP0001.JPG layout, which photo
    printers like the Canon SELPHY expect when browsing a card. Without a card,
    the strip, print sheet and photos go to a folder under downloads_dir.
    """
    src = session.path(SHEET)
    stamp = time.strftime('%Y%m%d_%H%M%S')

    export_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, export_dir / f"{stamp}_{session.id}_4x6.jpg")

    result = ExportResult(_copy_to_cards(src, media_roots))
    if not result.cards and downloads_dir:
        folder = downloads_dir / f"{stamp}_{session.id}"
        folder.mkdir(parents=True, exist_ok=True)
        for name in [STRIP, SHEET, *session.photo_names()]:
            shutil.copy2(session.path(name), folder / name)
        result.downloads = folder
    if hasattr(os, "sync"):
        os.sync()  # guests may pull the card right after the toast
    return result


def _copy_to_cards(src: Path, media_roots: list[str]) -> list[Path]:
    written: list[Path] = []
    for mount in find_removable_media(media_roots):
        folder = mount / "DCIM" / "100SNIPS"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / _next_dcf_name(folder)
            shutil.copy2(src, dest)
            written.append(dest)
        except OSError as exc:
            log.warning("Could not write to %s: %s", mount, exc)
    return written
