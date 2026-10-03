from __future__ import annotations

import math
import time

import numpy as np
import pygame
from PIL import Image

from booth.ui import fx
from booth.ui import theme as t

# pygame < 2.1.3 (Pi OS apt package) only has fromstring.
_frombytes = getattr(pygame.image, "frombytes", None) or pygame.image.fromstring


def fit_size(w: int, h: int, box_w: int, box_h: int) -> tuple[int, int]:
    s = min(box_w / w, box_h / h)
    return max(1, int(w * s)), max(1, int(h * s))


def pil_to_surface(img: Image.Image, box: tuple[int, int] | None = None) -> pygame.Surface:
    img = img.convert("RGB")
    if box:
        img = img.resize(fit_size(*img.size, *box), Image.LANCZOS)
    return _frombytes(img.tobytes(), img.size, "RGB")


def array_to_surface(arr: np.ndarray) -> pygame.Surface:
    h, w = arr.shape[:2]
    return _frombytes(np.ascontiguousarray(arr).tobytes(), (w, h), "RGB")


class Button:
    """Pill button. Styles: primary (gradient), secondary (white), glass (dark, for camera), ghost.

    icon is a Material Icons name, e.g. "arrow_forward".
    """

    def __init__(self, rect: tuple[int, int, int, int], label: str = "", style: str = "secondary",
                 size: int = 14, icon: str | None = None, icon_right: bool = False, glow: bool = False):
        self.rect = pygame.Rect(rect)
        self.style = style
        self.size = size
        self.icon = icon
        self.icon_right = icon_right
        self.glow = glow
        self.enabled = True
        self.visible = True
        self.pressed = False
        self._label = label
        self._cache: tuple[pygame.Surface, pygame.Surface] | None = None

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        if value != self._label:
            self._label = value
            self._cache = None

    def _build(self) -> tuple[pygame.Surface, pygame.Surface]:
        w, h = self.rect.size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if self.style == "primary":
            surf.blit(fx.gradient_pill(w, h), (0, 0))
            fg = t.WHITE
        elif self.style == "secondary":
            surf.blit(fx.rrect_surface(w, h, h // 2, t.WHITE), (0, 0))
            fg = t.INK
        elif self.style == "glass":
            surf.blit(fx.rrect_surface(w, h, h // 2, (20, 16, 28, 150)), (0, 0))
            fg = t.WHITE
        else:
            fg = t.ACCENT

        label = t.render(self._label, self.size, fg, "semibold") if self._label else None
        glyph = t.icon(self.icon, self.size + 6, fg) if self.icon else None
        gap = 6 if glyph and label else 0
        total = (glyph.get_width() if glyph else 0) + gap + (label.get_width() if label else 0)
        x = (w - total) // 2
        cy = h // 2
        parts = [glyph, label] if not self.icon_right else [label, glyph]
        for part in parts:
            if part is None:
                continue
            dy = 1 if part is label else 0  # Poppins sits slightly high
            surf.blit(part, part.get_rect(midleft=(x, cy + dy)))
            x += part.get_width() + gap

        pressed = surf.copy()
        pressed.fill((218, 218, 218, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return surf, pressed

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return
        if self._cache is None:
            self._cache = self._build()
        normal, pressed = self._cache
        radius = self.rect.h // 2
        if self.glow and self.enabled:
            pulse = 0.5 + 0.5 * math.sin(time.monotonic() * 3)
            halo = fx.soft_shadow((self.rect.w, self.rect.h), radius, 12, 170, t.ACCENT)
            halo.set_alpha(int(80 + 110 * pulse))
            surf.blit(halo, (self.rect.x - 12, self.rect.y - 10))
        elif self.style in ("primary", "secondary") and not self.pressed:
            fx.shadow(surf, self.rect, radius, blur=8, alpha=40, offset=3)
        img = pressed if self.pressed else normal
        if not self.enabled:
            img = img.copy()
            img.set_alpha(110)
        surf.blit(img, self.rect.move(0, 1 if self.pressed else 0))

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.visible and self.enabled and self.rect.collidepoint(pos)


class Carousel:
    """One large centered card with smaller neighbors peeking in from the sides."""

    SIDE_SCALE = 0.78
    SIDE_ALPHA = 150

    def __init__(self, center: tuple[int, int], cards: list[pygame.Surface], spacing: int, index: int = 0):
        self.center = center
        self.spacing = spacing
        self.index = index
        self.pos = float(index)
        self.set_cards(cards)

    def set_cards(self, cards: list[pygame.Surface]) -> None:
        self.cards = cards
        self._small = []
        for card in cards:
            w, h = card.get_size()
            small = pygame.transform.smoothscale(card, (int(w * self.SIDE_SCALE), int(h * self.SIDE_SCALE)))
            small.set_alpha(self.SIDE_ALPHA)
            self._small.append(small)

    def step(self, delta: int) -> bool:
        new = max(0, min(len(self.cards) - 1, self.index + delta))
        changed = new != self.index
        self.index = new
        return changed

    def update(self, dt: float) -> None:
        self.pos += (self.index - self.pos) * min(1.0, dt * 12)
        if abs(self.index - self.pos) < 0.002:
            self.pos = float(self.index)

    def center_rect(self) -> pygame.Rect:
        card = self.cards[self.index]
        return card.get_rect(center=self.center).inflate(-2 * fx.CARD_MARGIN, -2 * fx.CARD_MARGIN)

    def hit(self, pos: tuple[int, int]) -> str | None:
        """'center', 'prev', 'next' or None."""
        rect = self.center_rect()
        if rect.collidepoint(pos):
            return "center"
        if abs(pos[1] - rect.centery) < rect.h // 2:
            if pos[0] < rect.left and self.index > 0:
                return "prev"
            if pos[0] > rect.right and self.index < len(self.cards) - 1:
                return "next"
        return None

    def draw(self, surf: pygame.Surface) -> None:
        order = sorted(range(len(self.cards)), key=lambda i: -abs(i - self.pos))
        for i in order:
            d = i - self.pos
            if abs(d) > 1.7:
                continue
            k = min(1.0, abs(d))
            x = int(self.center[0] + d * self.spacing)
            if k < 0.01:
                img = self.cards[i]
            elif k > 0.99:
                img = self._small[i]
            else:
                full = self.cards[i]
                scale = fx.lerp(1.0, self.SIDE_SCALE, k)
                img = pygame.transform.smoothscale(full, (int(full.get_width() * scale), int(full.get_height() * scale)))
                img.set_alpha(int(fx.lerp(255, self.SIDE_ALPHA, k)))
            surf.blit(img, img.get_rect(center=(x, self.center[1])))


class Toggle:
    """Labelled on/off switch."""

    def __init__(self, rect: tuple[int, int, int, int], label: str, on: bool, icon: str | None = None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.icon = icon
        self.on = on
        self._knob = 1.0 if on else 0.0

    def update(self, dt: float) -> None:
        target = 1.0 if self.on else 0.0
        self._knob += (target - self._knob) * min(1.0, dt * 14)

    def draw(self, surf: pygame.Surface) -> None:
        fx.card(surf, self.rect, self.rect.h // 2, elevation=1)
        track = pygame.Rect(0, 0, 40, 24)
        track.midright = (self.rect.right - 10, self.rect.centery)
        color = tuple(int(fx.lerp(a, b, self._knob)) for a, b in zip((214, 208, 220), t.ACCENT))
        fx.rrect(surf, track, 12, color)
        kx = fx.lerp(track.left + 12, track.right - 12, self._knob)
        fx.circle(surf, (kx, track.centery + 1), 9, (0, 0, 0, 40))
        fx.circle(surf, (kx, track.centery), 9, t.WHITE)
        x = self.rect.x + 14
        if self.icon:
            fx.icon(surf, self.icon, (x + 9, self.rect.centery), 20, t.ACCENT)
            x += 26
        t.text(surf, self.label, 14, t.INK, "semibold", midleft=(x, self.rect.centery + 1))

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)
