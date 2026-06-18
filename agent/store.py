import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConversationStore:
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
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);

                CREATE TABLE IF NOT EXISTS user_settings (
                    phone TEXT PRIMARY KEY,
                    system_prompt TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def add_message(self, sender: str, role: str, content: str):
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO messages (sender, role, content) VALUES (?, ?, ?)",
                (sender, role, content),
            )
            conn.commit()
        finally:
            conn.close()

    def get_conversation(self, sender: str, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE sender = ? ORDER BY id DESC LIMIT ?",
                (sender, limit),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        finally:
            conn.close()

    def clear_conversation(self, sender: str):
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM messages WHERE sender = ?", (sender,))
            conn.commit()
        finally:
            conn.close()

    def get_message_count_last_hour(self, sender: str) -> int:
        conn = self._get_conn()
        try:
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE sender = ? AND role = 'user' AND created_at > ?",
                (sender, one_hour_ago),
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def set_system_prompt(self, phone: str, prompt: str):
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO user_settings (phone, system_prompt, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(phone) DO UPDATE SET system_prompt = excluded.system_prompt, updated_at = CURRENT_TIMESTAMP",
                (phone, prompt),
            )
            conn.commit()
        finally:
            conn.close()

    def get_system_prompt(self, phone: str) -> str | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT system_prompt FROM user_settings WHERE phone = ?",
                (phone,),
            ).fetchone()
            return row["system_prompt"] if row else None
        finally:
            conn.close()

    def get_stats(self, sender: str) -> dict:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as total FROM messages WHERE sender = ?",
                (sender,),
            ).fetchone()
            return {"total_messages": row["total"] if row else 0}
        finally:
            conn.close()
