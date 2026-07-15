import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def normalize_url(url: str) -> str:
    """Add https:// if the user forgot a scheme, so scans never fail
    with a 'missing scheme' error over something this easy to fix."""
    url = url.strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url

def get_conn():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def seed_universities(seed_list):
    """Insert seed universities if the table is empty."""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) AS c FROM universities").fetchone()["c"]
    if count == 0:
        for u in seed_list:
            try:
                conn.execute(
                    "INSERT INTO universities (name, type, url) VALUES (?, ?, ?)",
                    (u["name"], u.get("type", ""), normalize_url(u["url"])),
                )
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    conn.close()

def list_universities():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM universities ORDER BY name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return rows

def add_university(name, url, type_=""):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO universities (name, type, url) VALUES (?, ?, ?)",
            (name.strip(), type_.strip(), normalize_url(url)),
        )
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def delete_university(uni_id):
    conn = get_conn()
    conn.execute("DELETE FROM postings WHERE university_id=?", (uni_id,))
    conn.execute("DELETE FROM page_snapshots WHERE university_id=?", (uni_id,))
    conn.execute("DELETE FROM universities WHERE id=?", (uni_id,))
    conn.commit()
    conn.close()

def update_university_status(uni_id, status):
    conn = get_conn()
    conn.execute(
        "UPDATE universities SET last_checked=?, last_status=? WHERE id=?",
        (datetime.utcnow().isoformat(), status, uni_id),
    )
    conn.commit()
    conn.close()

def posting_exists(item_hash):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM postings WHERE item_hash=?", (item_hash,)
    ).fetchone()
    conn.close()
    return row is not None

def insert_posting(university_id, title, link, item_hash):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO postings (university_id, title, link, item_hash, first_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (university_id, title, link, item_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_snapshot(university_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT content_hash FROM page_snapshots WHERE university_id=?",
        (university_id,),
    ).fetchone()
    conn.close()
    return row["content_hash"] if row else None

def update_snapshot(university_id, content_hash):
    conn = get_conn()
    conn.execute(
        "INSERT INTO page_snapshots (university_id, content_hash) VALUES (?, ?) "
        "ON CONFLICT(university_id) DO UPDATE SET content_hash=excluded.content_hash",
        (university_id, content_hash),
    )
    conn.commit()
    conn.close()

def list_postings(only_unread=False, limit=300):
    conn = get_conn()
    q = """
        SELECT postings.*, universities.name AS uni_name, universities.type AS uni_type
        FROM postings
        JOIN universities ON universities.id = postings.university_id
    """
    if only_unread:
        q += " WHERE postings.is_read = 0"
    q += " ORDER BY postings.first_seen DESC LIMIT ?"
    rows = conn.execute(q, (limit,)).fetchall()
    conn.close()
    return rows

def mark_read(posting_id):
    conn = get_conn()
    conn.execute("UPDATE postings SET is_read=1 WHERE id=?", (posting_id,))
    conn.commit()
    conn.close()

def mark_all_read():
    conn = get_conn()
    conn.execute("UPDATE postings SET is_read=1")
    conn.commit()
    conn.close()

def unread_count():
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM postings WHERE is_read=0"
    ).fetchone()
    conn.close()
    return row["c"]
