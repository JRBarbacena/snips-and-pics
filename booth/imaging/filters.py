from __future__ import annotations

from typing import Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

_SEPIA = np.array(
    [[0.393, 0.769, 0.189],
     [0.349, 0.686, 0.168],
     [0.272, 0.534, 0.131]],
    dtype=np.float32,
)


def _arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def _img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _vignette(arr: np.ndarray, strength: float) -> np.ndarray:
    h, w = arr.shape[:2]
    y, x = np.ogrid[-1:1:complex(0, h), -1:1:complex(0, w)]
    mask = 1 - strength * np.clip(x * x + y * y - 0.3, 0, None)
    return arr * mask[..., None]


def original(img: Image.Image) -> Image.Image:
    return img


def black_white(img: Image.Image) -> Image.Image:
    return ImageOps.grayscale(img).convert("RGB")


def noir(img: Image.Image) -> Image.Image:
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=2)
    return ImageEnhance.Contrast(g).enhance(1.5).convert("RGB")


def sepia(img: Image.Image) -> Image.Image:
    return _img(_arr(img) @ _SEPIA.T)


def vintage(img: Image.Image) -> Image.Image:
    a = _arr(img)
    a = 0.6 * a + 0.4 * (a @ _SEPIA.T)
    a = a * 0.85 + 25  # faded blacks
    return _img(_vignette(a, 0.45))


def warm(img: Image.Image) -> Image.Image:
    a = _arr(img)
    a[..., 0] = a[..., 0] * 1.08 + 6
    a[..., 2] *= 0.9
    return _img(a)


def cool(img: Image.Image) -> Image.Image:
    a = _arr(img)
    a[..., 0] *= 0.9
    a[..., 2] = a[..., 2] * 1.08 + 6
    return _img(a)


def vivid(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Color(img).enhance(1.45)
    return ImageEnhance.Contrast(img).enhance(1.1)


FILTERS: dict[str, tuple[str, Callable[[Image.Image], Image.Image]]] = {
    "original": ("Original", original),
    "vivid": ("Vivid", vivid),
    "warm": ("Warm", warm),
    "cool": ("Cool", cool),
    "bw": ("B&W", black_white),
    "noir": ("Noir", noir),
    "sepia": ("Sepia", sepia),
    "vintage": ("Vintage", vintage),
}


def apply(name: str, img: Image.Image) -> Image.Image:
    return FILTERS[name][1](img)
