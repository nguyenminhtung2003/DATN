"""
DrowsiGuard — Local Event Queue (SQLite)
Stores events locally when WebSocket is offline.
FIFO policy, max 1000 records, priority: alert > session > face_mismatch > ota > gps > heartbeat.
"""
import json
import os
import sqlite3
import time
import threading

from utils.logger import get_logger
import config

logger = get_logger("storage.local_queue")

# Priority: lower number = higher priority
PRIORITY_MAP = {
    "session_start": 1,
    "session_end": 2,
    "alert": 3,
    "face_mismatch": 4,
    "ota_status": 5,
    "gps": 6,
    "hardware": 7,
    "driver": 8,
    "verify_snapshot": 8,
}

COALESCED_TYPES = {"hardware", "gps", "verify_snapshot"}


class LocalQueue:
    """SQLite-backed local event queue for offline resilience."""

    def __init__(self, db_path: str = None):
        self._db_path = db_path or config.QUEUE_DB_PATH
        self._max_records = config.QUEUE_MAX_RECORDS
        self._lock = threading.Lock()
        self._init_db()
        logger.info(f"LocalQueue initialized: {self._db_path}")

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_type TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 5,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_sent ON event_queue(sent, priority, id)")

    def push(self, msg_type: str, data: dict):
        """Add event to queue."""
        priority = PRIORITY_MAP.get(msg_type, 5)
        payload = json.dumps({"type": msg_type, "data": data})
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                if msg_type in COALESCED_TYPES:
                    conn.execute(
                        "DELETE FROM event_queue WHERE sent=0 AND msg_type=?",
                        (msg_type,),
                    )
                conn.execute(
                    "INSERT INTO event_queue (msg_type, priority, payload, created_at) VALUES (?, ?, ?, ?)",
                    (msg_type, priority, payload, time.time()),
                )
                # Enforce max records by removing lowest priority oldest entries
                count = conn.execute("SELECT COUNT(*) FROM event_queue WHERE sent=0").fetchone()[0]
                if count > self._max_records:
                    excess = count - self._max_records
                    conn.execute(
                        "DELETE FROM event_queue WHERE id IN "
                        "(SELECT id FROM event_queue WHERE sent=0 ORDER BY priority DESC, id ASC LIMIT ?)",
                        (excess,),
                    )
        logger.debug(f"Queued event: {msg_type} (priority={priority})")

    def pop_batch(self, limit: int = 50) -> list:
        """Get oldest unsent events, ordered by priority then age."""
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT id, payload FROM event_queue WHERE sent=0 ORDER BY priority ASC, id ASC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [(row[0], json.loads(row[1])) for row in rows]

    def mark_sent(self, event_ids: list):
        """Mark events as successfully sent."""
        if not event_ids:
            return
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                placeholders = ",".join(["?"] * len(event_ids))
                conn.execute(f"UPDATE event_queue SET sent=1 WHERE id IN ({placeholders})", event_ids)

    def cleanup_sent(self):
        """Remove sent events from DB."""
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM event_queue WHERE sent=1")

    @property
    def pending_count(self) -> int:
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                return conn.execute("SELECT COUNT(*) FROM event_queue WHERE sent=0").fetchone()[0]
