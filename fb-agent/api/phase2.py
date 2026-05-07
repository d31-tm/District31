"""
D31 Facebook Marketing Agent — Phase 2
Receives club data + Zeffy URL, then:
  Step 3 — Generates a QR code PNG (Python qrcode library)
  Step 4 — Composites a flyer PNG (Python Pillow onto flyer_template.png)
  Step 5 — Posts the flyer to the District 31 Facebook Page (Graph API)

Vercel environment variables required:
  FACEBOOK_PAGE_TOKEN  — Long-lived Page Access Token (~60-day expiry)
  FACEBOOK_PAGE_ID     — Numeric Facebook Page ID

Static assets (committed to repo, served from /static/):
  flyer_template.png   — Base flyer design
  Montserrat-Bold.ttf  — Font for club name and date/time
  Montserrat-Regular.ttf — Font for address and body text

TEXT COORDINATES — pixel positions on flyer_template.png
  Recalibrate these if the template image dimensions or layout change.

  CLUB_NAME_XY       = (120, 340)
  DATETIME_XY        = (120, 500)
  BOTTOM_DATETIME_XY = (120, 1050)
  BOTTOM_ADDRESS_XY  = (120, 1100)
  QR_XY              = (780, 1000)
"""

import os
import io
import json
import base64
import traceback
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# -- Asset paths ---------------------------------------------------------------

STATIC_DIR    = Path(__file__).parent.parent / "static"
TEMPLATE_PATH = STATIC_DIR / "flyer_template.png"
FONT_BOLD     = STATIC_DIR / "Montserrat-Bold.ttf"
FONT_REGULAR  = STATIC_DIR / "Montserrat-Regular.ttf"

# -- Layout constants ----------------------------------------------------------

CLUB_NAME_XY       = (120, 340)
DATETIME_XY        = (120, 500)
BOTTOM_DATETIME_XY = (120, 1050)
BOTTOM_ADDRESS_XY  = (120, 1100)
QR_XY              = (780, 1000)
QR_SIZE            = 250
MAX_TEXT_WIDTH     = 600

CLUB_NAME_FONT_SIZE   = 52
DATETIME_FONT_SIZE    = 36
BOTTOM_TEXT_FONT_SIZE = 28

COLOR_DARK = (30,  30,  30)
COLOR_GOLD = (212, 175, 55)

FB_API_VERSION = "v18.0"
FB_GRAPH_BASE  = f"https://graph.facebook.com/{FB_API_VERSION}"


# -- Step 3: QR Code -----------------------------------------------------------

def generate_qr(zeffy_url):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(zeffy_url)
    qr.make(fit=True)
    from PIL import Image
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
    return img


# -- Step 4: Flyer -------------------------------------------------------------

def generate_flyer(club, zeffy_url, qr_img):
    from PIL import Image, ImageDraw, ImageFont

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"flyer_template.png not found at {TEMPLATE_PATH}. "
            f"Files in static/: {list(STATIC_DIR.iterdir()) if STATIC_DIR.exists() else 'static/ dir missing'}"
        )

    flyer = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw  = ImageDraw.Draw(flyer)

    if FONT_BOLD.exists():
        font_club     = ImageFont.truetype(str(FONT_BOLD), CLUB_NAME_FONT_SIZE)
        font_datetime = ImageFont.truetype(str(FONT_BOLD), DATETIME_FONT_SIZE)
    else:
        font_club = font_datetime = ImageFont.load_default()

    if FONT_REGULAR.exists():
        font_bottom = ImageFont.truetype(str(FONT_REGULAR), BOTTOM_TEXT_FONT_SIZE)
    else:
        font_bottom = ImageFont.load_default()

    # Club name
    words = club["club_name"].upper().split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font_club)
        if bbox[2] > MAX_TEXT_WIDTH and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    x, y = CLUB_NAME_XY
    for line in lines:
        draw.text((x, y), line, font=font_club, fill=COLOR_DARK)
        y += font_club.size + 8

    # Date/time
    draw.text(DATETIME_XY, club["day_time"], font=font_datetime, fill=COLOR_DARK)

    # Bottom section
    draw.text(BOTTOM_DATETIME_XY, club["day_time"], font=font_bottom, fill=COLOR_GOLD)
    draw.text(BOTTOM_ADDRESS_XY,  club["address"],  font=font_bottom, fill=COLOR_GOLD)

    # QR code
    flyer.paste(qr_img, QR_XY)

    buf = io.BytesIO()
    flyer.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# -- Step 5: Facebook ----------------------------------------------------------

def post_to_facebook(flyer_bytes, club, zeffy_url):
    page_token = os.environ["FACEBOOK_PAGE_TOKEN"]
    page_id    = os.environ["FACEBOOK_PAGE_ID"]

    caption = (
        f"You are invited! Join us at {club['club_name']}!\n\n"
        f"Meeting: {club['day_time']}\n"
        f"Location: {club['address']}\n\n"
        f"Register here: {zeffy_url}\n\n"
        f"#Toastmasters #District31 #PublicSpeaking #Leadership"
    )

    boundary = "----D31FlyerBoundary"
    body_parts = []
    for key, val in {"caption": caption, "access_token": page_token}.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{val}\r\n"
        )
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="source"; filename="flyer.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    )
    body = (
        "".join(body_parts).encode("utf-8")
        + flyer_bytes
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    url = f"{FB_GRAPH_BASE}/{page_id}/photos"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())

    post_id = result.get("post_id") or result.get("id")
    return f"https://www.facebook.com/{post_id}"


# -- Vercel handler ------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length  = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode())

            zeffy_url = payload["zeffy_url"]
            club      = payload["club"]

            qr_img      = generate_qr(zeffy_url)
            flyer_bytes = generate_flyer(club, zeffy_url, qr_img)
            flyer_b64   = base64.b64encode(flyer_bytes).decode()
            fb_url      = post_to_facebook(flyer_bytes, club, zeffy_url)

            self._respond(200, {"ok": True, "flyer_b64": flyer_b64, "facebook_url": fb_url})

        except Exception as e:
            err_msg = str(e)
            tb      = traceback.format_exc()
            if "token" in err_msg.lower() or "oauth" in err_msg.lower() or "190" in err_msg:
                err_msg += " — Facebook token may be expired. Regenerate in Meta Developer Portal and update FACEBOOK_PAGE_TOKEN in Vercel."
            self._respond(500, {"ok": False, "error": err_msg, "traceback": tb})

    def _respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
