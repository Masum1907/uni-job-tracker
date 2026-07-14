"""
Generic scraper that works across many different university website
layouts. It does NOT try to parse a specific site's HTML structure
(impossible to hand-write for 100+ sites). Instead, for each page it:

  1. Pulls out every link (<a>) and its visible text.
  2. Keeps only links whose text matches one of our KEYWORDS
     (e.g. "lecturer", "job circular", "vacancy").
  3. Flags any such link that we haven't recorded before as a new
     posting.
  4. If a page has NO matching links at all (e.g. some notice boards
     render circulars as an image or plain paragraph, not a link),
     it falls back to hashing the whole page and flags "page updated"
     when the hash changes, so you at least know to go check it.

This trades perfect precision for coverage across many unknown site
structures, which is the only practical way to monitor 100+ pages
you don't control.
"""

import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config import KEYWORDS, REQUEST_TIMEOUT
import db

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UniJobTracker/1.0; "
        "personal research/career-monitoring tool)"
    )
}

# Minimum visible text length before we consider a static fetch to have
# actually gotten real content. Many JS-framework sites (Next.js, React,
# Angular) return a near-empty HTML shell -- if we see less than this many
# characters of visible text, we assume the real content is loaded by
# JavaScript and fall back to rendering it with a headless browser.
MIN_TEXT_LENGTH_FOR_STATIC = 250

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _visible_text_length(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    return len(soup.get_text(strip=True))


def render_with_browser(url: str, wait_ms: int = 4000) -> str:
    """
    Render a page with a real (headless) browser so JavaScript-loaded
    content shows up, e.g. Next.js/React job listing pages like IUB's.
    Requires: pip install playwright && playwright install chromium
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. Run:\n"
            "  pip install playwright --break-system-packages\n"
            "  playwright install chromium\n"
            "to enable JavaScript-rendered site support."
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(wait_ms)  # extra buffer for late-loading widgets
            html = page.content()
        finally:
            browser.close()
    return html


def extract_candidate_items(html: str, base_url: str):
    soup = BeautifulSoup(html, "lxml")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if not text or len(text) < 4:
            continue
        full_url = urljoin(base_url, href)
        key = (text.lower(), full_url)
        if key in seen:
            continue
        seen.add(key)
        items.append((text, full_url))
    return items


def matches_keywords(text: str) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)


def check_university(uni_row):
    """uni_row: sqlite3.Row with id, name, url."""
    uni_id = uni_row["id"]
    url = uni_row["url"]
    new_postings = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        html = resp.text
        render_mode = "static"

        # If the static HTML looks like an empty JS-app shell (very little
        # visible text, e.g. Next.js/React sites), re-fetch with a headless
        # browser so client-side-rendered job listings actually show up.
        if _visible_text_length(html) < MIN_TEXT_LENGTH_FOR_STATIC and PLAYWRIGHT_AVAILABLE:
            try:
                html = render_with_browser(url)
                render_mode = "browser"
            except Exception:
                pass  # keep the static HTML if browser rendering fails

        items = extract_candidate_items(html, url)
        matched = [(t, u) for t, u in items if matches_keywords(t)]

        if matched:
            for text, link in matched:
                item_hash = _hash(f"{url}|{link}|{text}")
                if not db.posting_exists(item_hash):
                    db.insert_posting(uni_id, text, link, item_hash)
                    new_postings.append((text, link))
        else:
            # Fallback: whole-page change detection
            page_hash = _hash(html)
            prev_hash = db.get_snapshot(uni_id)
            if prev_hash and prev_hash != page_hash:
                item_hash = _hash(f"{url}|page-change|{page_hash}")
                if not db.posting_exists(item_hash):
                    title = f"Page content changed on {uni_row['name']} (check manually)"
                    db.insert_posting(uni_id, title, url, item_hash)
                    new_postings.append((title, url))
            db.update_snapshot(uni_id, page_hash)

        status = "ok" if render_mode == "static" else "ok (rendered with browser)"
        if render_mode == "static" and _visible_text_length(html) < MIN_TEXT_LENGTH_FOR_STATIC:
            status = "ok (page looks JS-rendered; install Playwright for full coverage)"
        db.update_university_status(uni_id, status)

    except requests.exceptions.RequestException as e:
        db.update_university_status(uni_id, f"error: {type(e).__name__}")
    except Exception as e:
        db.update_university_status(uni_id, f"error: {e}")

    return new_postings


def run_all_checks():
    """Check every active university. Returns total new postings found."""
    universities = [u for u in db.list_universities() if u["active"]]
    total_new = 0
    for uni in universities:
        new = check_university(uni)
        total_new += len(new)
    return total_new
