"""Anti-aliased drawing and effects.

pygame.draw has no anti-aliasing, so shapes are drawn at SS x size and
smooth-scaled down once, then cached. On the Pi each frame is just blits.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np
import pygame
import pygame.gfxdraw

from booth.ui import theme as t

SS = 4


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(p: float) -> float:
    p = clamp01(p)
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    p = clamp01(p)
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


def lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * p


def _rgba(color: tuple) -> tuple[int, int, int, int]:
    return (*color[:3], color[3] if len(color) > 3 else 255)


def _canvas(w: int, h: int, color: tuple) -> pygame.Surface:
    s = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    s.fill((*color[:3], 0))  # transparent pixels share RGB so edges don't fringe when scaled
    return s


# --- primitives ------------------------------------------------------------------

@lru_cache(maxsize=512)
def rrect_surface(w: int, h: int, radius: int, color: tuple, border: int = 0) -> pygame.Surface:
    color = _rgba(color)
    s = _canvas(w, h, color)
    pygame.draw.rect(s, color, s.get_rect(), width=border * SS, border_radius=min(radius, h // 2, w // 2) * SS)
    return pygame.transform.smoothscale(s, (w, h))


def rrect(surf: pygame.Surface, rect: pygame.Rect, radius: int, color: tuple, border: int = 0) -> None:
    surf.blit(rrect_surface(rect.w, rect.h, radius, tuple(color), border), rect.topleft)


@lru_cache(maxsize=256)
def circle_surface(r: int, color: tuple, width: int = 0) -> pygame.Surface:
    color = _rgba(color)
    d = r * 2 + 2
    s = _canvas(d, d, color)
    pygame.draw.circle(s, color, (d * SS // 2, d * SS // 2), r * SS, width * SS)
    return pygame.transform.smoothscale(s, (d, d))


def circle(surf: pygame.Surface, center: tuple[float, float], r: int, color: tuple, width: int = 0) -> None:
    img = circle_surface(int(r), tuple(color), width)
    surf.blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))


@lru_cache(maxsize=512)
def arc_surface(r: int, width: int, steps: int, color: tuple) -> pygame.Surface:
    """Arc covering steps/180 of a turn, clockwise from 12 o'clock, round caps."""
    color = _rgba(color)
    d = (r + width) * 2 + 2
    s = _canvas(d, d, color)
    c = d * SS / 2
    frac = steps / 180
    if frac > 0:
        ro, ri = r * SS + width * SS / 2, r * SS - width * SS / 2
        n = max(2, int(frac * 120))
        angles = [frac * math.tau * i / n for i in range(n + 1)]
        outer = [(c + ro * math.sin(a), c - ro * math.cos(a)) for a in angles]
        inner = [(c + ri * math.sin(a), c - ri * math.cos(a)) for a in reversed(angles)]
        pygame.draw.polygon(s, color, outer + inner)
        if frac < 1:
            for a in (0, frac * math.tau):
                pygame.draw.circle(s, color, (c + r * SS * math.sin(a), c - r * SS * math.cos(a)), width * SS / 2)
    return pygame.transform.smoothscale(s, (d, d))


def arc(surf: pygame.Surface, center: tuple[float, float], r: int, width: int, frac: float, color: tuple,
        rotate_deg: float = 0) -> None:
    img = arc_surface(r, width, int(round(clamp01(frac) * 180)), tuple(color))
    if rotate_deg:
        img = pygame.transform.rotozoom(img, -rotate_deg, 1)
    surf.blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))


def rounded(surface: pygame.Surface, radius: int) -> pygame.Surface:
    out = surface.convert_alpha()
    w, h = out.get_size()
    out.blit(rrect_surface(w, h, radius, (255, 255, 255, 255)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _surface_from_rgb(arr: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(np.ascontiguousarray(arr.transpose(1, 0, 2)))


def gradient(size: tuple[int, int], top: tuple, bottom: tuple, dither: bool = False) -> pygame.Surface:
    w, h = size
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    mix = (x * 0.35 + y * 0.65)[..., None]
    arr = np.array(top, np.float32) * (1 - mix) + np.array(bottom, np.float32) * mix
    if dither:
        # SPI TFTs are 16-bit (5 bits red/blue); noise hides the banding steps.
        arr += np.random.default_rng(3).uniform(-3.5, 3.5, arr.shape).astype(np.float32)
    return _surface_from_rgb(np.clip(arr, 0, 255).astype(np.uint8))


@lru_cache(maxsize=32)
def h_gradient(size: tuple[int, int], left: tuple, right: tuple) -> pygame.Surface:
    w, h = size
    mix = np.linspace(0, 1, w, dtype=np.float32)[None, :, None] * np.ones((h, 1, 1), np.float32)
    arr = np.array(left, np.float32) * (1 - mix) + np.array(right, np.float32) * mix
    return _surface_from_rgb(arr.astype(np.uint8))


@lru_cache(maxsize=32)
def gradient_pill(w: int, h: int, radius: int | None = None) -> pygame.Surface:
    return rounded(h_gradient((w, h), t.ACCENT, t.ACCENT_2), h // 2 if radius is None else radius)


@lru_cache(maxsize=64)
def gradient_icon(name: str, size: int) -> pygame.Surface:
    glyph = t.icon(name, size, t.WHITE)
    out = h_gradient(glyph.get_size(), t.ACCENT, t.ACCENT_2).convert_alpha()
    out.blit(glyph, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def icon(surf: pygame.Surface, name: str, center: tuple[int, int], size: int, color: tuple) -> None:
    img = t.icon(name, size, tuple(color))
    surf.blit(img, img.get_rect(center=center))


# --- composites ----------------------------------------------------------------

@lru_cache(maxsize=32)
def soft_circle(radius: int, color: tuple, alpha: int) -> pygame.Surface:
    d = radius * 2
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    dist = np.hypot(xx - radius + 0.5, yy - radius + 0.5) / radius
    a = (alpha * np.clip(1 - dist ** 2, 0, 1)).astype(np.uint8)
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    surf.fill((*color, 255))
    pygame.surfarray.pixels_alpha(surf)[:] = a.T
    return surf


@lru_cache(maxsize=64)
def soft_shadow(size: tuple[int, int], radius: int, blur: int = 10, alpha: int = 55,
                color: tuple = (60, 30, 70)) -> pygame.Surface:
    w, h = size
    s = pygame.Surface((w + 2 * blur, h + 2 * blur), pygame.SRCALPHA)
    s.fill((*color, 0))
    pygame.draw.rect(s, (*color, alpha), (blur, blur, w, h), border_radius=radius)
    small = pygame.transform.smoothscale(s, (max(1, s.get_width() // 5), max(1, s.get_height() // 5)))
    return pygame.transform.smoothscale(small, s.get_size())


def shadow(surf: pygame.Surface, rect: pygame.Rect, radius: int, blur: int = 10, alpha: int = 55,
           offset: int = 4) -> None:
    surf.blit(soft_shadow((rect.w, rect.h), radius, blur, alpha), (rect.x - blur, rect.y - blur + offset))


def card(surf: pygame.Surface, rect: pygame.Rect, radius: int = 16, color: tuple = t.WHITE,
         elevation: int = 1) -> None:
    if elevation:
        shadow(surf, rect, radius, blur=8 + 4 * elevation, alpha=40 + 10 * elevation, offset=2 + 2 * elevation)
    rrect(surf, rect, radius, color)


def glass(surf: pygame.Surface, rect: pygame.Rect, radius: int = 14, rgba: tuple = (20, 16, 28, 150)) -> None:
    rrect(surf, rect, radius, rgba)


def pill(surf: pygame.Surface, s: str, size: int, center: tuple[int, int], fg: tuple = t.WHITE,
         bg: tuple = (20, 16, 28, 160), weight: str = "semibold") -> pygame.Rect:
    img = t.render(s, size, fg, weight)
    rect = img.get_rect(center=center).inflate(28, 12)
    glass(surf, rect, rect.height // 2, bg)
    surf.blit(img, img.get_rect(center=(center[0], center[1] + 1)))
    return rect


def badge(surf: pygame.Surface, center: tuple[int, int], r: int) -> None:
    """White disc with a soft drop shadow, used behind hero icons."""
    sh = soft_shadow((r * 2, r * 2), r, 12, 60)
    surf.blit(sh, (center[0] - r - 12, center[1] - r - 12 + 5))
    circle(surf, center, r, t.WHITE)


CARD_MARGIN = 14


def card_surface(content: pygame.Surface, pad: int = 8, radius: int = 14) -> pygame.Surface:
    """White card with baked-in shadow around content; CARD_MARGIN of transparent space on each side."""
    w, h = content.get_width() + 2 * pad, content.get_height() + 2 * pad
    m = CARD_MARGIN
    out = pygame.Surface((w + 2 * m, h + 2 * m), pygame.SRCALPHA)
    out.blit(soft_shadow((w, h), radius, 10, 60), (m - 10, m - 10 + 4))
    out.blit(rrect_surface(w, h, radius, t.WHITE), (m, m))
    out.blit(content, (m + pad, m + pad))
    return out


def polaroid(photo: pygame.Surface, border: int = 5, bottom: int = 14) -> pygame.Surface:
    w, h = photo.get_size()
    out = rrect_surface(w + 2 * border, h + border + bottom, 4, t.WHITE).copy()
    out.blit(photo, (border, border))
    return out


class Background:
    """Pastel gradient with slowly drifting bokeh. Shared across screens."""

    def __init__(self, size: tuple[int, int], animated: bool = True):
        self.animated = animated
        self.base = gradient(size, t.BG_TOP, t.BG_BOTTOM, dither=True)
        rng = random.Random(7)
        w, h = size
        self.blobs = []
        for i in range(6):
            r = rng.randint(55, 110)
            self.blobs.append((rng.uniform(0, w), rng.uniform(0, h), soft_circle(r, t.BOKEH[i % len(t.BOKEH)], 110),
                               rng.uniform(0.15, 0.35), rng.uniform(0, math.tau)))
        self.time = 0.0

    def update(self, dt: float) -> None:
        if self.animated:
            self.time += dt

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self.base, (0, 0))
        for x, y, img, speed, phase in self.blobs:
            a = self.time * speed + phase
            surf.blit(img, img.get_rect(center=(int(x + 40 * math.sin(a)), int(y + 25 * math.cos(a * 1.3)))))


class Confetti:
    def __init__(self, size: tuple[int, int], count: int = 70):
        self.w, self.h = size
        rng = random.Random()
        self.parts = [
            [rng.uniform(0, self.w), rng.uniform(-160, -10), rng.uniform(-40, 40), rng.uniform(40, 150),
             rng.choice(t.CONFETTI), rng.uniform(3, 6), rng.uniform(0, math.tau), rng.uniform(-6, 6)]
            for _ in range(count)
        ]

    @property
    def alive(self) -> bool:
        return any(p[1] < self.h + 10 for p in self.parts)

    def update(self, dt: float) -> None:
        for p in self.parts:
            p[3] += 90 * dt
            p[0] += (p[2] + 25 * math.sin(p[6])) * dt
            p[1] += p[3] * dt
            p[6] += p[7] * dt

    def draw(self, surf: pygame.Surface) -> None:
        for x, y, _, _, color, size, rot, _ in self.parts:
            if y > self.h + 10:
                continue
            c, s = math.cos(rot), math.sin(rot)
            hw, hh = size, size * 0.45
            pts = [(int(x + c * dx - s * dy), int(y + s * dx + c * dy))
                   for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            pygame.gfxdraw.filled_polygon(surf, pts, color)
            pygame.gfxdraw.aapolygon(surf, pts, color)


# --- illustrations -------------------------------------------------------------

def strips_illustration(surf: pygame.Surface, c: tuple[int, int], s: int, time_s: float) -> None:
    x, y = c
    for i, dx in enumerate((-0.78, 0, 0.78)):
        lift = 5 * math.sin(time_s * 2.2) if i == 1 else 0
        r = pygame.Rect(0, 0, int(s * 0.62), int(s * 1.7))
        r.center = (int(x + dx * s), int(y - lift))
        rrect(surf, r.inflate(4, 4), 5, t.ACCENT if i == 1 else t.LINE)
        rrect(surf, r, 4, t.WHITE)
        fh = (r.h - 14) // 3
        for k in range(3):
            frame = pygame.Rect(r.x + 4, r.y + 4 + k * (fh + 3), r.w - 8, fh)
            rrect(surf, frame, 2, (255, 205, 214) if i == 1 else (222, 218, 228))


def countdown_illustration(surf: pygame.Surface, c: tuple[int, int], s: int, time_s: float) -> None:
    circle(surf, c, s, t.LINE, 6)
    arc(surf, c, s, 6, 1 - (time_s % 1.0), t.ACCENT)
    t.text(surf, str(3 - int(time_s) % 3), int(s * 1.05), t.INK, "bold", center=(c[0], c[1] + 3))


def shutter_button(surf: pygame.Surface, c: tuple[int, int], r: int, time_s: float) -> None:
    pulse = 0.5 + 0.5 * math.sin(time_s * 4)
    circle(surf, c, r, t.WHITE, 3)
    circle(surf, c, int(r - 6 - 2 * pulse), t.ACCENT)
