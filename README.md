# Campsites

Finds open RV campsites across federal and state parks in Florida and Georgia for a
given set of dates, then drops them all on one interactive map.

Built for trip planning: pick a start date, a number of nights, and a minimum rig
length, and the scanner reports what is actually bookable instead of making you check
three reservation systems by hand.

## What it checks

| Source | How | Covers |
|---|---|---|
| recreation.gov | RIDB API + availability API | All reservable federal campgrounds in FL / GA |
| FloridaStateParks.org | Playwright browser automation | FL state parks |
| GeorgiaStateParks.org | Playwright browser automation | GA state parks |

Federal sites can either be discovered automatically for the whole state, or limited to
a hand-picked watchlist.

## Scripts

- **`app_v1.py`** — the main one. Scans federal + FL + GA, reverse-geocodes each hit for
  a street address, and writes `ultimate_radar.html`.
- **`natl_sites.py`** — federal sites only, from a fixed watchlist with pre-filled
  coordinates. Faster, since it skips the geocoding lookups.
- **`fl_state_scraper.py`** — Georgia state parks only, driven off a park-ID dictionary.
- **`find_sites.py`** — the original Florida prototype. Kept for reference.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` to `.env` and add a RIDB key. It is free from
[ridb.recreation.gov/profile](https://ridb.recreation.gov/profile) under **API Keys**.
The key is only needed when scanning all federal campgrounds; without it the scanner
falls back to the built-in watchlist.

```
RIDB_API_KEY=your_key_here
```

## Running it

Edit the trip settings at the top of `app_v1.py`:

```python
START_DATE = "2026-09-29"   # YYYY-MM-DD
NIGHTS = 7
MIN_RV_LENGTH = 20          # feet
SCAN_REGION = "Both"        # "FL", "GA", or "Both"
SCAN_ALL_FEDERAL = True     # False = watchlist only
```

Then:

```bash
python app_v1.py
```

It writes `ultimate_radar.html` and opens it in your browser. Green markers are open
sites, and each popup carries the park name, address, and a link into the booking page.

## Notes

- The state park scrapers drive a real browser. They break whenever those sites change
  their markup, which is normal and expected.
- Scanning all federal campgrounds in both states makes a lot of API calls and takes a
  while. Use the watchlist mode when iterating.
- `output/` holds generated maps and debug screenshots. It is gitignored.
