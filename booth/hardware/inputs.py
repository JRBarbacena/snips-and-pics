from __future__ import annotations

import logging
import queue
import time
from enum import Enum, auto

import pygame

from booth.config import GpioConfig

log = logging.getLogger(__name__)

SHUTTER_KEYS = (pygame.K_SPACE, pygame.K_RETURN)
BACK_KEYS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)


class InputEvent(Enum):
    SHUTTER = auto()       # short press
    SHUTTER_HOLD = auto()  # held past hold_seconds
    BACK = auto()


class InputManager:
    """Merges keyboard (desktop) and GPIO buttons (Pi) into one event queue.

    GPIO callbacks run on gpiozero threads, so everything goes through a Queue.
    """

    def __init__(self, hold_seconds: float):
        self.hold_seconds = hold_seconds
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._key_down_at: float | None = None
        self._key_hold_fired = False
        self._gpio_hold_fired = False
        self._devices: list = []

    def push(self, event: InputEvent) -> None:
        self._queue.put(event)

    def drain(self) -> list[InputEvent]:
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                return events

    def handle_key(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in SHUTTER_KEYS and self._key_down_at is None:
                self._key_down_at = time.monotonic()
                self._key_hold_fired = False
            elif event.key in BACK_KEYS:
                self.push(InputEvent.BACK)
        elif event.type == pygame.KEYUP and event.key in SHUTTER_KEYS:
            if self._key_down_at is not None and not self._key_hold_fired:
                self.push(InputEvent.SHUTTER)
            self._key_down_at = None

    def update(self) -> None:
        if (
            self._key_down_at is not None
            and not self._key_hold_fired
            and time.monotonic() - self._key_down_at >= self.hold_seconds
        ):
            self._key_hold_fired = True
            self.push(InputEvent.SHUTTER_HOLD)

    def attach_gpio(self, cfg: GpioConfig) -> None:
        from gpiozero import Button

        shutter = Button(cfg.shutter_pin, pull_up=True, bounce_time=0.05,
                         hold_time=self.hold_seconds)
        shutter.when_pressed = self._gpio_pressed
        shutter.when_held = self._gpio_held
        shutter.when_released = self._gpio_released
        self._devices.append(shutter)

        if cfg.back_pin is not None:
            back = Button(cfg.back_pin, pull_up=True, bounce_time=0.05)
            back.when_pressed = lambda: self.push(InputEvent.BACK)
            self._devices.append(back)
        log.info("GPIO buttons attached (shutter=%s back=%s)", cfg.shutter_pin, cfg.back_pin)

    def _gpio_pressed(self) -> None:
        self._gpio_hold_fired = False

    def _gpio_held(self) -> None:
        self._gpio_hold_fired = True
        self.push(InputEvent.SHUTTER_HOLD)

    def _gpio_released(self) -> None:
        if not self._gpio_hold_fired:
            self.push(InputEvent.SHUTTER)

    def close(self) -> None:
        for dev in self._devices:
            dev.close()
