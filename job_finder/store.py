"""Dedupe store: remembers every post we've already seen."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    id          TEXT PRIMARY KEY,
    subreddit   TEXT,
    title       TEXT,
    score       INTEGER,
    first_seen  REAL
);
"""


class Store:
    def __init__(self, db_path: str | Path = "seen.sqlite3"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def is_new(self, post_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen WHERE id = ?", (post_id,)).fetchone()
        return row is None

    def mark(self, post_id: str, subreddit: str = "", title: str = "", score: int = 0) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen (id, subreddit, title, score, first_seen) VALUES (?, ?, ?, ?, ?)",
            (post_id, subreddit, title, score, time.time()),
        )
        self.conn.commit()

    def mark_many(self, posts) -> None:
        self.conn.executemany(
            "INSERT OR IGNORE INTO seen (id, subreddit, title, score, first_seen) VALUES (?, ?, ?, ?, ?)",
            [(p.id, p.subreddit, p.title, getattr(p, "notify_score", 0), time.time()) for p in posts],
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    def prune(self, keep_days: int = 90) -> None:
        cutoff = time.time() - keep_days * 86400
        self.conn.execute("DELETE FROM seen WHERE first_seen < ?", (cutoff,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
