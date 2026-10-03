# Tutorial

This guide has two parts. The first is the guest path, the way someone uses the box. The second is the operator path: install, run, download photos, and save a print file.

## Guest path

The screen is portrait. Touch works with a finger on the Pi and with the mouse on Windows. The physical shutter on top does the main action on every screen (on Windows, that key is Space or Enter).

1. **Welcome.** The booth shows the Snips&Pics mark and “Tap or press to start”. Tap the screen or press the top button. “How it works” opens the guide without starting a session.
2. **How it works.** The first visit always shows three pages. Later visits skip them unless someone taps “How it works”, or you start the app with `--onboarding`.
   - Pick a layout.
   - Strike a pose and wait through the countdown.
   - Pick a filter and a design, then scan the QR code.
   Swipe sideways, or use Back and Next. Skip jumps straight to the layout picker. Finishing this guide writes `data/.onboarded` so the next guest starts faster.
3. **Pick a layout.** Swipe the cards. Four layouts ship:
   - **Classic 3** — three stacked photos, brand on top, date on the bottom. 2×6 in.
   - **Classic 4** — four stacked photos. 2×6 in.
   - **Full Bleed** — three edge-to-edge photos. 2×6 in.
   - **Landscape** — three photos in a row. 6×2 in.
   Tap Start, tap the center card, or press the top button.
4. **Live preview.** The camera is mirrored, like a phone selfie camera. Press the top button or tap the prompt. A 3-2-1 countdown runs, the shutter fires, then the next countdown starts on its own until the layout has all of its photos. The X (or Esc) cancels and returns to the layout picker. Hold still; the gap between shots is about 2.5 seconds.
5. **Developing.** The booth enhances the set (white balance, local contrast, a light smooth, then a sharpen). This screen cannot be skipped.
6. **Filter.** The first photo previews the look. Swipe, or tap the small arrows beside the name. Choices: Original, Vivid, Warm, Cool, B&W, Noir, Sepia, Vintage. “Auto enhance” can be turned off if the raw shots are preferred. Retake throws the set away and goes back to the camera. Next continues.
7. **Card design.** Swipe the designs. **Plain White** is the only finished design. The last card is locked and labeled “Coming soon”. Create builds the strip.
8. **Your photos.** The strip sits on the left. On the right:
   - If the booth has a network address, a QR code opens the photos on a phone.
   - If a hotspot name is configured, the first QR joins that Wi-Fi and the second QR opens the photos. Swipe or tap the tabs to switch.
   - If the booth is offline, the screen says so and Save is the way to keep the pictures.
   **Save** writes a 4×6 print file. With a memory card mounted, that file lands in `DCIM/100SNIPS/` for a Canon SELPHY. With no card, the strip, the 4×6 sheet, and the separate photos go to the downloads folder. **Retake** starts the same layout again. **Done** continues. Hold the top button for about 1.5 seconds to retake from this screen. A short press Saves when no printer is configured.
   If a printer backend is turned on, a **Print** button appears and a short press prints instead.
9. **Thanks.** “Thanks for snapping!” stays for about 3.5 seconds, then the booth returns to Welcome. A tap skips the wait.

If a guest walks away mid-session, a “Still there?” card appears in the last 10 seconds of the idle timer (90 seconds by default). Tap anywhere to stay. Otherwise the booth returns to Welcome. Welcome, the how-to, the developing screen, and Thanks do not use this timer.

## Run it on Windows

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m booth
```

Python 3.11 or newer is required. The development machine used for this project is Python 3.13.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--mock-camera` | Animated test image. No webcam needed. |
| `--onboarding` | Show the how-to again, even if it was finished before. |
| `--fullscreen` | Fill the monitor. The mouse cursor hides. |
| `--config path\to\config.toml` | Use a config file other than `config.toml`. |
| `-v` | Debug logging. |

Desktop controls:

| Input | Action |
| --- | --- |
| Mouse click | Tap |
| Mouse drag sideways | Swipe (layout picker, how-to, filters, QR tabs) |
| Space or Enter | Shutter. Hold about 1.5 seconds for retake where that applies. |
| Esc or Backspace | Back |
| Ctrl+Q | Quit |

The window is 320×480, the same pixels as the side screen on the box. On a normal monitor pygame scales it up smoothly.

Phones on the same Wi-Fi as the PC can scan the QR code on the review screen. The PC must allow inbound connections on port 8000.

## Run it on the Raspberry Pi

Set up the 3.5" TFT with its vendor driver first, so the desktop appears on that panel and touch works. Rotate the panel to portrait in the driver overlay. Common Waveshare and PiScreen overlays use `rotate=0` or `rotate=180`; the right value depends on which way the panel sits in the box. The app then draws fullscreen at 320×480.

On Raspberry Pi OS Bookworm, from the project folder:

```bash
bash scripts/install_pi.sh
.venv/bin/python -m booth
```

The install script uses apt packages for the camera, OpenCV, pygame, GPIO, Pillow, Flask, and QR codes, then creates a virtual environment that can see those system packages. It also installs `python-escpos` for a thermal printer you might add later, and it turns fullscreen on in `config.toml` the first time that file is created.

Check the Camera Module 3 on its own before blaming the app:

```bash
rpicam-hello -t 3000
```

### Buttons, light, and buzzer

All of these are optional. BCM pin numbers, wire each button between the pin and GND. Internal pull-ups are on, so no extra resistors are required.

| Part | Default BCM pin |
| --- | --- |
| Shutter (top of the box) | 17 |
| Back | 27 |
| Status LED | 22 |
| Buzzer | 23 |

The LED stays on when the booth is waiting and blinks while a job is running. The buzzer ticks on each countdown second and sounds again when a photo is taken.

### Downloads with no venue Wi-Fi

The Pi’s built-in Wi-Fi can be a hotspot or join another network, not both at once. While the hotspot is up, the Pi has no internet unless you add Ethernet or a second Wi-Fi adapter.

```bash
bash scripts/setup_hotspot.sh SnipsPics yourpassword
```

The password must be at least 8 characters. The script prints the lines to put in `config.toml`:

```toml
[share]
base_url = "http://10.42.0.1:8000"
hotspot_ssid = "SnipsPics"
hotspot_password = "yourpassword"
```

Guests then scan “1 Wi-Fi” and “2 Photos” on the review screen. Turn the hotspot off later with:

```bash
sudo nmcli connection down SnipsPicsHotspot
```

## Where the pictures go

Each finished session is a folder under `data/sessions/<id>/`:

| File | Contents |
| --- | --- |
| `photo_1.jpg`, `photo_2.jpg`, … | The shots after the chosen filter |
| `strip.jpg` | The photo strip at 300 dpi |
| `print_4x6.jpg` | Two copies of that strip on one 4×6 sheet, to cut down the middle |

Portrait strips are 600×1800 (2×6 in). Two sit side by side on a 4×6 sheet. The landscape strip is 1800×600 (6×2 in). Two stack on a 6×4 sheet.

**Save** always keeps a copy in `exports/`, named with the time and session id. It also looks for mounted cards under the paths in `removable_media_roots` (default `/media`, which is how Raspberry Pi OS mounts USB readers). A card receives `DCIM/100SNIPS/SNIP0001.JPG`, then `SNIP0002.JPG`, and so on. A Canon SELPHY can browse that folder.

If no card is mounted, Save copies the strip, the 4×6 sheet, and the separate photos into `~/Downloads/snips&pics/<time>_<id>/`. On Windows that is the usual result, because `/media` is not how Windows mounts drives. To write a Windows card reader as well, add its mount path to `removable_media_roots` in `config.toml`.

The booth keeps the newest 200 sessions and deletes older ones. A QR code for a deleted session shows “This photo link has expired”.

## Phone download page

The QR code opens a small page served by the booth itself, for example `http://192.168.1.20:8000/s/<session-id>`.

That page shows the strip and offers:

- Download strip
- Download 4×6 print file
- Each photo, tap to download

On an iPhone, press and hold a photo, then tap “Save to Photos”.

The link only works while the phone can reach the booth: same Wi-Fi, or the booth’s hotspot. It is not a cloud link. Once the guest leaves the network, the QR stops working. A printed thermal QR is only added when `share.public` is true, which you should set only for a URL that stays reachable.

## Configuration

Copy `config.example.toml` to `config.toml`. Every key is optional. Defaults live in `booth/config.py`. The example file comments each setting.

Settings you are most likely to change:

| Key | Why |
| --- | --- |
| `[screen] fullscreen` | `true` on the Pi. The install script sets this. |
| `[screen] effects` | `false` if animations stutter on a slow Pi. |
| `[camera] mirror` | `true` is the selfie mirror. `false` is a normal view. |
| `[camera] backend` | `auto`, `picamera`, `opencv`, or `mock`. |
| `[capture] countdown_seconds` | Length of the 3-2-1. |
| `[capture] idle_timeout_seconds` | How long until “Still there?” sends the guest back. |
| `[share] port` | Download server port, default 8000. |
| `[share] base_url` | Leave empty on a normal LAN. Set it for the hotspot address. |
| `[storage] downloads_dir` | Where Save goes when no card is plugged in. |
| `[branding] text` | Words printed on the strip. Default `snips&pics`. |

`config.toml` is ignored by git so a hotspot password stays on the machine.

## Adding a card design

Only Plain White ships today. To add one:

1. Add a `Design(...)` entry in `booth/imaging/designs.py`.
2. Drop artwork in `assets/designs/<design_id>/`, one pair per layout:
   - `<layout>_background.png` is drawn under the photos.
   - `<layout>_overlay.png` is drawn over them, with transparent holes where the photos show.

Layout file names are `classic3`, `classic4`, `fullbleed3`, and `landscape3`. Artwork is 600×1800, or 1800×600 for `landscape3`. The locked “Coming soon” card disappears from the end of the carousel only when you stop appending it in code; new real designs show up as soon as they are listed in `DESIGNS`.
