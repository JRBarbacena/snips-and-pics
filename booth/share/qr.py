from __future__ import annotations

import qrcode
from PIL import Image


def make_qr(data: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")


def wifi_payload(ssid: str, password: str) -> str:
    def esc(s: str) -> str:
        return "".join("\\" + c if c in '\\;,:"' else c for c in s)

    if password:
        return f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;"
    return f"WIFI:T:nopass;S:{esc(ssid)};;"
