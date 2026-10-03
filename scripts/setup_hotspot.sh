#!/usr/bin/env bash
# Turns the Pi's Wi-Fi into an access point so phones can download photos offline.
# Usage: bash scripts/setup_hotspot.sh [SSID] [PASSWORD]
#
# The Pi's built-in Wi-Fi can't be a hotspot and join another network at once.
# While the hotspot is up, the Pi has no internet unless a USB Wi-Fi/Ethernet is added.
set -euo pipefail

SSID="${1:-SnipsPics}"
PASS="${2:-snipspics}"
if [ ${#PASS} -lt 8 ]; then
  echo "Password must be at least 8 characters." >&2
  exit 1
fi

sudo nmcli connection delete SnipsPicsHotspot 2>/dev/null || true
sudo nmcli connection add type wifi ifname wlan0 con-name SnipsPicsHotspot autoconnect yes \
  ssid "$SSID" mode ap 802-11-wireless.band bg ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS"
sudo nmcli connection up SnipsPicsHotspot

cat <<EOF

Hotspot "$SSID" is up. Pi address: 10.42.0.1
Put this in config.toml:

[share]
base_url = "http://10.42.0.1:8000"
hotspot_ssid = "$SSID"
hotspot_password = "$PASS"

Turn off later with: sudo nmcli connection down SnipsPicsHotspot
EOF
