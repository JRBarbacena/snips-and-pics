#!/usr/bin/env bash
# Raspberry Pi OS Bookworm setup. Run from the project folder: bash scripts/install_pi.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# picamera2, OpenCV and pygame come from apt: prebuilt for the Pi, no compiling.
sudo apt update
sudo apt install -y \
  python3-picamera2 python3-opencv python3-pygame python3-gpiozero \
  python3-pil python3-numpy python3-flask python3-qrcode python3-venv python3-usb

python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
# Only needed if a thermal printer is added later.
.venv/bin/pip install python-escpos

if [ ! -f config.toml ]; then
  cp config.example.toml config.toml
  sed -i 's/^fullscreen = false/fullscreen = true/' config.toml
  echo "Created config.toml (fullscreen on)."
fi

echo
echo "Done. Test with:  .venv/bin/python -m booth"
echo "Camera check:     rpicam-hello -t 3000"
