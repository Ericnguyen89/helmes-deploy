import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_sender_key
                    ON memories(sender, key);
                CREATE INDEX IF NOT EXISTS idx_memories_category
                    ON memories(sender, category);
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, sender: str, key: str, content: str, category: str = "general") -> str:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO memories (sender, key, content, category, updated_at) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(sender, key) DO UPDATE SET "
                "content = excluded.content, category = excluded.category, "
                "updated_at = CURRENT_TIMESTAMP",
                (sender, key, content, category),
            )
            conn.commit()
            return f"Memory saved: [{category}] {key}"
        finally:
            conn.close()

    def recall(self, sender: str, query: str) -> list[dict]:
        conn = self._get_conn()
        try:
            query_pattern = f"%{query}%"
            rows = conn.execute(
                "SELECT key, content, category, updated_at FROM memories "
                "WHERE sender = ? AND (key LIKE ? OR content LIKE ? OR category LIKE ?) "
                "ORDER BY updated_at DESC LIMIT 10",
                (sender, query_pattern, query_pattern, query_pattern),
            ).fetchall()
            return [
                {
                    "key": r["key"],
                    "content": r["content"],
                    "category": r["category"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def list_all(self, sender: str, category: str | None = None) -> list[dict]:
        conn = self._get_conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT key, content, category, updated_at FROM memories "
                    "WHERE sender = ? AND category = ? ORDER BY updated_at DESC",
                    (sender, category),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, content, category, updated_at FROM memories "
                    "WHERE sender = ? ORDER BY category, updated_at DESC",
                    (sender,),
                ).fetchall()
            return [
                {
                    "key": r["key"],
                    "content": r["content"],
                    "category": r["category"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def delete(self, sender: str, key: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM memories WHERE sender = ? AND key = ?",
                (sender, key),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_context(self, sender: str, limit: int = 20) -> str:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT key, content, category FROM memories "
                "WHERE sender = ? ORDER BY updated_at DESC LIMIT ?",
                (sender, limit),
            ).fetchall()
            if not rows:
                return ""
            lines = ["[Long-term Memory]"]
            current_cat = None
            for r in rows:
                if r["category"] != current_cat:
                    current_cat = r["category"]
                    lines.append(f"\n## {current_cat}")
                lines.append(f"- {r['key']}: {r['content']}")
            return "\n".join(lines)
        finally:
            conn.close()
