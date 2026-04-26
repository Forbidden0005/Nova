"""
memory/store.py — Persistent SQLite-backed memory store for LocalAgentOS.
Stores chat history, agent facts, and task execution logs.
Thread-safe via a single write-lock.
"""
from __future__ import annotations
import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from config import MEMORY_DB, CONTEXT_WINDOW_TURNS

logger = logging.getLogger(__name__)


class MemoryStore:
    """Thread-safe persistent memory backed by SQLite."""

    def __init__(self, db_path: Path = MEMORY_DB) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._bootstrap()
        logger.info("MemoryStore initialised at %s", db_path)

    def _bootstrap(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    role    TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts      TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS facts (
                    key     TEXT PRIMARY KEY,
                    value   TEXT NOT NULL,
                    updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_logs (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    steps     TEXT NOT NULL,
                    result    TEXT NOT NULL,
                    log       TEXT NOT NULL,
                    ts        TEXT NOT NULL
                );
            """)
            self._conn.commit()

    def add_message(self, role: str, content: str) -> None:
        ts = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO chat_history (role, content, ts) VALUES (?, ?, ?)",
                (role, content, ts),
            )
            self._conn.commit()

    def get_recent_messages(self, n: int = CONTEXT_WINDOW_TURNS) -> list[dict[str, str]]:
        cur = self._conn.execute(
            "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?", (n,)
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def clear_history(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM chat_history")
            self._conn.commit()

    def set_fact(self, key: str, value: Any) -> None:
        ts = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO facts (key, value, updated) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated""",
                (key, json.dumps(value), ts),
            )
            self._conn.commit()

    def get_fact(self, key: str, default: Any = None) -> Any:
        cur = self._conn.execute("SELECT value FROM facts WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupted JSON for fact key '%s', returning default", key)
            return default

    def log_task(self, task_name: str, steps: list[str], result: str, log: str) -> int:
        ts = datetime.utcnow().isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO task_logs (task_name, steps, result, log, ts) VALUES (?, ?, ?, ?, ?)",
                (task_name, json.dumps(steps), result, log, ts),
            )
            self._conn.commit()
            return cur.lastrowid

    def close(self) -> None:
        with self._lock:
            self._conn.close()
