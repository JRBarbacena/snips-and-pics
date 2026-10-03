"""Screens for the handheld box: 3.5" touchscreen mounted portrait (320x480) on the side,
camera on the front, shutter button on top.

Rules: buttons at least 48 px tall (~7.5 mm on the panel), text at least 12 px,
one main thing per screen. Actions also reachable with the top shutter button
carry the SHUTTER icon.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Any, Callable

import cv2
import numpy as np
import pygame
from PIL import Image, ImageOps

from booth.hardware.inputs import InputEvent
from booth.hardware.printer import FilePrinter, PrinterError
from booth.imaging import filters
from booth.imaging.designs import DESIGNS
from booth.imaging.enhance import auto_enhance
from booth.imaging.templates import TEMPLATES, compose
from booth.imaging.thermal import render_thermal
from booth.share.qr import make_qr, wifi_payload
from booth.storage import export_session
from booth.ui import fx
from booth.ui import theme as t
from booth.ui.widgets import Button, Carousel, Toggle, array_to_surface, pil_to_surface

log = logging.getLogger(__name__)

POSE_TIPS = ("Big smiles!", "Strike a pose!", "Get closer!", "Silly face time!", "Look at the camera!")
DARK = (20, 16, 28)
SHUTTER = "radio_button_checked"
W, H = 320, 480
BTN_H = 48
BAR_Y = H - 60                          # bottom button row
FULL = (12, BAR_Y, W - 24, BTN_H)
LEFT = (12, BAR_Y, 140, BTN_H)
RIGHT = (160, BAR_Y, W - 172, BTN_H)


def _today() -> str:
    return time.strftime("%d %b %Y")


def _header(surf: pygame.Surface, title: str, x: int = 16) -> None:
    t.text(surf, title, 20, t.INK, "bold", midleft=(x, 30))


def _swipe_hint(surf: pygame.Surface) -> None:
    fx.icon(surf, "swipe", (W - 52, 30), 18, t.MUTED)
    t.text(surf, "Swipe", 12, t.MUTED, midleft=(W - 40, 31))


def _dots(surf: pygame.Surface, n: int, index: int, y: int) -> None:
    x = W // 2 - ((n - 1) * 14 + 18) // 2
    for i in range(n):
        if i == index:
            fx.rrect(surf, pygame.Rect(x, y - 3, 18, 6), 3, t.ACCENT)
            x += 26
        else:
            fx.circle(surf, (x + 3, y), 3, (205, 195, 212))
            x += 14


class Screen:
    idle_resets = True

    def __init__(self, app):
        self.app = app
        self._job: tuple[Any, Callable, Callable | None] | None = None

    @property
    def busy(self) -> bool:
        return self._job is not None

    def run_job(self, fn: Callable[[], Any], on_done: Callable[[Any], None],
                on_error: Callable[[Exception], None] | None = None) -> None:
        self._job = (self.app.jobs.submit(fn), on_done, on_error)

    def poll_job(self) -> None:
        if not self._job or not self._job[0].done():
            return
        future, on_done, on_error = self._job
        self._job = None
        try:
            result = future.result()
        except Exception as exc:
            log.exception("Background job failed")
            if on_error:
                on_error(exc)
            return
        on_done(result)

    def widgets(self) -> list[Button]:
        return []

    def on_press(self, pos) -> None:
        for b in self.widgets():
            b.pressed = b.hit(pos)

    def on_release(self) -> None:
        for b in self.widgets():
            b.pressed = False

    def enter(self) -> None:
        pass

    def on_tap(self, pos: tuple[int, int]) -> None:
        pass

    def on_swipe(self, direction: int) -> None:
        """direction -1 = finger moved left (next), +1 = right (previous)."""

    def on_input(self, event: InputEvent) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        pass


# --- welcome / onboarding ------------------------------------------------------

class WelcomeScreen(Screen):
    idle_resets = False
    _decor: list[pygame.Surface] = []

    def enter(self) -> None:
        self.t = 0.0
        self.how = Button((70, 404, 180, 44), "How it works", style="ghost", size=14, icon="help_outline")
        self.app.indicators.ready()
        label = t.render("Tap or press to start", 16, t.WHITE, "semibold")
        glyph = t.icon(SHUTTER, 22, t.WHITE)
        self.cta_rect = pygame.Rect(24, 330, W - 48, 54)
        self.cta = fx.gradient_pill(*self.cta_rect.size).copy()
        x = (self.cta_rect.w - glyph.get_width() - 8 - label.get_width()) // 2
        self.cta.blit(glyph, glyph.get_rect(midleft=(x, 27)))
        self.cta.blit(label, label.get_rect(midleft=(x + glyph.get_width() + 8, 28)))
        if not WelcomeScreen._decor:
            for i, angle in enumerate((-14, 11)):
                photo = fx.rounded(fx.gradient((64, 48), t.BOKEH[i], t.BOKEH[i + 2]), 2)
                WelcomeScreen._decor.append(pygame.transform.rotozoom(fx.polaroid(photo, 5, 13), angle, 1))

    def widgets(self):
        return [self.how]

    def _start(self) -> None:
        if self.app.onboarded_flag.exists():
            self.app.go_home()
        else:
            self.app.go(OnboardingScreen(self.app), "slide", 1)

    def on_tap(self, pos) -> None:
        if self.how.hit(pos):
            self.app.go(OnboardingScreen(self.app), "slide", 1)
        else:
            self._start()

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER:
            self._start()

    def update(self, dt) -> None:
        self.t += dt

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        left, right = self._decor
        surf.blit(left, left.get_rect(center=(52, int(64 + 5 * math.sin(self.t * 1.3)))))
        surf.blit(right, right.get_rect(center=(270, int(96 + 5 * math.cos(self.t * 1.1)))))

        bob = int(3 * math.sin(self.t * 2.2))
        fx.badge(surf, (W // 2, 160 + bob), 52)
        cam = fx.gradient_icon("photo_camera", 56)
        surf.blit(cam, cam.get_rect(center=(W // 2, 160 + bob)))

        parts = (("snips", t.INK), ("&", t.ACCENT), ("pics", t.INK))
        imgs = [t.render(s, 36, c, "bold") for s, c in parts]
        x = W // 2 - sum(i.get_width() for i in imgs) // 2
        for img in imgs:
            surf.blit(img, img.get_rect(midleft=(x, 250)))
            x += img.get_width()
        t.text(surf, "Strike a pose. Take it home.", 15, t.MUTED, center=(W // 2, 282))

        pulse = 0.5 + 0.5 * math.sin(self.t * 3)
        rect = self.cta_rect
        halo = fx.soft_shadow(rect.size, rect.h // 2, 12, 170, t.ACCENT)
        halo.set_alpha(int(70 + 130 * pulse))
        surf.blit(halo, (rect.x - 12, rect.y - 9))
        surf.blit(self.cta, rect)
        self.how.draw(surf)


class OnboardingScreen(Screen):
    idle_resets = False
    PAGES = (
        ("Pick a layout", "Swipe to choose a strip style, then press the button on top.", "strips"),
        ("Strike a pose", "Point the camera at your friends and press the top button. "
                          "Hold still for the 3-2-1 countdown.", "countdown"),
        ("Share it", "Pick a filter and design, then scan the QR code to get the photos on a phone.", "phone"),
    )

    def enter(self) -> None:
        self.page = 0
        self.anim = 1.0
        self.direction = 1
        self.t = 0.0
        self.skip = Button((W - 88, 8, 80, 44), "Skip", style="ghost", size=14)
        self.back = Button(LEFT, "Back", style="secondary", icon="arrow_back_ios_new")
        self.next = Button(RIGHT, "Next", style="primary", icon=SHUTTER)

    def widgets(self):
        return [self.skip, self.back, self.next]

    def _goto(self, i: int) -> None:
        if i < 0:
            return
        if i >= len(self.PAGES):
            self._finish()
            return
        self.direction = 1 if i > self.page else -1
        self.page = i
        self.anim = 0.0

    def _finish(self) -> None:
        self.app.onboarded_flag.parent.mkdir(parents=True, exist_ok=True)
        self.app.onboarded_flag.touch()
        self.app.go_home()

    def on_tap(self, pos) -> None:
        if self.skip.hit(pos):
            self._finish()
        elif self.back.hit(pos):
            self._goto(self.page - 1)
        elif self.next.hit(pos):
            self._goto(self.page + 1)

    def on_swipe(self, direction) -> None:
        self._goto(self.page - direction)

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER:
            self._goto(self.page + 1)
        elif event == InputEvent.BACK:
            if self.page:
                self._goto(self.page - 1)
            else:
                self.app.go_welcome()

    def update(self, dt) -> None:
        self.t += dt
        self.anim = min(1.0, self.anim + dt / 0.35)

    def _draw_page(self, surf: pygame.Surface) -> None:
        title, body, kind = self.PAGES[self.page]
        center = (W // 2, 150)
        fx.badge(surf, center, 62)
        if kind == "strips":
            fx.strips_illustration(surf, center, 34, self.t)
        elif kind == "countdown":
            fx.countdown_illustration(surf, center, 36, self.t)
        else:
            img = fx.gradient_icon("qr_code_scanner", 64)
            surf.blit(img, img.get_rect(center=center))
        t.text(surf, f"STEP {self.page + 1} OF {len(self.PAGES)}", 12, t.ACCENT, "semibold", center=(W // 2, 248))
        t.text(surf, title, 24, t.INK, "bold", center=(W // 2, 276))
        y = 312
        for line in t.wrap(body, 15, W - 48):
            t.text(surf, line, 15, t.MUTED, center=(W // 2, y))
            y += 22

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        e = fx.ease_out(self.anim)
        if e < 1:
            layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            self._draw_page(layer)
            layer.set_alpha(int(255 * e))
            surf.blit(layer, (int((1 - e) * self.direction * 70), 0))
        else:
            self._draw_page(surf)

        _dots(surf, len(self.PAGES), self.page, BAR_Y - 18)
        self.back.visible = self.page > 0
        self.next.label = "Let's go" if self.page == len(self.PAGES) - 1 else "Next"
        rect = pygame.Rect(RIGHT if self.back.visible else FULL)
        if rect != self.next.rect:
            self.next = Button(rect, self.next.label, style="primary", icon=SHUTTER)
        self.skip.draw(surf)
        self.back.draw(surf)
        self.next.draw(surf)


# --- layout picker -------------------------------------------------------------

class HomeScreen(Screen):
    _cards: list[pygame.Surface] = []

    def enter(self) -> None:
        self.app.indicators.ready()
        if not HomeScreen._cards:
            brand = self.app.cfg.branding.text
            for tpl in TEMPLATES:
                content = pygame.Surface((180, 262), pygame.SRCALPHA)
                thumb = pil_to_surface(compose(tpl, None, brand, _today()), (164, 196))
                trect = thumb.get_rect(center=(90, 100))
                fx.rrect(content, trect.inflate(2, 2), 2, t.LINE)
                content.blit(thumb, trect)
                t.text(content, tpl.name, 17, t.INK, "semibold", center=(90, 222))
                t.text(content, f"{tpl.photo_count} photos", 13, t.MUTED, center=(90, 246))
                HomeScreen._cards.append(fx.card_surface(content, 8, 18))
        self.carousel = Carousel((W // 2, 226), HomeScreen._cards, spacing=212,
                                 index=TEMPLATES.index(self.app.state.template))
        self.back = Button((8, 8, 44, 44), "", style="secondary", icon="arrow_back_ios_new", size=14)
        self.start = Button(FULL, "Start", style="primary", icon=SHUTTER, glow=True)

    def widgets(self):
        return [self.back, self.start]

    def _start(self) -> None:
        self.app.state.new_session(TEMPLATES[self.carousel.index])
        self.app.go(CaptureScreen(self.app), "fade")

    def on_tap(self, pos) -> None:
        if self.back.hit(pos):
            self.app.go_welcome()
        elif self.start.hit(pos):
            self._start()
        else:
            hit = self.carousel.hit(pos)
            if hit == "center":
                self._start()
            elif hit:
                self.carousel.step(-1 if hit == "prev" else 1)

    def on_swipe(self, direction) -> None:
        self.carousel.step(-direction)

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER:
            self._start()
        elif event == InputEvent.BACK:
            self.app.go_welcome()

    def update(self, dt) -> None:
        self.carousel.update(dt)

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        self.back.draw(surf)
        _header(surf, "Pick a layout", x=62)
        _swipe_hint(surf)
        self.carousel.draw(surf)
        _dots(surf, len(TEMPLATES), self.carousel.index, 392)
        self.start.draw(surf)


# --- capture -------------------------------------------------------------------

class CaptureScreen(Screen):
    FLY_SECONDS = 0.6
    VIEW = pygame.Rect(0, 104, W, W * 3 // 4)   # 4:3 photos, full width

    def enter(self) -> None:
        self.phase = "ready"  # ready | countdown | between | done
        self.count = 0
        self.timer = 0.0
        self.flash = 0.0
        self.t = 0.0
        self.latest: np.ndarray | None = None
        self.preview: pygame.Surface | None = None
        self.tray: list[pygame.Surface] = []
        self.flyers: list[list] = []
        self.close = Button((8, 8, 44, 44), "", style="glass", icon="close", size=16)
        self.app.indicators.ready()

    def widgets(self):
        return [self.close]

    @property
    def total(self) -> int:
        return self.app.state.template.photo_count

    def _preview_surface(self, frame: np.ndarray) -> pygame.Surface:
        vw, vh = self.VIEW.size
        h, wd = frame.shape[:2]
        scale = max(vw / wd, vh / h)
        nw, nh = math.ceil(wd * scale), math.ceil(h * scale)
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        x, y = (nw - vw) // 2, (nh - vh) // 2
        return array_to_surface(resized[y:y + vh, x:x + vw])

    def _tray_pos(self, i: int) -> tuple[int, int]:
        n = self.total
        x0 = W // 2 - (n * 70 - 8) // 2
        return x0 + i * 70 + 31, 428

    def _start_countdown(self) -> None:
        self.phase = "countdown"
        self.count = self.app.cfg.capture.countdown_seconds
        self.timer = 1.0
        self.app.indicators.tick()

    def _capture(self) -> None:
        if self.latest is None:
            return
        photo = Image.fromarray(self.latest)
        self.app.state.raw.append(photo)
        self.app.indicators.shutter()
        self.flash = 1.0
        big = fx.polaroid(pil_to_surface(photo, (160, 120)), 6, 16)
        small = fx.polaroid(pil_to_surface(photo, (56, 42)), 3, 8)
        self.flyers.append([big, small, 0.0, len(self.app.state.raw) - 1])
        if len(self.app.state.raw) >= self.total:
            self.phase = "done"
            self.timer = 1.0
        else:
            self.phase = "between"
            self.timer = self.app.cfg.capture.interval_seconds

    def _cancel(self) -> None:
        self.app.go_home(direction=-1)

    def on_tap(self, pos) -> None:
        if self.close.hit(pos):
            self._cancel()
        elif self.phase == "ready":
            self._start_countdown()

    def on_input(self, event) -> None:
        if event == InputEvent.BACK:
            self._cancel()
        elif event == InputEvent.SHUTTER and self.phase == "ready":
            self._start_countdown()

    def update(self, dt) -> None:
        self.t += dt
        frame = self.app.camera.frame()
        if frame is not None:
            self.latest = frame
            self.preview = self._preview_surface(frame)

        self.flash = max(0.0, self.flash - dt * 3)
        for f in self.flyers[:]:
            f[2] += dt
            if f[2] >= self.FLY_SECONDS:
                self.flyers.remove(f)
                self.tray.append(f[1])

        if self.phase == "countdown":
            self.timer -= dt
            if self.timer <= 0:
                self.count -= 1
                if self.count <= 0:
                    self._capture()
                else:
                    self.timer = 1.0
                    self.app.indicators.tick()
        elif self.phase == "between":
            self.timer -= dt
            if self.timer <= 0:
                self._start_countdown()
        elif self.phase == "done":
            self.timer -= dt
            if self.timer <= 0 and not self.flyers:
                self._go_process()

    def _go_process(self) -> None:
        app = self.app
        raw = list(app.state.raw)

        def done(enhanced):
            app.state.enhanced = enhanced
            app.go(FilterScreen(app), "fade")

        app.go(ProcessingScreen(app, "Developing your photos", lambda: [auto_enhance(p) for p in raw],
                                done, raw), "fade")

    def _draw_corners(self, surf: pygame.Surface) -> None:
        g = self.VIEW
        L, inset, th = 20, 8, 3
        for cx, cy, dx, dy in ((g.left, g.top, 1, 1), (g.right, g.top, -1, 1),
                               (g.left, g.bottom, 1, -1), (g.right, g.bottom, -1, -1)):
            x, y = cx + dx * inset, cy + dy * inset
            hx = x if dx > 0 else x - L
            vy = y if dy > 0 else y - L
            fx.rrect(surf, pygame.Rect(hx, y - (0 if dy > 0 else th), L, th), 1, t.WHITE)
            fx.rrect(surf, pygame.Rect(x - (0 if dx > 0 else th), vy, th, L), 1, t.WHITE)

    def _draw_progress(self, surf: pygame.Surface) -> None:
        n = self.total
        taken = len(self.app.state.raw)
        rect = pygame.Rect(0, 0, n * 22 + 18, 30)
        rect.center = (W // 2, 30)
        fx.glass(surf, rect, 15, (255, 255, 255, 30))
        for i in range(n):
            c = (rect.x + 20 + i * 22, rect.centery)
            if i < taken:
                fx.circle(surf, c, 7, t.ACCENT)
            elif i == taken and self.phase != "done":
                pulse = 0.5 + 0.5 * math.sin(self.t * 5)
                fx.circle(surf, c, 7 + round(pulse), t.WHITE, 2)
            else:
                fx.circle(surf, c, 4, (120, 112, 135))
        shot = min(taken + 1, n)
        label = "All done!" if self.phase == "done" else f"Photo {shot} of {n}"
        t.text(surf, label, 15, t.WHITE, "semibold", center=(W // 2, 76))

    def draw(self, surf) -> None:
        surf.fill(DARK)
        v = self.VIEW
        if self.preview:
            surf.blit(self.preview, v)
        self._draw_corners(surf)
        self._draw_progress(surf)
        self.close.draw(surf)
        cx, cy = v.center

        if self.phase == "ready":
            card = pygame.Rect(12, 362, W - 24, 70)
            fx.glass(surf, card, 22, (255, 255, 255, 26))
            fx.shutter_button(surf, (card.x + 40, card.centery), 24, self.t)
            t.text(surf, "Ready when you are!", 16, t.WHITE, "semibold", midleft=(card.x + 78, card.centery - 11))
            t.text(surf, "Press the top button or tap", 13, (205, 198, 215),
                   midleft=(card.x + 78, card.centery + 13))
        elif self.phase == "countdown":
            fx.circle(surf, (cx, cy), 72, (*DARK, 140))
            fx.arc(surf, (cx, cy), 63, 5, self.timer, t.WHITE)
            pop = fx.clamp01((1.0 - self.timer) / 0.35)
            num = t.render(str(self.count), 72, t.WHITE, "bold")
            img = pygame.transform.rotozoom(num, 0, fx.lerp(1.7, 1.0, fx.ease_out_back(pop)))
            surf.blit(img, img.get_rect(center=(cx, cy + 5)))
            tip = POSE_TIPS[len(self.app.state.raw) % len(POSE_TIPS)]
            fx.pill(surf, tip, 16, (W // 2, 374), bg=(*t.ACCENT, 255))
        elif self.phase == "between":
            fx.pill(surf, "Nice! Next one coming up", 15, (cx, cy))
            interval = self.app.cfg.capture.interval_seconds
            bar = pygame.Rect(W // 2 - 80, 370, 160, 6)
            fx.rrect(surf, bar, 3, (255, 255, 255, 60))
            filled = bar.copy()
            filled.w = max(6, int(bar.w * fx.clamp01(1 - self.timer / interval)))
            fx.rrect(surf, filled, 3, t.WHITE)
        elif self.phase == "done":
            fx.pill(surf, "That's a wrap!", 20, (cx, cy))

        if self.phase != "ready":
            for i in range(self.total):
                x, y = self._tray_pos(i)
                if i < len(self.tray):
                    surf.blit(self.tray[i], self.tray[i].get_rect(center=(x, y)))
                else:
                    fx.rrect(surf, pygame.Rect(x - 31, y - 26, 62, 52), 4, (255, 255, 255, 22))
        for big, small, age, index in self.flyers:
            p = fx.ease_out(age / self.FLY_SECONDS)
            tx, ty = self._tray_pos(index)
            scale = fx.lerp(1.0, small.get_width() / big.get_width(), p)
            img = pygame.transform.rotozoom(big, fx.lerp(-8, 0, p), scale)
            surf.blit(img, img.get_rect(center=(int(fx.lerp(cx, tx, p)), int(fx.lerp(cy, ty, p)))))

        if self.flash > 0:
            veil = pygame.Surface(surf.get_size())
            veil.fill(t.WHITE)
            veil.set_alpha(int(255 * self.flash))
            surf.blit(veil, (0, 0))


# --- processing ----------------------------------------------------------------

class ProcessingScreen(Screen):
    idle_resets = False
    MIN_SECONDS = 1.0

    def __init__(self, app, message: str, job: Callable[[], Any], on_done: Callable[[Any], None],
                 photos: list[Image.Image] | None = None):
        super().__init__(app)
        self.message = message
        self.job = job
        self.on_done = on_done
        self.photos = photos or []

    def enter(self) -> None:
        self.t = 0.0
        self.error: str | None = None
        self.result: tuple[Any] | None = None
        n = min(len(self.photos), 4)
        angles = [(i - (n - 1) / 2) * 10 for i in range(n)]
        self.cards = []
        for photo, angle in zip(self.photos[:4], angles):
            base = fx.polaroid(pil_to_surface(photo, (88, 66)), 5, 16)
            self.cards.append((base, angle, pygame.transform.rotozoom(base, angle, 1)))
        self.app.indicators.busy()
        self.run_job(self.job, lambda r: setattr(self, "result", (r,)), self._failed)

    def _failed(self, exc: Exception) -> None:
        self.error = "Something went wrong. Please try again."
        self.t = 0.0

    def update(self, dt) -> None:
        self.t += dt
        if self.error and self.t > 3:
            self.app.go_home(direction=-1)
        elif self.result and self.t >= self.MIN_SECONDS:
            self.app.indicators.ready()
            self.on_done(self.result[0])

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        cx = W // 2
        if self.error:
            fx.icon(surf, "error_outline", (cx, 200), 48, t.ACCENT)
            for i, line in enumerate(t.wrap(self.error, 16, W - 48, "semibold")):
                t.text(surf, line, 16, t.INK, "semibold", center=(cx, 252 + i * 24))
            return

        n = len(self.cards)
        for i, (base, angle, rotated) in enumerate(self.cards):
            p = fx.clamp01((self.t - i * 0.15) / 0.4)
            if p <= 0:
                continue
            img = rotated if p >= 1 else pygame.transform.rotozoom(base, angle, max(0.05, fx.ease_out_back(p)))
            off = i - (n - 1) / 2
            surf.blit(img, img.get_rect(center=(int(cx + off * 54), int(200 + abs(off) * 12))))
        if not n:
            fx.circle(surf, (cx, 200), 32, t.LINE, 6)
            fx.arc(surf, (cx, 200), 32, 6, 0.3, t.ACCENT, rotate_deg=self.t * 300)

        t.text(surf, self.message, 18, t.INK, "semibold", center=(cx, 320))
        for k in range(3):
            dy = -6 * max(0.0, math.sin(self.t * 6 - k * 0.7))
            fx.circle(surf, (cx - 16 + k * 16, 354 + dy), 5, t.ACCENT)


# --- filters -------------------------------------------------------------------

class FilterScreen(Screen):
    PREVIEW = (280, 210)
    FADE_SECONDS = 0.18

    def enter(self) -> None:
        state = self.app.state
        self.names = list(filters.FILTERS)
        self.index = self.names.index(state.filter_name)
        self.toggle = Toggle((12, 358, W - 24, 48), "Auto enhance", state.enhance_on, icon="auto_awesome")
        # Small glyphs, but the tap area stays finger-sized.
        self.prev = Button((40, 288, 44, 44), "", style="ghost", icon="chevron_left", size=18)
        self.nxt = Button((W - 84, 288, 44, 44), "", style="ghost", icon="chevron_right", size=18)
        self.retake = Button(LEFT, "Retake", style="secondary", icon="replay")
        self.next = Button(RIGHT, "Next", style="primary", icon=SHUTTER)
        self.photo_rect = pygame.Rect(0, 0, self.PREVIEW[0] + 12, self.PREVIEW[1] + 12)
        self.photo_rect.center = (W // 2, 172)
        self._build_previews()
        self.fading_from: pygame.Surface | None = None
        self.fade = 1.0

    def widgets(self):
        return [self.prev, self.nxt, self.retake, self.next]

    def _build_previews(self) -> None:
        self.base = ImageOps.fit(self.app.state.base_photos[0], self.PREVIEW, Image.LANCZOS)
        self._previews: dict[int, pygame.Surface] = {}

    def _preview(self, index: int) -> pygame.Surface:
        if index not in self._previews:
            self._previews[index] = fx.rounded(pil_to_surface(filters.apply(self.names[index], self.base)), 10)
        return self._previews[index]

    def _select(self, index: int) -> None:
        index %= len(self.names)
        if index == self.index:
            return
        self.fading_from = self._preview(self.index)
        self.fade = 0.0
        self.index = index
        self.app.state.filter_name = self.names[index]

    def _retake(self) -> None:
        self.app.state.new_session(self.app.state.template)
        self.app.go(CaptureScreen(self.app), "fade")

    def _finish(self) -> None:
        self.app.go(DesignScreen(self.app), "slide", 1)

    def on_tap(self, pos) -> None:
        if self.toggle.hit(pos):
            self.app.state.enhance_on = self.toggle.on = not self.toggle.on
            self._build_previews()
        elif self.prev.hit(pos):
            self._select(self.index - 1)
        elif self.nxt.hit(pos) or self.photo_rect.collidepoint(pos):
            self._select(self.index + 1)
        elif self.retake.hit(pos):
            self._retake()
        elif self.next.hit(pos):
            self._finish()

    def on_swipe(self, direction) -> None:
        self._select(self.index - direction)

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER:
            self._finish()
        elif event in (InputEvent.SHUTTER_HOLD, InputEvent.BACK):
            self._retake()

    def update(self, dt) -> None:
        self.toggle.update(dt)
        self.fade = min(1.0, self.fade + dt / self.FADE_SECONDS)
        if self.fade >= 1:
            self.fading_from = None

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        _header(surf, "Filter")
        _swipe_hint(surf)

        fx.card(surf, self.photo_rect, 16, elevation=2)
        current = self._preview(self.index)
        pos = current.get_rect(center=self.photo_rect.center)
        if self.fading_from:
            surf.blit(self.fading_from, pos)
            img = current.copy()
            img.set_alpha(int(255 * fx.ease_out(self.fade)))
            surf.blit(img, pos)
        else:
            surf.blit(current, pos)

        name = filters.FILTERS[self.names[self.index]][0]
        t.text(surf, name, 20, t.INK, "bold", center=(W // 2, 310))
        _dots(surf, len(self.names), self.index, 344)
        self.prev.draw(surf)
        self.nxt.draw(surf)
        self.toggle.draw(surf)
        self.retake.draw(surf)
        self.next.draw(surf)


# --- card design ---------------------------------------------------------------

class DesignScreen(Screen):
    CONTENT = (220, 250)

    def enter(self) -> None:
        state = self.app.state
        self.photos = [filters.apply(state.filter_name, ImageOps.fit(p, (320, 240), Image.BILINEAR))
                       for p in state.base_photos]
        brand = self.app.cfg.branding.text
        cw, ch = self.CONTENT
        cards = []
        for design in DESIGNS:
            content = pygame.Surface(self.CONTENT, pygame.SRCALPHA)
            img = compose(state.template, self.photos, brand, _today(), design)
            if img.width > img.height:
                img = img.rotate(90, expand=True)
            strip = pil_to_surface(img, (cw - 8, ch - 8))
            srect = strip.get_rect(center=(cw // 2, ch // 2))
            fx.rrect(content, srect.inflate(2, 2), 2, t.LINE)
            content.blit(strip, srect)
            cards.append(fx.card_surface(content, 8, 16))
        cards.append(fx.card_surface(self._coming_soon(), 8, 16))
        ids = [d.id for d in DESIGNS]
        self.carousel = Carousel((W // 2, 206), cards, spacing=240, index=ids.index(state.design_id))
        self.back = Button(LEFT, "Filter", style="secondary", icon="arrow_back_ios_new")
        self.create = Button(RIGHT, "Create", style="primary", icon=SHUTTER)

    def _coming_soon(self) -> pygame.Surface:
        w, h = self.CONTENT
        content = pygame.Surface((w, h), pygame.SRCALPHA)
        fx.rrect(content, content.get_rect(), 10, (248, 244, 250))
        c = (w // 2, h // 2)
        fx.circle(content, c, 38, t.WHITE)
        fx.icon(content, "palette", c, 40, (190, 180, 198))
        lock = (c[0] + 30, c[1] + 28)
        fx.circle(content, lock, 14, t.MUTED)
        fx.icon(content, "lock", lock, 16, t.WHITE)
        return content

    def widgets(self):
        return [self.back, self.create]

    @property
    def _locked(self) -> bool:
        return self.carousel.index >= len(DESIGNS)

    def _sync(self) -> None:
        if not self._locked:
            self.app.state.design_id = DESIGNS[self.carousel.index].id
        self.create.enabled = not self._locked

    def _finish(self) -> None:
        if self._locked:
            return
        app = self.app
        state = app.state
        template, name, base = state.template, state.filter_name, list(state.base_photos)
        design = DESIGNS[self.carousel.index]
        brand = app.cfg.branding.text

        def build():
            photos = [filters.apply(name, p) for p in base]
            strip = compose(template, photos, brand, _today(), design)
            session = app.store.create()
            app.store.save(session, photos, strip)
            return strip, session

        def done(result):
            state.strip, state.session = result
            app.go(ReviewScreen(app), "fade")

        previews = [ImageOps.fit(p, (176, 132)) for p in self.photos]
        app.go(ProcessingScreen(app, "Building your strip", build, done, previews), "fade")

    def _back(self) -> None:
        self.app.go(FilterScreen(self.app), "slide", -1)

    def on_tap(self, pos) -> None:
        if self.back.hit(pos):
            self._back()
        elif self.create.hit(pos):
            self._finish()
        else:
            hit = self.carousel.hit(pos)
            if hit in ("prev", "next"):
                self.carousel.step(-1 if hit == "prev" else 1)
                self._sync()

    def on_swipe(self, direction) -> None:
        self.carousel.step(-direction)
        self._sync()

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER:
            self._finish()
        elif event == InputEvent.BACK:
            self._back()

    def update(self, dt) -> None:
        self.carousel.update(dt)

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        _header(surf, "Card design")
        _swipe_hint(surf)
        self.carousel.draw(surf)
        if self._locked:
            t.text(surf, "More designs", 18, t.MUTED, "semibold", center=(W // 2, 362))
            t.text(surf, "Coming soon", 13, t.MUTED, center=(W // 2, 386))
        else:
            design = DESIGNS[self.carousel.index]
            t.text(surf, design.name, 18, t.INK, "semibold", center=(W // 2, 362))
            t.text(surf, design.tagline, 13, t.MUTED, center=(W // 2, 386))
        self.back.draw(surf)
        self.create.draw(surf)


# --- review / thanks -----------------------------------------------------------

class ReviewScreen(Screen):
    QR = 150
    ROW1 = BAR_Y - 56

    def enter(self) -> None:
        app = self.app
        self.t = 0.0
        self.toast: str | None = None
        self.toast_timer = 0.0
        self.confetti = fx.Confetti(app.size, 50) if app.effects else None
        strip = app.state.strip
        if strip.width > strip.height:
            strip = strip.rotate(90, expand=True)
        self.strip_card = pygame.Rect(12, 64, 112, self.ROW1 - 64 - 10)
        self.strip = pil_to_surface(strip, (self.strip_card.w - 16, self.strip_card.h - 16))
        self.url = app.share.session_url(app.state.session.id) if app.share else None

        def qr(data: str) -> pygame.Surface:
            return pil_to_surface(make_qr(data).resize((self.QR, self.QR), Image.NEAREST))

        ssid = app.cfg.share.hotspot_ssid
        self.wifi_qr = qr(wifi_payload(ssid, app.cfg.share.hotspot_password)) if self.url and ssid else None
        self.link_qr = qr(self.url) if self.url else None
        self.tab = 0 if self.wifi_qr else 1
        self.tabs = [pygame.Rect(14, 10, 144, 42), pygame.Rect(162, 10, 144, 42)]
        self.qr_card = pygame.Rect(0, 0, self.QR + 16, self.QR + 16)
        self.qr_card.midtop = ((self.strip_card.right + W) // 2, 64)

        self.has_printer = app.printer.name != "none"
        if self.has_printer:
            self.print_btn = Button((12, self.ROW1, 140, BTN_H), "Print", style="primary", icon=SHUTTER)
            self.save_btn = Button((160, self.ROW1, W - 172, BTN_H), "Save", style="secondary", icon="sd_card")
        else:
            self.print_btn = None
            self.save_btn = Button((12, self.ROW1, W - 24, BTN_H), "Save", style="primary", icon=SHUTTER)
        self.retake_btn = Button(LEFT, "Retake", style="secondary", icon="replay")
        self.done_btn = Button(RIGHT, "Done", style="secondary", icon="check")

    def widgets(self):
        return [b for b in (self.print_btn, self.save_btn, self.retake_btn, self.done_btn) if b]

    def _show(self, msg: str, seconds: float = 3.0) -> None:
        self.toast = msg
        self.toast_timer = seconds

    def _print(self) -> None:
        if not self.has_printer or self.busy:
            return
        app = self.app
        strip = app.state.strip
        qr_url = self.url if app.cfg.share.public else None
        self._show("Printing...")

        def job():
            app.printer.print_image(render_thermal(strip, app.cfg.printer.paper_width_px, qr_url))

        def done(_):
            self._show("Print preview saved" if isinstance(app.printer, FilePrinter) else "Printed!")

        def failed(exc):
            self._show(str(exc) if isinstance(exc, PrinterError) else "Print failed")

        self.run_job(job, done, failed)

    def _save(self) -> None:
        if self.busy:
            return
        app = self.app
        session = app.state.session
        self._show("Saving...")

        def job():
            return export_session(session, app.cfg.export_path, app.cfg.storage.removable_media_roots,
                                  app.cfg.downloads_path)

        def done(result):
            self._show("Saved to card!" if result.cards else "No card, saved to Downloads")

        self.run_job(job, done, lambda exc: self._show("Save failed"))

    def _retake(self) -> None:
        self.app.state.new_session(self.app.state.template)
        self.app.go(CaptureScreen(self.app), "fade")

    def _done(self) -> None:
        self.app.go(ThanksScreen(self.app), "fade")

    def on_tap(self, pos) -> None:
        if self.print_btn and self.print_btn.hit(pos):
            self._print()
        elif self.save_btn.hit(pos):
            self._save()
        elif self.retake_btn.hit(pos):
            self._retake()
        elif self.done_btn.hit(pos):
            self._done()
        elif self.wifi_qr:
            for i, rect in enumerate(self.tabs):
                if rect.collidepoint(pos):
                    self.tab = i
            if self.qr_card.collidepoint(pos):
                self.tab = 1 - self.tab

    def on_swipe(self, direction) -> None:
        if self.wifi_qr:
            self.tab = 1 if direction < 0 else 0

    def on_input(self, event) -> None:
        if event == InputEvent.SHUTTER and self.has_printer:
            self._print()
        elif event == InputEvent.SHUTTER:
            self._save()
        elif event == InputEvent.SHUTTER_HOLD:
            self._retake()
        elif event == InputEvent.BACK:
            self._done()

    def update(self, dt) -> None:
        self.t += dt
        if self.confetti:
            self.confetti.update(dt)
            if not self.confetti.alive:
                self.confetti = None
        if self.toast and not self.busy:
            self.toast_timer -= dt
            if self.toast_timer <= 0:
                self.toast = None

    def _draw_tabs(self, surf) -> None:
        track = self.tabs[0].union(self.tabs[1]).inflate(4, 4)
        fx.rrect(surf, track, track.h // 2, t.WHITE)
        for i, (rect, icon, label) in enumerate(zip(self.tabs, ("wifi", "download"), ("1  Wi-Fi", "2  Photos"))):
            active = i == self.tab
            if active:
                surf.blit(fx.gradient_pill(rect.w, rect.h), rect)
            color = t.WHITE if active else t.MUTED
            glyph = t.icon(icon, 18, color)
            lbl = t.render(label, 14, color, "semibold")
            x = rect.centerx - (glyph.get_width() + 4 + lbl.get_width()) // 2
            surf.blit(glyph, glyph.get_rect(midleft=(x, rect.centery)))
            surf.blit(lbl, lbl.get_rect(midleft=(x + glyph.get_width() + 4, rect.centery + 1)))

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        p = fx.ease_out(self.t / 0.6)
        card = self.strip_card.move(0, int((1 - p) * 80))
        fx.card(surf, card, 14, elevation=2)
        surf.blit(self.strip, self.strip.get_rect(center=card.center))

        rx = self.qr_card.centerx
        text_w = W - self.strip_card.right - 16
        if self.link_qr:
            if self.wifi_qr:
                self._draw_tabs(surf)
                qr = self.wifi_qr if self.tab == 0 else self.link_qr
                caption = (f"Join \"{self.app.cfg.share.hotspot_ssid}\" Wi-Fi first" if self.tab == 0
                           else "Then scan to get your photos")
            else:
                t.text(surf, "Looking good!", 20, t.INK, "bold", center=(W // 2, 30))
                qr, caption = self.link_qr, "Scan with a phone camera to get your photos"
            fx.card(surf, self.qr_card, 14, elevation=1)
            surf.blit(qr, qr.get_rect(center=self.qr_card.center))
            y = self.qr_card.bottom + 18
            for line in t.wrap(caption, 13, text_w):
                t.text(surf, line, 13, t.MUTED, center=(rx, y))
                y += 19
        else:
            fx.icon(surf, "wifi_off", (rx, 140), 40, t.MUTED)
            t.text(surf, "No download", 14, t.INK, "semibold", center=(rx, 180))
            for i, line in enumerate(t.wrap("Booth is offline. Use Save instead.", 13, text_w)):
                t.text(surf, line, 13, t.MUTED, center=(rx, 204 + i * 19))

        if self.toast:
            fx.pill(surf, self.toast, 15, (W // 2, 31), bg=(*t.INK, 245))
        for b in self.widgets():
            b.draw(surf)
        if self.confetti:
            self.confetti.draw(surf)


class ThanksScreen(Screen):
    idle_resets = False
    SECONDS = 3.5

    def enter(self) -> None:
        self.t = 0.0
        self.confetti = fx.Confetti(self.app.size, 40) if self.app.effects else None
        self.heart = fx.gradient_icon("favorite", 60)
        self.app.indicators.ready()

    def on_tap(self, pos) -> None:
        self.app.go_welcome()

    def on_input(self, event) -> None:
        self.app.go_welcome()

    def update(self, dt) -> None:
        self.t += dt
        if self.confetti:
            self.confetti.update(dt)
        if self.t >= self.SECONDS:
            self.app.go_welcome()

    def draw(self, surf) -> None:
        self.app.bg.draw(surf)
        fx.badge(surf, (W // 2, 170), 58)
        beat = 1 + 0.1 * max(0.0, math.sin(self.t * 7))
        img = pygame.transform.rotozoom(self.heart, 0, beat)
        surf.blit(img, img.get_rect(center=(W // 2, 171)))
        t.text(surf, "Thanks for", 24, t.INK, "bold", center=(W // 2, 272))
        t.text(surf, "snapping!", 24, t.INK, "bold", center=(W // 2, 302))
        t.text(surf, "Come back for another round", 14, t.MUTED, center=(W // 2, 338))

        bar = pygame.Rect(W // 2 - 50, 410, 100, 6)
        fx.rrect(surf, bar, 3, t.LINE)
        filled = bar.copy()
        filled.w = max(6, int(bar.w * fx.clamp01(self.t / self.SECONDS)))
        fx.rrect(surf, filled, 3, t.ACCENT)
        if self.confetti:
            self.confetti.draw(surf)
