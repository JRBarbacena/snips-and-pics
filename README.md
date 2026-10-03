# Snips&Pics

A photobooth app for the Raspberry Pi with a Camera Module 3 and a 3.5" TFT touchscreen, built as a handheld box: camera on the front, screen mounted portrait (320x480) on the side, shutter button on top.
It's written in Python, and the same code runs on Windows with a webcam for development.

Full write-up:

- [Tutorial](docs/tutorial.md) — guest flow, Windows, the Pi, downloads, and card designs
- [What we used](docs/stack.md) — libraries, Pi packages, and fonts
- [How it works](docs/architecture.md) — screens, session files, and hardware
- [Plans](docs/roadmap.md) — the original brief, what is built, and what is next

## Flow

Welcome screen, then a 3-page how-to (first visit, or tap "How it works"), then pick a layout,
then a live preview. Press the button to start a 3-2-1 countdown; the app takes 3 or 4 photos.
Next it auto-enhances them, you pick a filter, then a card design, and the app builds the strip. A Thanks screen
follows, then it returns to the Welcome screen for the next guest. Idle guests get a
"Still there?" warning, then go back to Welcome.

Touch: tap, or swipe in onboarding, the layout picker and the filter preview.
Set `effects = false` under `[screen]` if animations stutter on a slow Pi.

On the final screen you can:

- **Download:** scan the QR code on screen to open the photos on your phone.
- **Save to card:** writes a 4x6 print file (two strips, cut down the middle) to a USB card reader,
  in `DCIM/100SNIPS/`, ready for a Canon SELPHY.
- **Retake** or **Done**.

Layouts: Classic 3, Classic 4, Full Bleed, Landscape (references 1, 5, 6 and 8).
Filters: Original, Vivid, Warm, Cool, B&W, Noir, Sepia, Vintage.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m booth
```

Options: `--mock-camera` (no webcam needed), `--onboarding` (show onboarding again),
`--fullscreen`, `--config path\to\config.toml`.

Controls: mouse = touch, `Space` = shutter button (hold 1.5 s = retake), `Esc` = back, `Ctrl+Q` = quit.

Phones on the same Wi-Fi as the PC can scan the QR to test downloads.

## Run on the Pi

```bash
bash scripts/install_pi.sh
bash scripts/setup_hotspot.sh SnipsPics yourpassword   # optional, for offline downloads
.venv/bin/python -m booth
```

Set up the touchscreen with its vendor's driver first, so the desktop shows on it and touch works.
The app then runs fullscreen at 320x480 (portrait). Rotate the display to portrait in the TFT driver overlay (for example `rotate=0` or `rotate=180` on the common `piscreen`/`waveshare35a` overlays; the right value depends on how the panel sits in the box).

Default GPIO pins (BCM numbering), all optional: shutter button 17, back button 27, LED 22, buzzer 23.
Wire the buttons between the pin and GND; no resistors are needed.

## Card designs

Only "Plain White" ships today. To add one, list it in `booth/imaging/designs.py` and drop artwork in
`assets/designs/<design_id>/`, one pair of files per layout:

- `<layout>_background.png`, drawn under the photos
- `<layout>_overlay.png`, drawn over them, with transparent holes where the photos show

Layout names are `classic3`, `classic4`, `fullbleed3` and `landscape3`. Artwork is 600x1800, or 1800x600 for `landscape3`.

## Configuration

Copy `config.example.toml` to `config.toml`. Every key is documented there.

## Layout

```
booth/
  hardware/   camera, buttons, LED/buzzer, printer (Pi or desktop versions)
  imaging/    templates, filters, enhance, thermal, 4x6 export
  share/      phone download web server, QR codes
  ui/         pygame screens
  storage.py  sessions on disk, export to card
scripts/      Pi install and hotspot setup
assets/fonts/ Poppins (SIL OFL) and Material Icons Round (Apache 2.0); licenses alongside
```

Icons are Material Icons Round glyphs referenced by name (see `MaterialIconsRound-Regular.codepoints`),
e.g. `Button(..., icon="photo_camera")`. Browse names at https://fonts.google.com/icons.
