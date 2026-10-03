from __future__ import annotations

import logging
import re
import socket
import threading

from flask import Flask, abort, render_template_string, request, send_file
from werkzeug.serving import make_server

from booth.config import ShareConfig
from booth.storage import SHEET, STRIP, SessionStore

log = logging.getLogger(__name__)

ALLOWED_FILE = re.compile(r"^(strip|print_4x6|photo_\d{1,2})\.jpg$")

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ brand }}</title>
<style>
  body{margin:0;font-family:system-ui,sans-serif;background:#fafafa;color:#1e1e1e;text-align:center}
  header{padding:20px 16px 4px;font-weight:700;letter-spacing:.04em}
  main{padding:8px 16px 40px;max-width:480px;margin:auto}
  .strip{max-width:100%;max-height:70vh;box-shadow:0 4px 18px rgba(0,0,0,.15);background:#fff}
  .btn{display:block;margin:12px 0;padding:14px;border-radius:12px;background:#e9546e;color:#fff;
       text-decoration:none;font-weight:600}
  .btn.alt{background:#fff;color:#1e1e1e;border:1px solid #ddd}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}
  .grid img{width:100%;border-radius:8px}
  p.tip{color:#777;font-size:.9em}
</style></head><body>
<header>{{ brand }}</header>
<main>
  {% if session %}
    <img class="strip" src="{{ base }}/{{ strip }}" alt="Your photo strip">
    <a class="btn" href="{{ base }}/{{ strip }}?dl=1">Download strip</a>
    <a class="btn alt" href="{{ base }}/{{ sheet }}?dl=1">Download 4x6 print file</a>
    <p class="tip">On iPhone, press and hold a photo, then tap "Save to Photos".</p>
    <div class="grid">
      {% for name in photos %}
        <a href="{{ base }}/{{ name }}?dl=1"><img src="{{ base }}/{{ name }}" alt="Photo"></a>
      {% endfor %}
    </div>
  {% elif missing %}
    <p>This photo link has expired or doesn't exist.</p>
    <p class="tip">Ask at the booth if you need your photos again.</p>
  {% else %}
    <p>Scan the QR code on the booth screen to get your photos.</p>
  {% endif %}
</main></body></html>"""


HOTSPOT_IP = "10.42.0.1"


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet is sent; picks the outbound interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def create_app(store: SessionStore, brand: str) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template_string(PAGE, brand=brand, session=None)

    @app.get("/s/<sid>")
    def session_page(sid: str):
        session = store.get(sid)
        if session is None:
            return render_template_string(PAGE, brand=brand, session=None, missing=True), 404
        return render_template_string(
            PAGE, brand=brand, session=session, base=f"/s/{sid}",
            strip=STRIP, sheet=SHEET, photos=session.photo_names(),
        )

    @app.get("/s/<sid>/<name>")
    def session_file(sid: str, name: str):
        session = store.get(sid)
        if session is None or not ALLOWED_FILE.match(name) or not session.path(name).is_file():
            abort(404)
        return send_file(
            session.path(name),
            mimetype="image/jpeg",
            as_attachment=request.args.get("dl") == "1",
            download_name=f"snipspics_{sid}_{name}",
        )

    return app


class ShareServer:
    def __init__(self, cfg: ShareConfig, store: SessionStore, brand: str):
        self.cfg = cfg
        self._server = make_server("0.0.0.0", cfg.port, create_app(store, brand), threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str | None:
        """None when phones have no way to reach the booth (no hotspot, no network)."""
        if self.cfg.base_url:
            return self.cfg.base_url.rstrip("/")
        # NetworkManager shared mode always gives the Pi this address, and the hotspot
        # has no internet route for local_ip() to discover.
        ip = HOTSPOT_IP if self.cfg.hotspot_ssid else local_ip()
        return None if ip.startswith("127.") else f"http://{ip}:{self.cfg.port}"

    def session_url(self, sid: str) -> str | None:
        base = self.base_url
        return f"{base}/s/{sid}" if base else None

    def start(self) -> None:
        self._thread.start()
        log.info("Share server on %s", self.base_url)

    def stop(self) -> None:
        self._server.shutdown()
