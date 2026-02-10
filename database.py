"""
Thread-safe SQLite database module for JFFScraper.
Stores post metadata and media information.
"""

import json
import sqlite3
import threading
import time
from typing import Optional


class Database:
    """Thread-safe SQLite database. Write operations are serialized via a lock."""

    _instances: dict[str, 'Database'] = {}
    _instances_lock = threading.Lock()

    @classmethod
    def get_instance(cls, db_path: str) -> 'Database':
        """Get or create a Database instance for the given path."""
        with cls._instances_lock:
            if db_path not in cls._instances:
                cls._instances[db_path] = cls(db_path)
            return cls._instances[db_path]

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._write_lock = threading.Lock()
        self._local = threading.local()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection with retry for transient I/O errors."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            for attempt in range(3):
                try:
                    conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA journal_mode=DELETE")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA busy_timeout=5000")
                    self._local.connection = conn
                    break
                except sqlite3.OperationalError:
                    if attempt == 2:
                        raise
                    time.sleep(0.5 * (attempt + 1))
        return self._local.connection

    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid TEXT UNIQUE NOT NULL,
                mcid TEXT,
                uploader_id TEXT NOT NULL,
                post_url TEXT,
                upload_date TEXT,
                upload_date_iso TEXT,
                post_date TEXT,
                post_date_iso TEXT,
                full_text TEXT,
                type TEXT,
                pinned INTEGER,
                access_control TEXT,
                store_url TEXT,
                tags TEXT,
                raw_html TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                media_type TEXT,
                url TEXT NOT NULL,
                quality TEXT,
                license_url TEXT,
                kid TEXT,
                decryption_key TEXT,
                file_path TEXT,
                file_size INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_pid ON posts(pid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_uploader ON posts(uploader_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_post_id ON media(post_id)")

        conn.commit()

    def get_post_id(self, pid: str) -> Optional[int]:
        """Get the database ID of a post by its pid."""
        cursor = self._get_connection().execute(
            "SELECT id FROM posts WHERE pid = ?", (pid,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def insert_post(self, post, raw_html: Optional[str] = None) -> int:
        """Insert or update a post. Returns the database ID."""
        tags_json = json.dumps(post.tags) if post.tags else None

        with self._write_lock:
            self._get_connection().execute("""
                INSERT INTO posts (
                    pid, mcid, uploader_id, post_url, upload_date, upload_date_iso,
                    post_date, post_date_iso, full_text, type, pinned,
                    access_control, store_url, tags, raw_html
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pid) DO UPDATE SET
                    mcid = excluded.mcid,
                    uploader_id = excluded.uploader_id,
                    post_url = excluded.post_url,
                    upload_date = excluded.upload_date,
                    upload_date_iso = excluded.upload_date_iso,
                    post_date = excluded.post_date,
                    post_date_iso = excluded.post_date_iso,
                    full_text = excluded.full_text,
                    type = excluded.type,
                    pinned = excluded.pinned,
                    access_control = excluded.access_control,
                    store_url = excluded.store_url,
                    tags = excluded.tags,
                    raw_html = excluded.raw_html
            """, (
                post.pid,
                getattr(post, 'mcid', None),
                post.uploader_id,
                getattr(post, 'post_url', None),
                post.upload_date,
                post.upload_date_iso,
                post.post_date,
                post.post_date_iso,
                post.full_text,
                post.type,
                1 if post.pinned else 0,
                post.access_control,
                post.store_url,
                tags_json,
                raw_html
            ))
            self._get_connection().commit()
            return self.get_post_id(post.pid)

    def get_media_id(self, post_id: int, media_type: str, url: str) -> Optional[int]:
        """
        Get database ID of a media record.
        Video: matches by (post_id, media_type) since a post has at most 1 video.
        Photo: matches by (post_id, url) since a post can have multiple photos.
        """
        if media_type == "video":
            cursor = self._get_connection().execute(
                "SELECT id FROM media WHERE post_id = ? AND media_type = ?",
                (post_id, media_type)
            )
        else:
            cursor = self._get_connection().execute(
                "SELECT id FROM media WHERE post_id = ? AND url = ?",
                (post_id, url)
            )
        row = cursor.fetchone()
        return row[0] if row else None

    def insert_media(
        self,
        post_db_id: int,
        media_type: str,
        url: str,
        quality: Optional[str] = None,
        license_url: Optional[str] = None,
        kid: Optional[str] = None,
        decryption_key: Optional[str] = None
    ) -> int:
        """Insert or update a media record. Returns the database ID."""
        existing_id = self.get_media_id(post_db_id, media_type, url)

        with self._write_lock:
            conn = self._get_connection()
            if existing_id:
                conn.execute("""
                    UPDATE media SET
                        url = ?, quality = ?, license_url = ?, kid = ?, decryption_key = ?
                    WHERE id = ?
                """, (url, quality, license_url, kid, decryption_key, existing_id))
                conn.commit()
                return existing_id
            else:
                cursor = conn.execute("""
                    INSERT INTO media (
                        post_id, media_type, url, quality, license_url, kid, decryption_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (post_db_id, media_type, url, quality, license_url, kid, decryption_key))
                conn.commit()
                return cursor.lastrowid

    def update_media(self, media_id: int, file_path: str = None, file_size: int = None):
        """Update media record with file path and size after download."""
        with self._write_lock:
            conn = self._get_connection()
            conn.execute(
                "UPDATE media SET file_path = ?, file_size = ? WHERE id = ?",
                (file_path, file_size, media_id)
            )
            conn.commit()
