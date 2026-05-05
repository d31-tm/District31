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
  flyer_template.png   — Base flyer design with blank zones for variable content
  Montserrat-Bold.ttf  — Font for club name and date/time
  Montserrat-Regular.ttf — Font for address and body text

⚠ TEXT COORDINATES — pixel positions on flyer_template.png (1080×1350 px assumed)
  These must be recalibrated if the template image dimensions or layout change.
  All coordinates are (x, y) from top-left corner.

  CLUB_NAME_XY      = (120, 340)   ← large bold text, yellow bubble zone
  DATETIME_XY       = (120, 500)   ← date + time line, yellow bubble zone
  BOTTOM_DATETIME_XY= (120, 1050)  ← gold text, bottom section
  BOTTOM_ADDRESS_XY = (120, 1100)  ← gold text, bottom section
  QR_XY             = (780, 1000)  ← bottom right quadrant, 250×250 px

  ⚠ Calibrate these against the actual template PNG before first deploy.
     Add a calibration helper at the bottom of this file if needed.
"""

import os
import io
import json
import base64
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw, ImageFont

# ── Asset paths ───────────────────────────────────────────────────────────────

STATIC_DIR    = Path(__file__).parent.parent / "static"
TEMPLATE_PATH = STATIC_DIR / "flyer_template.png"
FONT_BOLD     = STATIC_DIR / "Montserrat-Bold.ttf"
FONT_REGULAR  = STATIC_DIR / "Montserrat-Regular.ttf"

# ── Layout constants (recalibrate against actual template) ────────────────────

CLUB_NAME_XY       = (120, 340)
DATETIME_XY        = (120, 500)
BOTTOM_DATETIME_XY = (120, 1050)
BOTTOM_ADDRESS_XY  = (120, 1100)
QR_XY              = (780, 1000)
QR_SIZE            = 250          # pixels — QR pasted at this size
MAX_TEXT_WIDTH     = 600          # pixels — club name wraps beyond this

CLUB_NAME_FONT_SIZE    = 52
DATETIME_FONT_SIZE     = 36
BOTTOM_TEXT_FONT_SIZE  = 28

COLOR_DARK  = (30,  30,  30)   # near-black for club name / datetime
COLOR_GOLD  = (212, 175, 55)   # gold for bottom date/address lines

# ── Facebook Graph API ────────────────────────────────────────────────────────

FB_API_VERSION = "v18.0"
FB_GRAPH_BASE  = f"https://graph.facebook.com/{FB_API_VERSION}"


# ── Step 3: QR Code ───────────────────────────────────────────────────────────

def generate_qr(zeffy_url: str) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,                    # auto-size
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(zeffy_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
    return img


# ── Step 4: Flyer ─────────────────────────────────────────────────────────────

def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _draw_text_wrapped(draw, text, xy, font, fill, max_width):
    """Draw text, wrapping at max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    x, y = xy
    line_height = font.size + 8
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def generate_flyer(club: dict, zeffy_url: str, qr_img: Image.Image) -> bytes:
    # Load template
    flyer = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw  = ImageDraw.Draw(flyer)

    # Load fonts
    font_club     = _load_font(FONT_BOLD,    CLUB_NAME_FONT_SIZE)
    font_datetime = _load_font(FONT_BOLD,    DATETIME_FONT_SIZE)
    font_bottom   = _load_font(FONT_REGULAR, BOTTOM_TEXT_FONT_SIZE)

    # Club name (wrapping, dark color, yellow bubble zone)
    _draw_text_wrapped(
        draw, club["club_name"].upper(),
        CLUB_NAME_XY, font_club, COLOR_DARK, MAX_TEXT_WIDTH
    )

    # Date + time (yellow bubble zone)
    draw.text(DATETIME_XY, club["day_time"], font=font_datetime, fill=COLOR_DARK)

    # Bottom section — date/time and address (gold)
    draw.text(BOTTOM_DATETIME_XY, club["day_time"],  font=font_bottom, fill=COLOR_GOLD)
    draw.text(BOTTOM_ADDRESS_XY,  club["address"],   font=font_bottom, fill=COLOR_GOLD)

    # Paste QR code
    flyer.paste(qr_img, QR_XY)

    # Convert to PNG bytes
    buf = io.BytesIO()
    flyer.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Step 5: Facebook Post ─────────────────────────────────────────────────────

def post_to_facebook(flyer_bytes: bytes, club: dict, zeffy_url: str) -> str:
    page_token = os.environ["FACEBOOK_PAGE_TOKEN"]
    page_id    = os.environ["FACEBOOK_PAGE_ID"]

    caption = (
        f"You are invited! Join us at {club['club_name']}!\n\n"
        f"📅 Meeting: {club['day_time']}\n"
        f"📍 Location: {club['address']}\n\n"
        f"Register here: {zeffy_url}\n\n"
        f"#Toastmasters #District31 #PublicSpeaking #Leadership"
    )

    # Upload photo with caption
    url    = f"{FB_GRAPH_BASE}/{page_id}/photos"
    fields = {
        "caption":      caption,
        "access_token": page_token,
    }

    # Multipart form upload
    boundary = "----D31FlyerBoundary"
    body_parts = []
    for key, val in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{val}\r\n"
        )
    # Attach image
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


# ── Vercel handler ────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        self.send_header("Access-Control-Allow-Origin", "*")

        try:
            length  = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode())

            zeffy_url = payload["zeffy_url"]
            club      = payload["club"]          # club object from Phase 1

            # Step 3 — QR Code
            qr_img = generate_qr(zeffy_url)

            # Step 4 — Flyer
            flyer_bytes = generate_flyer(club, zeffy_url, qr_img)
            flyer_b64   = base64.b64encode(flyer_bytes).decode()

            # Step 5 — Facebook
            fb_url = post_to_facebook(flyer_bytes, club, zeffy_url)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = json.dumps({
                "ok":          True,
                "flyer_b64":   flyer_b64,          # base64 PNG for preview
                "facebook_url": fb_url,
            })

        except KeyError as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            token_hint = (
                " — Facebook token may be expired. Regenerate in Meta Developer Portal "
                "and update the FACEBOOK_PAGE_TOKEN Vercel environment variable."
                if "token" in str(e).lower() else ""
            )
            body = json.dumps({"ok": False, "error": f"Missing key: {e}{token_hint}"})

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            msg = str(e)
            if "token" in msg.lower() or "oauth" in msg.lower() or "190" in msg:
                msg += (
                    " — Facebook token expired. Regenerate in Meta Developer Portal "
                    "and update FACEBOOK_PAGE_TOKEN in Vercel environment variables."
                )
            body = json.dumps({"ok": False, "error": msg})

        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
