# How it works

```
booth/
  hardware/    camera, buttons, LED and buzzer, printer
  imaging/     layouts, designs, filters, enhance, thermal bitmap, 4x6 sheet
  share/       download server and QR codes
  ui/          pygame loop, screens, widgets, motion
  config.py    TOML settings and platform detection
  storage.py   session folders and card export
scripts/       Pi install and hotspot setup
assets/fonts/  Poppins and Material Icons Round
```

`python -m booth` loads config, then `booth.ui.app.App` owns the pygame window, the camera, inputs, the session store, and the download server. One screen object is current. It receives taps, swipes, and shutter or back events, then draws into a 320×480 surface.

## Screen flow

```
Welcome
  ├─ first visit, or "How it works" → Onboarding → Layout picker
  └─ later visits → Layout picker
        → Capture (countdown, N photos)
        → Processing (auto enhance)
        → Filter
        → Card design
        → Processing (compose strip, write session)
        → Review (QR, Save, Retake, Done)
        → Thanks
        → Welcome
```

Idle timeout sends most of those screens back to Welcome. Capture can cancel to the layout picker. Filter and Review can retake into Capture with the same layout. Design can step back to Filter.

Swipe is a horizontal drag of at least 40 pixels that is clearly more horizontal than vertical. It moves the how-to, the layout carousel, the filter, the design carousel, and the Wi-Fi / Photos QR tabs.

Animations (slides, fades, confetti, the welcome background) follow `[screen] effects`. Set that to false on a board that drops frames. The booth still works; it just cuts the motion.

## A finished session

When the guest taps Create, the app:

1. Applies the chosen filter to each photo.
2. Composes them into the layout with the chosen design, the branding text, and today’s date.
3. Creates a session id (URL-safe, 10 characters) and writes JPEGs under `data/sessions/<id>/`.
4. Builds the review screen. The QR target is `{base_url}/s/{id}`.

`base_url` is, in order:

- `share.base_url` if you set it (use this for the hotspot, `http://10.42.0.1:8000`).
- `http://10.42.0.1:8000` when a hotspot SSID is set but `base_url` is empty.
- `http://<lan-ip>:8000`, discovered by opening a UDP socket toward `8.8.8.8` (no packet is sent; this only picks the outbound interface).
- Nothing, if the only address is loopback. The review screen then shows “No download” and Save is the copy the guest can take.

The download server allows only `strip.jpg`, `print_4x6.jpg`, and `photo_N.jpg`. Other names 404. Session ids that are the wrong shape never touch the filesystem.

## Layouts

Defined in `booth/imaging/templates.py`. Portrait strips are 600×1800 pixels (2×6 in at 300 dpi). Landscape is 1800×600 (6×2 in).

| Id | On-screen name | Photos | Notes |
| --- | --- | --- | --- |
| `classic3` | Classic 3 | 3 | Inset frames, brand above, date below |
| `classic4` | Classic 4 | 4 | Same idea, four frames |
| `fullbleed3` | Full Bleed | 3 | Frames run to the left and right edges |
| `landscape3` | Landscape | 3 | Brand and date rotated along the right edge |

These four are the styles picked from the reference sheet (items 1, 5, 6, and 8). A design can replace the white paper. `booth/imaging/designs.py` looks up:

```
assets/designs/<design_id>/<template_id>_background.png
assets/designs/<design_id>/<template_id>_overlay.png
```

Missing files mean a flat paper color. Plain White ships with no artwork files.

`booth/imaging/export.py` places two copies of the strip on one sheet so a 4×6 printer can cut them apart.

## Hardware boundary

Nothing in the screens imports picamera2 or gpiozero directly. `create_camera`, `InputManager.attach_gpio`, `create_indicators`, and `create_printer` pick an implementation from config and platform. On the desktop, GPIO attach is skipped. If GPIO attach throws on a Pi, the app logs it and keeps running with touch and the keyboard.

The physical box:

| Face | What is there |
| --- | --- |
| Front | Camera Module 3 (Standard), aimed at the group |
| Left or right | 3.5" TFT, mounted portrait. The panel itself is 480×320; the driver overlay rotates it. |
| Top | Shutter button |

An optional second button, LED, and buzzer use the pins in `[gpio]`.

## Printing

Two different “print” ideas exist, and only one is the current plan.

**Save to card** is the path for a Canon SELPHY. The review screen’s Save button writes `print_4x6.jpg` onto a mounted card as `DCIM/100SNIPS/SNIPnnnn.JPG`. The SELPHY reads that like a camera card.

**Thermal** is optional and off by default (`[printer] backend = "none"`). `thermal` sends a dithered, printer-width bitmap over USB ESC/POS (`python-escpos`). `file` writes that same bitmap to `data/print_preview` so the layout can be checked without hardware. A QR is added to a thermal print only when `share.public` is true, because a hotspot URL is useless after the guest walks away.
