"""
D31 Facebook Marketing Agent — Phase 1
Reads the 30 Club Program tab from the District 31 Google Sheet.
Returns a JSON array of club objects, one per row.

Vercel environment variables required:
  GOOGLE_SHEETS_API_KEY  — Google Sheets API key (restricted to Sheets API)
  GOOGLE_SHEET_ID        — Sheet ID from the URL between /d/ and /edit

Column mapping (0-indexed):
  A (0): Area #
  B (1): Division Letter
  C (2): Club Name
  D (3): Day/Time
  E (4): Location/Address
  F (5): Zeffy Link (may be blank)

⚠ Verify column headers against the live sheet before deploying.
  If columns shift, update the indices in _parse_row() below.
"""

import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

# ── Constants ────────────────────────────────────────────────────────────────

SHEET_TAB = "30 Club Program"  # Exact tab name — must match the live sheet
SHEET_RANGE = f"'{SHEET_TAB}'!A2:F100"  # A2 skips the header row; F100 is generous
SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


# ── Row parser ───────────────────────────────────────────────────────────────

def _parse_row(row: list) -> dict:
    """Map a raw Sheets API row (list of cell values) to a club object."""
    def cell(i):
        return row[i].strip() if i < len(row) and row[i] else ""

    return {
        "area":       cell(0),
        "division":   cell(1),
        "club_name":  cell(2),
        "day_time":   cell(3),
        "address":    cell(4),
        "zeffy_link": cell(5) or None,  # None means human must create Zeffy event
    }


# ── Google Sheets fetch ───────────────────────────────────────────────────────

def fetch_clubs() -> list:
    api_key  = os.environ["GOOGLE_SHEETS_API_KEY"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]

    params = urllib.parse.urlencode({
        "range": SHEET_RANGE,
        "key":   api_key,
    })
    url = f"{SHEETS_BASE}/{sheet_id}/values/{urllib.parse.quote(SHEET_RANGE)}?key={api_key}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    rows = data.get("values", [])
    clubs = [_parse_row(row) for row in rows if any(row)]  # skip blank rows
    return clubs


# ── Vercel handler ────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # CORS — allow the Vercel-hosted frontend to call this endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            clubs = fetch_clubs()
            body = json.dumps({"ok": True, "clubs": clubs})
        except KeyError as e:
            body = json.dumps({"ok": False, "error": f"Missing environment variable: {e}"})
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)})

        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        # Pre-flight CORS
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
