"""
Central configuration. Edit this file to customize what counts as a
'match' and how often the tracker re-checks university pages.
"""

# Keywords used to detect job/circular-related links or text on a page.
# Matching is case-insensitive and looks for these as substrings.
# Add/remove freely -- e.g. add "adjunct", "part-time faculty", your
# department name, etc.
KEYWORDS = [
    "lecturer",
    "assistant professor",
    "associate professor",
    "professor",
    "faculty",
    "teacher recruitment",
    "job circular",
    "recruitment circular",
    "recruitment notice",
    "vacancy",
    "vacancies",
    "walk-in interview",
    "career",
    "job opportunity",
    "notice for recruitment",
    "computer science",
    "cse",
    "software engineering",
]

# How often (in minutes) the background scheduler re-checks all
# active universities. 360 = every 6 hours. Set to 0 to disable the
# automatic scheduler (you can still use the "Check now" button).
SCAN_INTERVAL_MINUTES = 360

# HTTP request timeout (seconds) per site.
REQUEST_TIMEOUT = 15

DATABASE_PATH = "data/tracker.db"
