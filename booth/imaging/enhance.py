"""Offline auto-enhance sized for a Pi Zero 2 W (512 MB, no GPU).

Neural enhancers (face restore, upscaling) do not fit on that board. To add one
later (phone offload, server, or cloud API), give it the same signature as
auto_enhance and register it in ENHANCERS.
"""
from __future__ import annotations

from typing import Callable

import cv2
import numpy as np
from PIL import Image


def _white_balance(bgr: np.ndarray, strength: float = 0.6) -> np.ndarray:
    means = bgr.reshape(-1, 3).mean(axis=0)
    gains = means.mean() / np.maximum(means, 1)
    gains = 1 + (gains - 1) * strength
    return np.clip(bgr * gains, 0, 255).astype(np.uint8)


def _local_contrast(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _smooth(bgr: np.ndarray, amount: float = 0.35) -> np.ndarray:
    soft = cv2.bilateralFilter(bgr, d=5, sigmaColor=30, sigmaSpace=30)
    return cv2.addWeighted(soft, amount, bgr, 1 - amount, 0)


def _sharpen(bgr: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.2)
    return cv2.addWeighted(bgr, 1.4, blur, -0.4, 0)


def auto_enhance(img: Image.Image) -> Image.Image:
    bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    bgr = _white_balance(bgr)
    bgr = _local_contrast(bgr)
    bgr = _smooth(bgr)
    bgr = _sharpen(bgr)
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


ENHANCERS: dict[str, Callable[[Image.Image], Image.Image]] = {
    "auto": auto_enhance,
}
