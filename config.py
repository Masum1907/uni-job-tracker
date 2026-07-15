"""
Central configuration. Edit this file to customize what counts as a
'match' and how often the tracker re-checks university pages.
"""

# Keywords that indicate an ACTUAL job posting/circular (not just a
# navigation link like "Career" or a department name like "Faculty of
# Arts"). Kept deliberately specific -- generic single words like
# "career", "faculty", or "computer science" alone match ordinary site
# navigation constantly and create false positives.
KEYWORDS = [
    "job circular",
    "recruitment circular",
    "recruitment notice",
    "notice for recruitment",
    "teacher recruitment",
    "faculty recruitment",
    "faculty position",
    "faculty vacancy",
    "vacancy announcement",
    "vacancy",
    "vacancies",
    "walk-in interview",
    "assistant professor",
    "associate professor",
    "lecturer",
    "we are hiring",
    "hiring notice",
    "job opportunity",
]

# Link text that is ALWAYS navigation/boilerplate, never a job posting.
# Matched as an exact (trimmed, case-insensitive) match, not substring --
# this stops "Career" (the nav link itself) from being flagged while still
# letting through something like "Career Circular for Lecturer Post".
EXCLUDE_EXACT = {
    "career", "careers", "job", "jobs", "job opportunities",
    "contact", "contact us", "about", "about us", "home",
    "admission", "admissions", "academic calendar", "notice board",
    "notices", "notice", "news", "gallery", "photo gallery",
    "video gallery", "alumni", "login", "register", "sign in",
    "student portal", "academics", "research", "publication",
    "publications", "events", "apply online", "apply now",
    "downloads", "faqs", "faq",
}

# Link text STARTING WITH these patterns is an academic org unit name
# (department/faculty/school listing), not a job posting -- e.g.
# "Department of Computer Science and Engineering", "Faculty of Arts".
EXCLUDE_PREFIX_PATTERNS = [
    r"^(department|faculty|school|institute|office|center|centre|"
    r"program|programme|division)s?\s+of\s+",
]

# How often (in minutes) the background scheduler re-checks all
# active universities. 360 = every 6 hours. Set to 0 to disable the
# automatic scheduler (you can still use the "Check now" button).
SCAN_INTERVAL_MINUTES = 360

# HTTP request timeout (seconds) per site.
REQUEST_TIMEOUT = 15

DATABASE_PATH = "data/tracker.db"

# Password required to add/remove universities (the dashboard itself
# stays public so job-seekers can browse it). Set this via an
# environment variable in production -- do NOT commit your real
# password into a public GitHub repo. On Render: Dashboard -> your
# service -> Environment -> Add Environment Variable -> key
# ADMIN_PASSWORD, value = your chosen password.
import os
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
