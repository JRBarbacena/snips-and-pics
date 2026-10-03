from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ScreenConfig:
    width: int = 320   # 3.5" TFT mounted portrait on the side of the box
    height: int = 480
    fullscreen: bool = False
    fps: int = 30
    effects: bool = True  # animations, transitions, confetti; turn off on slow boards


@dataclass
class CameraConfig:
    backend: str = "auto"  # auto | picamera | opencv | mock
    index: int = 0
    width: int = 1280
    height: int = 960
    # Mirror image, like a phone selfie camera. Applies to the preview and the saved photos.
    mirror: bool = True


@dataclass
class CaptureConfig:
    countdown_seconds: int = 3
    interval_seconds: float = 2.5
    hold_seconds: float = 1.5
    idle_timeout_seconds: int = 90


@dataclass
class GpioConfig:
    shutter_pin: int = 17
    back_pin: int | None = 27
    led_pin: int | None = 22
    buzzer_pin: int | None = 23


@dataclass
class PrinterConfig:
    backend: str = "none"  # none | thermal | file (file = save preview PNGs, for testing)
    usb_vendor_id: int = 0x0416
    usb_product_id: int = 0x5011
    paper_width_px: int = 384
    feed_lines: int = 4


@dataclass
class ShareConfig:
    enabled: bool = True
    port: int = 8000
    # Leave empty to auto-detect the LAN address. Set it when running a hotspot
    # (NetworkManager shared mode uses http://10.42.0.1:8000) or a public URL.
    base_url: str = ""
    # True only when base_url is reachable from anywhere (cloud). Printed QR codes
    # are useless for hotspot links once the guest walks away from the booth.
    public: bool = False
    hotspot_ssid: str = ""
    hotspot_password: str = ""


@dataclass
class StorageConfig:
    data_dir: str = "data"
    export_dir: str = "exports"
    removable_media_roots: list[str] = field(default_factory=lambda: ["/media"])
    downloads_dir: str = "~/Downloads/snips&pics"  # used when no card is plugged in
    keep_sessions: int = 200


@dataclass
class BrandingConfig:
    text: str = "snips&pics"


@dataclass
class Config:
    platform: str = "desktop"
    screen: ScreenConfig = field(default_factory=ScreenConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    gpio: GpioConfig = field(default_factory=GpioConfig)
    printer: PrinterConfig = field(default_factory=PrinterConfig)
    share: ShareConfig = field(default_factory=ShareConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    branding: BrandingConfig = field(default_factory=BrandingConfig)

    @property
    def is_pi(self) -> bool:
        return self.platform == "pi"

    @property
    def data_path(self) -> Path:
        return _resolve(self.storage.data_dir)

    @property
    def export_path(self) -> Path:
        return _resolve(self.storage.export_dir)

    @property
    def downloads_path(self) -> Path:
        return _resolve(self.storage.downloads_dir)


def _resolve(p: str) -> Path:
    path = Path(p).expanduser()
    return path if path.is_absolute() else ROOT / path


def detect_platform() -> str:
    try:
        model = Path("/proc/device-tree/model").read_text(errors="ignore").lower()
    except OSError:
        return "desktop"
    return "pi" if "raspberry pi" in model else "desktop"


def load_config(path: Path | None = None) -> Config:
    cfg = Config(platform=detect_platform())
    path = path or ROOT / "config.toml"
    if not path.exists():
        log.info("No %s found, using defaults", path.name)
        return cfg

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    if "platform" in data:
        cfg.platform = data["platform"]
    for f in fields(cfg):
        section = data.get(f.name)
        if not isinstance(section, dict):
            continue
        target = getattr(cfg, f.name)
        known = {sf.name for sf in fields(target)}
        for key, value in section.items():
            if key in known:
                setattr(target, key, value)
            else:
                log.warning("Unknown config key [%s] %s", f.name, key)
    return cfg
