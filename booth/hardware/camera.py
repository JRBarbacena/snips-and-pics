from __future__ import annotations

import logging
import math
import sys
import time
from abc import ABC, abstractmethod

import cv2
import numpy as np

from booth.config import CameraConfig

log = logging.getLogger(__name__)


class Camera(ABC):
    """Returns RGB uint8 frames (H x W x 3) at the configured resolution."""

    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @abstractmethod
    def _read(self) -> np.ndarray | None:
        ...

    def frame(self) -> np.ndarray | None:
        img = self._read()
        if img is not None and self.cfg.mirror:
            img = np.ascontiguousarray(img[:, ::-1])
        return img


class PiCamera(Camera):
    def start(self) -> None:
        from libcamera import controls
        from picamera2 import Picamera2

        self._cam = Picamera2()
        config = self._cam.create_video_configuration(
            main={"size": (self.cfg.width, self.cfg.height), "format": "RGB888"}
        )
        self._cam.configure(config)
        self._cam.start()
        try:
            self._cam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:  # sensors without autofocus
            log.info("Camera has no autofocus control")

    def stop(self) -> None:
        self._cam.stop()
        self._cam.close()

    def _read(self) -> np.ndarray | None:
        # picamera2's "RGB888" is BGR in memory.
        return cv2.cvtColor(self._cam.capture_array("main"), cv2.COLOR_BGR2RGB)


class OpenCVCamera(Camera):
    def start(self) -> None:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self.cfg.index, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {self.cfg.index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def stop(self) -> None:
        self._cap.release()

    def _read(self) -> np.ndarray | None:
        ok, bgr = self._cap.read()
        if not ok:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


class MockCamera(Camera):
    def _read(self) -> np.ndarray | None:
        w, h = self.cfg.width, self.cfg.height
        t = time.monotonic()
        x = np.linspace(0, 1, w, dtype=np.float32)
        y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        r = (x * 180 + 60) * np.ones_like(y)
        g = (y * 160 + 70) * np.ones_like(x)
        b = np.full((h, w), 150 + 60 * math.sin(t), dtype=np.float32)
        img = np.dstack([r, g, b]).astype(np.uint8)
        cx = int(w / 2 + w / 4 * math.cos(t))
        cy = int(h / 2 + h / 4 * math.sin(t * 1.3))
        cv2.circle(img, (cx, cy), h // 6, (250, 230, 120), -1)
        cv2.putText(img, time.strftime("%H:%M:%S"), (30, h - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
        # Draw text pre-flipped so it reads correctly after mirroring.
        return np.ascontiguousarray(img[:, ::-1]) if self.cfg.mirror else img


def create_camera(cfg: CameraConfig, is_pi: bool) -> Camera:
    backend = cfg.backend
    if backend == "auto":
        backend = "picamera" if is_pi else "opencv"

    cls = {"picamera": PiCamera, "opencv": OpenCVCamera, "mock": MockCamera}[backend]
    cam = cls(cfg)
    try:
        cam.start()
        return cam
    except Exception as exc:
        log.warning("Camera '%s' failed (%s); using mock camera", backend, exc)
        cam = MockCamera(cfg)
        cam.start()
        return cam
