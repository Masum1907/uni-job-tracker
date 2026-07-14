CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT,
    url TEXT NOT NULL UNIQUE,
    last_checked TEXT,
    last_status TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    title TEXT,
    link TEXT,
    item_hash TEXT UNIQUE,
    first_seen TEXT,
    is_read INTEGER DEFAULT 0,
    FOREIGN KEY(university_id) REFERENCES universities(id)
);

CREATE TABLE IF NOT EXISTS page_snapshots (
    university_id INTEGER PRIMARY KEY,
    content_hash TEXT,
    FOREIGN KEY(university_id) REFERENCES universities(id)
);
