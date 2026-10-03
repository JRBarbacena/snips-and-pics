# What we used

Python is the whole application. It talks to a Raspberry Pi camera, GPIO, and a touchscreen without a separate service, and the same code runs on Windows for day-to-day work. The code targets Python 3.11 or newer so it matches Raspberry Pi OS Bookworm. Development on this project used Python 3.13.

## Application libraries

These are installed from `requirements.txt` on Windows, and from apt on the Pi (see `scripts/install_pi.sh`).

| Piece | Role |
| --- | --- |
| **pygame** 2.5+ | The whole touch UI. A browser kiosk was rejected because a 3.5" panel, especially on a small Pi, cannot spare the memory Chromium wants. The window is the panel’s real size, 320×480, and `pygame.SCALED` enlarges it on a desktop monitor. |
| **Pillow** | Strips, filters, QR images, JPEG export, and the 4×6 sheet. |
| **NumPy** | Filter math and camera frames. |
| **OpenCV** (`opencv-python`) | Webcam capture on Windows (DirectShow). On every platform it also does the auto-enhance steps and preview scaling. On the Pi, OpenCV comes from apt as `python3-opencv`. |
| **Flask** | The phone download site, one process inside the booth, bound to `0.0.0.0` so a phone on the LAN can reach it. |
| **qrcode** | The photo QR and the Wi-Fi join QR. |
| **tomllib** | Standard-library TOML reader for `config.toml`. No extra config package. |

## Pi-only packages

These are not in `requirements.txt`. They come from Raspberry Pi OS so they match the camera stack and do not need a compiler on the board.

| Package | Role |
| --- | --- |
| **picamera2** and **libcamera** | Camera Module 3. Continuous autofocus is requested when the sensor supports it. picamera2’s `RGB888` frames are BGR in memory, so the app converts them before display. |
| **gpiozero** | Shutter, optional back button, LED, and buzzer. Callbacks arrive on another thread and are queued into the pygame loop. |
| **python3-usb** | USB access used by the thermal printer library. |
| **python-escpos** | Optional 58 mm ESC/POS thermal printer. The install script adds it. The default printer backend is `none`, because the print path for this project is a 4×6 JPEG on a card for a Canon SELPHY, not a receipt printer. |

If the chosen camera fails to open, the app logs a warning and falls back to a generated test image so the UI can still be tried.

## Fonts and icons

The UI does not draw its own bitmap letters.

| Asset | License | Use |
| --- | --- | --- |
| Poppins (Regular, Medium, SemiBold, Bold) | SIL Open Font License. Text is in `assets/fonts/Poppins-OFL.txt`. | All on-screen type. |
| Material Icons Round | Apache 2.0. Text is in `assets/fonts/MaterialIcons-LICENSE.txt`. | Icons by glyph name, for example `photo_camera`. The name list is `MaterialIconsRound-Regular.codepoints`. Browse names at [Google Fonts Icons](https://fonts.google.com/icons). |

Text burned into the photo strip (the brand and the date) uses a bold system font: DejaVu Sans, Arial, or Liberation Sans, whichever is installed. Those faces are already on Raspberry Pi OS and on Windows.

## What “enhancement” is

The enhance step is classical image processing, chosen so it runs on a small board with no GPU and no network:

1. Gray-world white balance, applied part-way so skin does not swing wildly.
2. Local contrast (CLAHE on the L channel).
3. A light bilateral smooth.
4. An unsharp mask.

Face-restore and upscaling models were left out on purpose. They do not fit a board in the Pi Zero 2 W class (512 MB, no useful GPU), which was the conservative target while the exact Pi model was still open. The function is registered in `ENHANCERS` in `booth/imaging/enhance.py` so a later model, phone offload, or cloud call can be added with the same input and output: one PIL image in, one PIL image out.

## Filters

Filters are Pillow and NumPy, applied after enhance (unless the guest turns enhance off):

| Name | What it does |
| --- | --- |
| Original | Unchanged |
| Vivid | Higher color and a little more contrast |
| Warm | Lift red, pull blue |
| Cool | Pull red, lift blue |
| B&W | Grayscale |
| Noir | Autocontrast grayscale, then stronger contrast |
| Sepia | Standard sepia matrix |
| Vintage | Partial sepia, lifted blacks, vignette |

## Platform split

`booth/config.py` reads `/proc/device-tree/model`. If that file contains “raspberry pi”, the app picks the Pi camera, GPIO buttons, and GPIO LED/buzzer. Everywhere else it picks the webcam and the keyboard. You can force this with `platform = "pi"` or `platform = "desktop"` in `config.toml`.

Hardware calls sit behind small interfaces in `booth/hardware/`:

| Interface | Pi | Windows |
| --- | --- | --- |
| Camera | picamera2 | OpenCV webcam, or `--mock-camera` |
| Buttons | gpiozero | Space, Enter, Esc, Backspace |
| LED and buzzer | gpiozero | No-ops |
| Printer | `none`, `thermal` (USB ESC/POS), or `file` | `none` or `file` (PNG preview in `data/print_preview`) |
