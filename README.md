# Uni Job Tracker

Monitors university career pages and flags new job/circular postings on a
simple dashboard — no more manually checking dozens of websites.

Currently seeded with:
- North South University (NSU)
- Independent University, Bangladesh (IUB)

Add more any time from the "Manage Universities" page in the app.

## How it works

For each university URL, the tracker:
1. Fetches the page.
2. If the page looks empty/JS-rendered (common on sites like IUB built
   with Next.js/React), it re-fetches using a real headless browser so
   dynamically-loaded job listings show up.
3. Scans all links on the page for keywords like "lecturer", "faculty",
   "job circular", "vacancy" (edit the list in `config.py`).
4. Anything matching that you haven't seen before shows up on the
   dashboard as a new posting, with a direct link.
5. If a page has no matching links at all, it falls back to "the page
   content changed since last check — go look manually", so nothing
   silently falls through the cracks.

## Setup (run this once)

```bash
pip install -r requirements.txt --break-system-packages
playwright install chromium        # enables JS-rendered site support (e.g. IUB)
```

> If `playwright install chromium` fails or you skip it, everything still
> works for normal (non-JS) sites — that university's dashboard status will
> just say "page looks JS-rendered; install Playwright for full coverage".

## Run it

```bash
python3 app.py
```

Then open **http://localhost:5000** in your browser.

- Click **Check now** to run a scan immediately.
- It also auto-checks in the background every 6 hours (change
  `SCAN_INTERVAL_MINUTES` in `config.py` — set to `0` to disable auto-checks
  and only ever use the button).

## Adding more universities

Go to **Manage Universities** in the app. Two ways:

- **One at a time**: paste the name + the career/job page URL.
- **Bulk paste**: one per line, `Name, URL` — good for adding a batch you've
  collected. I already pulled the full official UGC list of ~160 public +
  private university websites — just say the word and I'll hand you that
  as a ready-to-paste bulk list (homepages, since exact career sub-pages
  aren't published for all of them).

**Tip:** if a university's page uses no links for postings (e.g. plain
text notices, or scanned PDF images), the tracker will still flag "page
changed" so you know to check it manually — it just can't extract a
specific title/link for you automatically.

## Keeping it running without your laptop on

Right now this runs locally — it only checks while your machine is on and
`python3 app.py` is running. To have it check jobs 24/7 even when your
laptop is off, deploy it to a free-tier host such as:
- **Render.com** (free web service tier)
- **Railway.app**
- **PythonAnywhere**

All three can run a Flask app like this directly from a GitHub repo. Ask
me when you're ready and I'll walk you through deploying to whichever you
pick.

## Customizing keywords

Edit `KEYWORDS` in `config.py` — e.g. add your department name, "adjunct",
"part-time faculty", or remove ones giving too much noise.

## Files

- `app.py` — Flask web app (dashboard + university management)
- `scraper.py` — the actual checking/detection logic
- `db.py` — SQLite storage helpers
- `config.py` — keywords, scan interval, timeouts
- `seed_universities.py` — initial university list (only used on first run)
- `schema.sql` — database schema
- `templates/` — HTML pages
