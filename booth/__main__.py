from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Smooth (not blocky) upscaling when the 480x320 UI is shown in a bigger desktop window.
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")

from booth.config import load_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(prog="booth", description="Snips&Pics photobooth")
    parser.add_argument("--config", type=Path, help="path to config.toml")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--mock-camera", action="store_true", help="use a generated test image")
    parser.add_argument("--onboarding", action="store_true", help="show onboarding again")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(args.config)
    if args.fullscreen:
        cfg.screen.fullscreen = True
    if args.mock_camera:
        cfg.camera.backend = "mock"
    if args.onboarding:
        (cfg.data_path / ".onboarded").unlink(missing_ok=True)

    from booth.ui.app import App

    App(cfg).run()


if __name__ == "__main__":
    main()
