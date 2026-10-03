from __future__ import annotations

import logging

from booth.config import GpioConfig

log = logging.getLogger(__name__)


class Indicators:
    """Status LED and buzzer. All methods are no-ops without hardware."""

    def tick(self) -> None:
        pass

    def shutter(self) -> None:
        pass

    def ready(self) -> None:
        pass

    def busy(self) -> None:
        pass

    def close(self) -> None:
        pass


class GpioIndicators(Indicators):
    def __init__(self, cfg: GpioConfig):
        from gpiozero import LED, Buzzer

        self._led = LED(cfg.led_pin) if cfg.led_pin is not None else None
        self._buzzer = Buzzer(cfg.buzzer_pin) if cfg.buzzer_pin is not None else None

    def tick(self) -> None:
        if self._buzzer:
            self._buzzer.beep(on_time=0.08, off_time=0, n=1, background=True)

    def shutter(self) -> None:
        if self._buzzer:
            self._buzzer.beep(on_time=0.25, off_time=0, n=1, background=True)

    def ready(self) -> None:
        if self._led:
            self._led.on()

    def busy(self) -> None:
        if self._led:
            self._led.blink(on_time=0.2, off_time=0.2, background=True)

    def close(self) -> None:
        for dev in (self._led, self._buzzer):
            if dev:
                dev.close()


def create_indicators(cfg: GpioConfig, is_pi: bool) -> Indicators:
    if not is_pi:
        return Indicators()
    try:
        return GpioIndicators(cfg)
    except Exception as exc:
        log.warning("LED/buzzer unavailable: %s", exc)
        return Indicators()
