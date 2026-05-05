# D31 Facebook Marketing Agent

Automates the five-step process District 31 leadership uses to promote club meetings on Facebook.

## Quick Start (for incoming District Directors)

1. Open the app URL in any browser
2. Click **Run Phase 1** — club details load from the Google Sheet
3. Select the club you want to promote
4. Click **Copy Details for Zeffy** — paste into Zeffy event creation form
5. Create the Zeffy event, copy the registration URL, paste it back into the app
6. Click **Run Phase 2** — QR code and flyer are generated and posted to Facebook automatically

---

## Repository Structure

```
fb-agent/
  api/
    phase1.py            ← Vercel serverless: reads Google Sheet
    phase2.py            ← Vercel serverless: QR + flyer + Facebook post
  static/
    index.html           ← Single-page UI
    flyer_template.png   ← Base flyer PNG (upload once, reuse forever)
    Montserrat-Bold.ttf  ← Font file for Pillow text compositing
    Montserrat-Regular.ttf
  requirements.txt
  vercel.json
  README.md
```

---

## Vercel Environment Variables

Set these in Vercel Dashboard → Project → Settings → Environment Variables:

| Variable | Description |
|---|---|
| `GOOGLE_SHEETS_API_KEY` | Google Sheets API key (restricted to Sheets API) |
| `GOOGLE_SHEET_ID` | Sheet ID from the URL between /d/ and /edit |
| `FACEBOOK_PAGE_TOKEN` | Long-lived Facebook Page Access Token (~60-day expiry) |
| `FACEBOOK_PAGE_ID` | Numeric Facebook Page ID |

---

## Annual Maintenance (before June 30 each year)

| Task | When | Who |
|---|---|---|
| Add incoming DD as Facebook Page admin | By June 15 | Outgoing DD |
| Transfer toastmastersD31@gmail.com password | By June 25 | Outgoing DD |
| Regenerate Facebook Page Access Token | By June 28 | Incoming DD |
| Update FACEBOOK_PAGE_TOKEN in Vercel | Immediately after regeneration | Incoming DD |
| Verify Google Sheet access | By June 28 | Incoming DD |
| Run test Phase 1 | By June 30 | Incoming DD |

⚠️ **Facebook token expires every ~60 days.** Set a recurring calendar reminder every 50 days to regenerate it in the Meta Developer Portal and update the Vercel environment variable.

---

## Updating the Flyer Template

1. Edit the design in Canva
2. Export as PNG (leave club name, date, address, and QR zones blank)
3. Replace `static/flyer_template.png` in the repo
4. **Recalibrate pixel coordinates** in `api/phase2.py` — see the coordinate constants at the top of that file

---

## Service Identity

All credentials are tied to **toastmastersD31@gmail.com** — not any individual officer's personal account. This ensures zero-downtime handoff at the June 30 officer transition.

- GitHub org: github.com/d31-tm
- Vercel project: tied to toastmastersD31@gmail.com
- Google Sheet: owned by toastmastersD31@gmail.com
- Facebook Page admin: toastmastersD31@gmail.com
- Zeffy account: toastmastersD31@gmail.com

---

*Built for District 31 Toastmasters · April 2026*
