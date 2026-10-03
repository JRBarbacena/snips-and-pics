# Plans

This is the brief the app was built from, what is in the tree today, and the work that is still ahead.

## Original brief

Build a photobooth that can move onto a Raspberry Pi, in a language that can talk to the camera and the buttons directly.

From the reference sheet, the layouts to support were items 1, 5, 6, and 8. Card artwork could wait: a plain white design was enough to start, with real templates later.

Features asked for up front:

- A free enhancement step.
- Common filters after the shots.
- A short onboarding guide, allowed to be a draft.
- A way for the guest to leave with a soft copy: a download button, a QR code, or both.

Hardware was narrowed after the first pass. The parts that are actually planned are a **Raspberry Pi Camera Module 3 (Standard)** and a **3.5" TFT touchscreen**. Earlier notes about a Pi Zero 2 W, a thermal receipt printer, and a battery were suggestions, not a parts list. The exact Pi board is still open. The enclosure is a handheld box: camera on the front, screen on the left or right side, shutter on top. It is not a kiosk people walk up to.

Printing, as decided for this project, is a 4×6 JPEG (two strips, cut down the middle) written to a memory card in a layout a Canon SELPHY can browse. A thermal printer stays available in code and stays off unless one is plugged in.

## Built

- Portrait UI at 320×480, sized for the side screen, with Poppins and Material Icons.
- Welcome screen, a three-page how-to on first visit, and a return to Welcome after Thanks.
- Four layouts: Classic 3, Classic 4, Full Bleed, Landscape.
- Mirrored live preview, 3-2-1 countdown, automatic next shot, pose tips.
- Classical auto-enhance, with a switch to turn it off, and eight filters previewed on the first photo.
- Card-design picker. Plain White is selectable. A locked card marks that more designs are coming.
- Session files on disk, a Flask page, and a QR code for phones on the same network.
- Optional second QR that joins a Pi hotspot, plus `scripts/setup_hotspot.sh`.
- Save to `DCIM/100SNIPS/` on a mounted card, with a fallback into `~/Downloads/snips&pics` when no card is present.
- Local `exports/` copy of every 4×6 sheet.
- Desktop stand-in: webcam or `--mock-camera`, mouse as touch, Space as the top button.
- Pi install script, GPIO shutter (and optional back, LED, buzzer), and an optional thermal or file printer.
- Idle warning that sends an abandoned session back to Welcome.

## Still to do

These are the open items from the brief and from the hooks left in the code. They are not started beyond the extension points.

**Card artwork.** Add designs beyond Plain White. The picker, file names, and sizes are already specified in the [tutorial](tutorial.md#adding-a-card-design). Drop PNGs in `assets/designs/<id>/` and list the design in `booth/imaging/designs.py`.

**Stronger enhancement.** The current enhance is fast and offline. A neural step (face restore, upscaling, or a free hosted model) should plug into `ENHANCERS` in `booth/imaging/enhance.py` with the same signature as `auto_enhance`. On a small Pi that work has to run somewhere else: a phone, a machine on the LAN, or a cloud API. Do not assume the booth board can host the model.

**The box itself.** Mount the Camera Module 3 on the front and the TFT on the side, rotate the panel to portrait in the vendor overlay, and wire the top shutter to BCM 17 (or change `[gpio]`). Confirm which Pi board is in the box. If it is a small one, set `[screen] effects = false` and expect enhance to take a moment; the UI already shows a developing screen for that wait.

**Event networking.** On a normal LAN, leave `share.base_url` empty and let the app detect the address. At a site with no Wi-Fi, run `scripts/setup_hotspot.sh` and set the hotspot fields so guests get a join-Wi-Fi QR and then a photo QR. A cloud URL, with `share.public = true`, is the later option for a link that still works after someone leaves. Printed thermal QR codes should stay off until that public URL exists.

**SELPHY pass.** Take a saved card to the printer and confirm `DCIM/100SNIPS/SNIPnnnn.JPG` shows up and prints at 4×6. Adjust roots in `[storage]` if the reader mounts somewhere other than `/media`.

**Onboarding copy.** The three pages are a draft, as originally allowed. Wording and illustrations can change without touching the capture pipeline.

**Thermal printer.** Only if a 58 mm ESC/POS printer is actually added. Set `[printer] backend = "thermal"` and the USB ids. Until then the review screen shows Save, not Print.

## Explicitly out of scope for now

- Running the UI in a browser.
- Enhancement models stored on the booth.
- Accounts, a gallery site, or a payment step.
- A second camera or a DSLR tether.
