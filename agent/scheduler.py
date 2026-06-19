import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    values = set()
    for part in field.split(","):
        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = min_val if base == "*" else int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            low, high = part.split("-", 1)
            values.update(range(int(low), int(high) + 1))
        else:
            values.add(int(part))
    return values


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    if dt.minute not in _parse_cron_field(minute, 0, 59):
        return False
    if dt.hour not in _parse_cron_field(hour, 0, 23):
        return False
    if dt.day not in _parse_cron_field(dom, 1, 31):
        return False
    if dt.month not in _parse_cron_field(month, 1, 12):
        return False
    if dt.weekday() not in _parse_cron_field(dow.replace("7", "0"), 0, 6):
        return False
    return True


class Scheduler:
    def __init__(self, db_path: str, callback=None):
        self.db_path = db_path
        self.callback = callback
        self._running = False
        self._thread = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    name TEXT NOT NULL,
                    cron_expr TEXT NOT NULL,
                    task_prompt TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_run DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sched_sender_name
                    ON scheduled_tasks(sender, name);
            """)
            conn.commit()
        finally:
            conn.close()

    def add_task(self, sender: str, name: str, cron_expr: str, prompt: str) -> str:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return f"Invalid cron expression: {cron_expr}. Format: min hour dom month dow"
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO scheduled_tasks (sender, name, cron_expr, task_prompt) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(sender, name) DO UPDATE SET "
                "cron_expr = excluded.cron_expr, task_prompt = excluded.task_prompt, "
                "enabled = 1",
                (sender, name, cron_expr, prompt),
            )
            conn.commit()
            return f"Scheduled task '{name}' with cron: {cron_expr}"
        finally:
            conn.close()

    def remove_task(self, sender: str, name: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM scheduled_tasks WHERE sender = ? AND name = ?",
                (sender, name),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_tasks(self, sender: str) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT name, cron_expr, task_prompt, enabled, last_run, created_at "
                "FROM scheduled_tasks WHERE sender = ? ORDER BY created_at",
                (sender,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_due_tasks(self) -> list[dict]:
        now = datetime.utcnow()
        one_min_ago = (now - timedelta(seconds=90)).isoformat()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, sender, name, cron_expr, task_prompt FROM scheduled_tasks "
                "WHERE enabled = 1 AND (last_run IS NULL OR last_run < ?)",
                (one_min_ago,),
            ).fetchall()
            due = []
            for r in rows:
                if cron_matches(r["cron_expr"], now):
                    due.append(dict(r))
                    conn.execute(
                        "UPDATE scheduled_tasks SET last_run = ? WHERE id = ?",
                        (now.isoformat(), r["id"]),
                    )
            conn.commit()
            return due
        finally:
            conn.close()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def _run_loop(self):
        while self._running:
            try:
                due_tasks = self.get_due_tasks()
                for task in due_tasks:
                    logger.info(
                        "Running scheduled task '%s' for %s",
                        task["name"],
                        task["sender"],
                    )
                    if self.callback:
                        try:
                            self.callback(task["sender"], task["task_prompt"])
                        except Exception:
                            logger.exception(
                                "Error executing scheduled task: %s", task["name"]
                            )
            except Exception:
                logger.exception("Scheduler loop error")
            time.sleep(30)
