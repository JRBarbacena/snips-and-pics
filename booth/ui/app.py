from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pygame
from PIL import Image

from booth.config import Config
from booth.hardware.camera import create_camera
from booth.hardware.indicators import create_indicators
from booth.hardware.inputs import InputManager
from booth.hardware.printer import create_printer
from booth.imaging.designs import DEFAULT as DEFAULT_DESIGN
from booth.imaging.templates import TEMPLATES, Template
from booth.share.server import ShareServer
from booth.storage import Session, SessionStore
from booth.ui import fx
from booth.ui import theme as t

log = logging.getLogger(__name__)

TRANSITION_SECONDS = 0.32
IDLE_WARNING_SECONDS = 10
SWIPE_MIN_PX = 40


@dataclass
class BoothState:
    template: Template = TEMPLATES[0]
    raw: list[Image.Image] = field(default_factory=list)
    enhanced: list[Image.Image] = field(default_factory=list)
    enhance_on: bool = True
    filter_name: str = "original"
    design_id: str = DEFAULT_DESIGN.id
    strip: Image.Image | None = None
    session: Session | None = None

    def new_session(self, template: Template) -> None:
        self.template = template
        self.raw = []
        self.enhanced = []
        self.filter_name = "original"
        self.design_id = DEFAULT_DESIGN.id
        self.strip = None
        self.session = None

    @property
    def base_photos(self) -> list[Image.Image]:
        return self.enhanced if self.enhance_on and self.enhanced else self.raw


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        pygame.init()
        flags = pygame.SCALED | (pygame.FULLSCREEN if cfg.screen.fullscreen else 0)
        self.surface = pygame.display.set_mode((cfg.screen.width, cfg.screen.height), flags)
        pygame.display.set_caption("Snips&Pics")
        if cfg.screen.fullscreen:
            pygame.mouse.set_visible(False)
        self.size = self.surface.get_size()
        self.effects = cfg.screen.effects
        self.bg = fx.Background(self.size, animated=self.effects)

        self.camera = create_camera(cfg.camera, cfg.is_pi)
        self.inputs = InputManager(cfg.capture.hold_seconds)
        if cfg.is_pi:
            try:
                self.inputs.attach_gpio(cfg.gpio)
            except Exception as exc:
                log.warning("GPIO buttons unavailable: %s", exc)
        self.indicators = create_indicators(cfg.gpio, cfg.is_pi)
        self.printer = create_printer(cfg.printer, cfg.data_path)

        self.store = SessionStore(cfg.data_path / "sessions", cfg.storage.keep_sessions)
        self.store.cleanup()
        self.share: ShareServer | None = None
        if cfg.share.enabled:
            try:
                self.share = ShareServer(cfg.share, self.store, cfg.branding.text)
                self.share.start()
            except OSError as exc:
                log.warning("Share server disabled: %s", exc)

        self.jobs = ThreadPoolExecutor(max_workers=1)
        self.state = BoothState()
        self.onboarded_flag = cfg.data_path / ".onboarded"
        self.screen = None
        self._last_activity = time.monotonic()
        self._down_pos: tuple[int, int] | None = None
        self._swallow_release = False
        self._transition: tuple[pygame.Surface, float, str, int] | None = None
        self._dim = pygame.Surface(self.size, pygame.SRCALPHA)
        self._dim.fill((20, 16, 28, 150))

    # --- navigation ----------------------------------------------------------

    def go(self, screen, transition: str | None = "fade", direction: int = 1) -> None:
        if self.screen is not None and transition and self.effects:
            self._transition = (self.surface.copy(), time.monotonic(), transition, direction)
        self.screen = screen
        screen.enter()

    def go_welcome(self, direction: int = -1) -> None:
        from booth.ui.screens import WelcomeScreen

        self.go(WelcomeScreen(self), "slide", direction)

    def go_home(self, direction: int = 1) -> None:
        from booth.ui.screens import HomeScreen

        self.go(HomeScreen(self), "slide", direction)

    # --- loop ----------------------------------------------------------------

    def run(self) -> None:
        from booth.ui.screens import WelcomeScreen

        self.go(WelcomeScreen(self), None)
        clock = pygame.time.Clock()
        running = True
        try:
            while running:
                dt = min(clock.tick(self.cfg.screen.fps) / 1000, 0.1)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
                        running = False
                    elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                        self.inputs.handle_key(event)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._pointer_down(event.pos)
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        self._pointer_up(event.pos)

                self.inputs.update()
                for ev in self.inputs.drain():
                    if self._idle_warning_active():
                        self._touch()
                        continue
                    self._touch()
                    self.screen.on_input(ev)

                remaining = self.cfg.capture.idle_timeout_seconds - (time.monotonic() - self._last_activity)
                if self.screen.idle_resets and remaining <= 0:
                    log.info("Idle timeout, back to welcome")
                    self._touch()
                    self.go_welcome()

                self.screen.poll_job()
                self.bg.update(dt)
                self.screen.update(dt)
                self.screen.draw(self.surface)
                self._draw_transition()
                if self._idle_warning_active():
                    self._draw_idle_warning(remaining)
                pygame.display.flip()
        finally:
            self.shutdown()

    def _touch(self) -> None:
        self._last_activity = time.monotonic()

    def _idle_warning_active(self) -> bool:
        if not self.screen.idle_resets:
            return False
        idle = time.monotonic() - self._last_activity
        return idle > self.cfg.capture.idle_timeout_seconds - IDLE_WARNING_SECONDS

    def _pointer_down(self, pos: tuple[int, int]) -> None:
        if self._idle_warning_active():
            self._swallow_release = True
            self._touch()
            return
        self._touch()
        self._down_pos = pos
        self.screen.on_press(pos)

    def _pointer_up(self, pos: tuple[int, int]) -> None:
        self._touch()
        if self._swallow_release:
            self._swallow_release = False
            return
        start, self._down_pos = self._down_pos, None
        if start is None:
            return
        self.screen.on_release()
        dx, dy = pos[0] - start[0], pos[1] - start[1]
        if abs(dx) > SWIPE_MIN_PX and abs(dx) > abs(dy) * 1.5:
            self.screen.on_swipe(-1 if dx < 0 else 1)
        else:
            self.screen.on_tap(pos)

    def _draw_transition(self) -> None:
        if not self._transition:
            return
        snap, start, kind, direction = self._transition
        p = (time.monotonic() - start) / TRANSITION_SECONDS
        if p >= 1:
            self._transition = None
            return
        e = fx.ease_out(p)
        if kind == "slide":
            w = self.size[0]
            fresh = self.surface.copy()
            x_old = int(-direction * e * w)
            self.surface.blit(snap, (x_old, 0))
            self.surface.blit(fresh, (x_old + direction * w, 0))
        else:
            snap.set_alpha(int(255 * (1 - e)))
            self.surface.blit(snap, (0, 0))

    def _draw_idle_warning(self, remaining: float) -> None:
        self.surface.blit(self._dim, (0, 0))
        w, h = self.size
        box = pygame.Rect(0, 0, 270, 140)
        box.center = (w // 2, h // 2)
        fx.card(self.surface, box, 20, elevation=2)
        t.text(self.surface, "Still there?", 20, t.INK, "bold", center=(box.centerx, box.y + 32))
        t.text(self.surface, f"Going back to start in {max(0, int(remaining) + 1)}", 13, t.MUTED,
               center=(box.centerx, box.y + 62))
        pill = pygame.Rect(0, 0, 190, 34)
        pill.center = (box.centerx, box.y + 104)
        self.surface.blit(fx.gradient_pill(*pill.size), pill)
        t.text(self.surface, "Tap anywhere to stay", 13, t.WHITE, "semibold", center=(pill.centerx, pill.centery + 1))

    def shutdown(self) -> None:
        self.jobs.shutdown(wait=False, cancel_futures=True)
        if self.share:
            self.share.stop()
        self.camera.stop()
        self.inputs.close()
        self.indicators.close()
        pygame.quit()
