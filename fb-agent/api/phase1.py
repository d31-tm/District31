"""
D31 Facebook Marketing Agent — Phase 1
Reads the 30 Club Program tab from the District 31 Google Sheet.
Returns a JSON array of club objects, one per row.

Vercel environment variables required:
  GOOGLE_SHEETS_API_KEY  — Google Sheets API key (restricted to Sheets API)
  GOOGLE_SHEET_ID        — Sheet ID from the URL between /d/ and /edit

Confirmed column mapping from the live 30 Club Program tab (0-indexed):
  A (0):  Area #
  B (1):  Division Letter
  C (2):  AD Last Name         skip
  D (3):  AD First Name        skip
  E (4):  AD Email             skip
  F (5):  Recommended Club     skip
  G (6):  Area Director Choice = club name to promote
  H (7):  Free Toast Host link = fallback registration URL if Zeffy is blank
  I (8):  Day and Time
  J (9):  Address
  K (10): Zeffy Link (may be blank)

Registration URL logic:
  - If Column K (Zeffy) is populated -> use Zeffy link (zeffy_link)
  - If Column K is blank but Column H (Free Toast Host) is populated -> use FTH link (fth_link)
  - If both are blank -> registration_url is null, human must paste URL manually
"""

import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

# -- Constants -----------------------------------------------------------------

SHEET_TAB   = "30 Club Program"
SHEET_RANGE = f"'{SHEET_TAB}'!A2:K100"
SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


# -- Row parser ----------------------------------------------------------------

def _parse_row(row: list) -> dict:
    def cell(i):
        return row[i].strip() if i < len(row) and row[i] else ""

    zeffy_link = cell(10) or None
    fth_link   = cell(7)  or None

    # Determine the best registration URL automatically
    if zeffy_link:
        registration_url = zeffy_link
        registration_type = "zeffy"
    elif fth_link:
        registration_url = fth_link
        registration_type = "fth"
    else:
        registration_url = None
        registration_type = "none"

    return {
        "area":              cell(0),
        "division":          cell(1),
        "club_name":         cell(6),
        "day_time":          cell(8),
        "address":           cell(9),
        "zeffy_link":        zeffy_link,
        "fth_link":          fth_link,
        "registration_url":  registration_url,   # pre-resolved best URL
        "registration_type": registration_type,  # "zeffy", "fth", or "none"
    }


# -- Google Sheets fetch -------------------------------------------------------

def fetch_clubs() -> list:
    api_key  = os.environ["GOOGLE_SHEETS_API_KEY"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]

    url = f"{SHEETS_BASE}/{sheet_id}/values/{urllib.parse.quote(SHEET_RANGE)}?key={api_key}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    rows  = data.get("values", [])
    clubs = [_parse_row(row) for row in rows if any(row)]
    return clubs


# -- Vercel handler ------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            clubs = fetch_clubs()
            body  = json.dumps({"ok": True, "clubs": clubs})
        except KeyError as e:
            body = json.dumps({"ok": False, "error": f"Missing environment variable: {e}"})
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)})

        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
