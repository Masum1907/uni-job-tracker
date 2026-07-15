"""
Generic scraper that works across many different university website
layouts. It does NOT try to parse a specific site's HTML structure
(impossible to hand-write for 100+ sites). Instead, for each page it:

  1. Pulls out every link (<a>) and its visible text.
  2. Filters OUT obvious navigation/boilerplate (the "Career" link
     itself, "Faculty of Arts", "Department of X", "Contact", etc.)
     so those never get flagged as if they were job postings.
  3. Keeps links whose text matches specific hiring phrases (e.g.
     "lecturer", "job circular", "vacancy", "assistant professor").
  4. Flags anything matching that we haven't recorded before as new.
  5. If the page has no matching postings at all, falls back to "page
     content changed -- check manually", so nothing silently falls
     through the cracks.

Only the exact URL you give it is scanned -- it never wanders off to
other pages on the site (no homepage crawling, no following links).
Give it the specific career/job listing page URL for each university.
"""

import re
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config import (
    KEYWORDS,
    EXCLUDE_EXACT,
    EXCLUDE_PREFIX_PATTERNS,
    REQUEST_TIMEOUT,
)
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

_EXCLUDE_PREFIX_RE = re.compile("|".join(EXCLUDE_PREFIX_PATTERNS), re.IGNORECASE)

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


def fetch_html(url: str) -> str:
    """Static fetch, escalating to a headless browser if the page looks
    like an empty JS-app shell."""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
    resp.raise_for_status()
    html = resp.text
    if _visible_text_length(html) < MIN_TEXT_LENGTH_FOR_STATIC and PLAYWRIGHT_AVAILABLE:
        try:
            html = render_with_browser(url)
        except Exception:
            pass  # keep the static HTML if browser rendering fails
    return html


def extract_all_links(html: str, base_url: str):
    """Every distinct (text, absolute_url) link on the page."""
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


def is_noise(text: str) -> bool:
    """True if this link text is clearly navigation/boilerplate, never
    an actual job posting (e.g. 'Career', 'Faculty of Arts', 'Contact')."""
    t = text.strip().lower()
    if t in EXCLUDE_EXACT:
        return True
    if _EXCLUDE_PREFIX_RE.match(t):
        return True
    return False


def matches_keywords(text: str) -> bool:
    if is_noise(text):
        return False
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)


def matched_items_from_page(html: str, page_url: str):
    items = extract_all_links(html, page_url)
    matched = [(t, u) for t, u in items if matches_keywords(t)]
    return matched


def _friendly_error(e: Exception) -> str:
    """Turn a raw exception into a message that actually tells you what
    to do about it, instead of a bare exception class name."""
    if isinstance(e, requests.exceptions.MissingSchema):
        return "error: URL is missing http:// or https:// -- edit it to start with https://"
    if isinstance(e, requests.exceptions.InvalidURL):
        return "error: URL looks malformed -- double check it"
    if isinstance(e, requests.exceptions.SSLError):
        return "error: SSL/certificate problem on that site"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "error: could not connect -- site may be down, or blocking automated requests"
    if isinstance(e, requests.exceptions.Timeout):
        return f"error: timed out after {REQUEST_TIMEOUT}s -- site may be slow or unreachable"
    if isinstance(e, requests.exceptions.HTTPError):
        code = e.response.status_code if e.response is not None else "?"
        if code == 403:
            return "error: HTTP 403 (site is blocking automated requests)"
        if code == 404:
            return "error: HTTP 404 (page not found -- check the URL is still correct)"
        if code and code >= 500:
            return f"error: HTTP {code} (problem on the university's server, try again later)"
        return f"error: HTTP {code}"
    return f"error: {type(e).__name__}: {e}"


def check_university(uni_row):
    """uni_row: sqlite3.Row with id, name, url."""
    uni_id = uni_row["id"]
    url = uni_row["url"]
    new_postings = []

    try:
        main_html = fetch_html(url)
        matched = matched_items_from_page(main_html, url)

        if matched:
            for text, link in matched:
                item_hash = _hash(f"{url}|{link}|{text}")
                if not db.posting_exists(item_hash):
                    db.insert_posting(uni_id, text, link, item_hash)
                    new_postings.append((text, link))
        else:
            # Fallback: whole-page change detection on the main page.
            page_hash = _hash(main_html)
            prev_hash = db.get_snapshot(uni_id)
            if prev_hash and prev_hash != page_hash:
                item_hash = _hash(f"{url}|page-change|{page_hash}")
                if not db.posting_exists(item_hash):
                    title = f"Page content changed on {uni_row['name']} (check manually)"
                    db.insert_posting(uni_id, title, url, item_hash)
                    new_postings.append((title, url))
            db.update_snapshot(uni_id, page_hash)

        db.update_university_status(uni_id, "ok")

    except requests.exceptions.RequestException as e:
        db.update_university_status(uni_id, _friendly_error(e))
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
