"""
D31 Facebook Marketing Agent — Phase 2
Receives club data + registration URL, then:
  Step 3 — Generates a QR code PNG (Python qrcode library)
  Step 4 — Composites a flyer PNG (Python Pillow onto flyer_template.png)
  Step 5 — Posts the flyer to the District 31 Facebook Page (Graph API)

Vercel environment variables required:
  FACEBOOK_PAGE_TOKEN  — Long-lived Page Access Token (~60-day expiry)
  FACEBOOK_PAGE_ID     — Numeric Facebook Page ID

Static assets (committed to repo under fb-agent/static/):
  flyer_template.png      — 1824x2358 blank template
  Montserrat-Bold.ttf     — Font for club name, day, city, bottom text
  Montserrat-Regular.ttf  — Font for time and body text

TEXT COORDINATES — calibrated for 1824x2358 px template
  BUBBLE_CENTER_X    = 620
  CLUB_NAME_L1_Y     = 390
  CLUB_NAME_L2_Y     = 490
  CLUB_NAME_FONT_SIZE = 90
  DAY_XY             = (350, 610)  -- adjusted down if club name is 2 lines
  DAY_FONT_SIZE      = 65
  TIME_XY            = (950, 700)
  TIME_FONT_SIZE     = 50
  CITY_XY            = (1150, 1020)
  CITY_FONT_SIZE     = 90
  BODY_CLUB_XY       = (278, 1178)
  BODY_CLUB_FONT_SIZE = 38
  BOTTOM_DATETIME_XY = (150, 1910)
  BOTTOM_ADDRESS_XY  = (150, 1990)
  BOTTOM_ADDRESS2_XY = (150, 2070)
  BOTTOM_FONT_SIZE   = 66
  QR_XY              = (1420, 1950)
  QR_SIZE            = 350
  BOTTOM_TEXT_MAX_W  = 1050  -- max width before address wraps
"""

import os
import io
import re
import json
import base64
import traceback
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw, ImageFont

# -- Asset paths ---------------------------------------------------------------

STATIC_DIR    = Path(__file__).parent.parent / "static"
TEMPLATE_PATH = STATIC_DIR / "flyer_template.png"
FONT_BOLD     = STATIC_DIR / "Montserrat-Bold.ttf"
FONT_REGULAR  = STATIC_DIR / "Montserrat-Regular.ttf"

# -- Layout constants (1824x2358 template) -------------------------------------

BUBBLE_CENTER_X     = 620
CLUB_NAME_L1_Y      = 390
CLUB_NAME_L2_Y      = 490
CLUB_NAME_FONT_SIZE = 90
DAY_XY              = (350, 610)
DAY_FONT_SIZE       = 65
TIME_XY             = (950, 700)
TIME_FONT_SIZE      = 50
CITY_XY             = (1150, 1020)
CITY_FONT_SIZE      = 90
BODY_CLUB_XY        = (278, 1178)
BODY_CLUB_FONT_SIZE = 38
BOTTOM_DATETIME_XY  = (150, 1910)
BOTTOM_ADDRESS_XY   = (150, 1990)
BOTTOM_ADDRESS2_XY  = (150, 2070)
BOTTOM_FONT_SIZE    = 66
BOTTOM_TEXT_MAX_W   = 1050
QR_XY               = (1420, 1950)
QR_SIZE             = 350

# -- Colors --------------------------------------------------------------------

COLOR_DARK  = (30,  30,  30)
COLOR_WHITE = (255, 255, 255)
COLOR_GOLD  = (212, 175, 55)

# -- Facebook ------------------------------------------------------------------

FB_API_VERSION = "v18.0"
FB_GRAPH_BASE  = f"https://graph.facebook.com/{FB_API_VERSION}"


# -- Text helpers --------------------------------------------------------------

def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def text_width(draw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def extract_city(address: str) -> str:
    """Extract city from 'Street, City, ST ZIP' format."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-2].strip()
    return ""


def split_day_time(day_time: str):
    """
    Split day/time string into (day_part, time_part).
    Handles formats like:
      'Friday at 12:00 pm'
      '2nd & 4th Wednesday 6:45 pm'
      'Thursday 6:15 PM to 7:45 PM'
      '2nd and 4th Wednesday 12:00 pm - 1:00 pm'
      'Wednesday 7:00 pm'
    """
    pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM|a\.m\.|p\.m\.)(?:\s*(?:to|-)\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM|a\.m\.|p\.m\.)?)?)'
    match = re.search(pattern, day_time, re.IGNORECASE)
    if match:
        time_part = match.group(1).strip()
        day_part  = day_time[:match.start()].strip().rstrip('at').strip()
        return day_part, time_part
    return day_time, ""


def wrap_club_name(name: str, max_chars: int = 13):
    """Split club name into up to 2 lines for yellow bubble."""
    upper = name.upper()
    if len(upper) <= max_chars:
        return upper, ""
    words = upper.split()
    line1, line2 = "", ""
    for word in words:
        test = f"{line1} {word}".strip()
        if len(test) <= max_chars:
            line1 = test
        else:
            line2 = f"{line2} {word}".strip()
    return line1, line2


def wrap_address(draw, address: str, font, max_width: int):
    """Split address at word boundary to fit within max_width."""
    if text_width(draw, address, font) <= max_width:
        return address, ""
    words = address.split(" ")
    for i in range(len(words) - 1, 0, -1):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        if text_width(draw, line1, font) <= max_width:
            return line1, line2
    return address, ""


# -- Step 3: QR Code -----------------------------------------------------------

def generate_qr(registration_url: str) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(registration_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
    return img


# -- Step 4: Flyer -------------------------------------------------------------

def generate_flyer(club: dict, registration_url: str, qr_img: Image.Image) -> bytes:
    if not TEMPLATE_PATH.exists():
        files = list(STATIC_DIR.iterdir()) if STATIC_DIR.exists() else ["static/ dir missing"]
        raise FileNotFoundError(
            f"flyer_template.png not found at {TEMPLATE_PATH}. "
            f"Files in static/: {files}"
        )

    flyer = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw  = ImageDraw.Draw(flyer)

    # Load fonts
    f_club   = load_font(FONT_BOLD,    CLUB_NAME_FONT_SIZE)
    f_day    = load_font(FONT_BOLD,    DAY_FONT_SIZE)
    f_time   = load_font(FONT_REGULAR, TIME_FONT_SIZE)
    f_city   = load_font(FONT_BOLD,    CITY_FONT_SIZE)
    f_body   = load_font(FONT_REGULAR, BODY_CLUB_FONT_SIZE)
    f_bottom = load_font(FONT_BOLD,    BOTTOM_FONT_SIZE)

    # ── Yellow bubble: Club name (centered, up to 2 lines) ──
    line1, line2 = wrap_club_name(club["club_name"])
    l1_x = BUBBLE_CENTER_X - text_width(draw, line1, f_club) // 2
    draw.text((l1_x, CLUB_NAME_L1_Y), line1, font=f_club, fill=COLOR_DARK)
    if line2:
        l2_x = BUBBLE_CENTER_X - text_width(draw, line2, f_club) // 2
        draw.text((l2_x, CLUB_NAME_L2_Y), line2, font=f_club, fill=COLOR_DARK)
        day_y = CLUB_NAME_L2_Y + CLUB_NAME_FONT_SIZE + 10
    else:
        day_y = CLUB_NAME_L2_Y

    # ── Yellow bubble: Day ──
    day_part, time_part = split_day_time(club["day_time"])
    draw.text((DAY_XY[0], day_y), day_part, font=f_day, fill=COLOR_DARK)

    # ── Small bubble: Time ──
    if time_part:
        draw.text(TIME_XY, time_part, font=f_time, fill=COLOR_DARK)

    # ── Teal banner: City after "WE CAN HELP" ──
    city = extract_city(club["address"])
    if city:
        draw.text(CITY_XY, f", {city.upper()}", font=f_city, fill=COLOR_WHITE)

    # ── Body text: Club name after "Come join" ──
    # Template has baked-in "!" after the blank zone — draw club name at consistent size
    draw.text(BODY_CLUB_XY, club["club_name"], font=f_body, fill=COLOR_WHITE)

    # ── Bottom section: Day/time and address (wrapped if long) ──
    draw.text(BOTTOM_DATETIME_XY, club["day_time"], font=f_bottom, fill=COLOR_GOLD)
    addr_line1, addr_line2 = wrap_address(draw, club["address"], f_bottom, BOTTOM_TEXT_MAX_W)
    draw.text(BOTTOM_ADDRESS_XY, addr_line1, font=f_bottom, fill=COLOR_GOLD)
    if addr_line2:
        draw.text(BOTTOM_ADDRESS2_XY, addr_line2, font=f_bottom, fill=COLOR_GOLD)

    # ── QR code ──
    flyer.paste(qr_img, QR_XY)

    buf = io.BytesIO()
    flyer.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# -- Step 5: Facebook Post -----------------------------------------------------

def post_to_facebook(flyer_bytes: bytes, club: dict, registration_url: str) -> str:
    page_token = os.environ["FACEBOOK_PAGE_TOKEN"]
    page_id    = os.environ["FACEBOOK_PAGE_ID"]

    caption = (
        f"You are invited! Join us at {club['club_name']}!\n\n"
        f"Meeting: {club['day_time']}\n"
        f"Location: {club['address']}\n\n"
        f"Register here: {registration_url}\n\n"
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

            registration_url = payload["zeffy_url"]
            club             = payload["club"]

            qr_img      = generate_qr(registration_url)
            flyer_bytes = generate_flyer(club, registration_url, qr_img)
            flyer_b64   = base64.b64encode(flyer_bytes).decode()
            fb_url      = post_to_facebook(flyer_bytes, club, registration_url)

            self._respond(200, {
                "ok":           True,
                "flyer_b64":    flyer_b64,
                "facebook_url": fb_url,
            })

        except Exception as e:
            err_msg = str(e)
            tb      = traceback.format_exc()
            if "token" in err_msg.lower() or "oauth" in err_msg.lower() or "190" in err_msg:
                err_msg += (
                    " — Facebook token may be expired. "
                    "Regenerate in Meta Developer Portal and update "
                    "FACEBOOK_PAGE_TOKEN in Vercel environment variables."
                )
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
