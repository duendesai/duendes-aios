"""
Duendes AIOS — Slack History Logger
Stores all Slack conversations in SQLite for brief analysis and historical querying.
DB: data/slack_history.db
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "slack_history.db"

log = logging.getLogger("duendes-slack-logger")


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

def _init_db() -> None:
    """Create data/ directory and initialize the SQLite schema."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT NOT NULL,
                    dept TEXT NOT NULL,
                    text TEXT NOT NULL,
                    is_bot INTEGER NOT NULL DEFAULT 0,
                    ts TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.execute("""
                CREATE TABLE IF NOT EXISTS thread_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_key ON thread_messages (thread_key)")
        conn.execute("""
                CREATE TABLE IF NOT EXISTS thread_tasks (
                    thread_key TEXT PRIMARY KEY,
                    context TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.close()
        log.info("slack_logger: DB initialised at %s", DB_PATH)
    except Exception as exc:
        log.error("slack_logger: _init_db failed: %s", exc)


# Initialise on import
_init_db()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_message(
    channel_name: str,
    dept: str,
    text: str,
    is_bot: bool = False,
    ts: str = "",
) -> None:
    """Insert a single message into the messages table. Never raises."""
    try:
        truncated = text[:2000] if len(text) > 2000 else text
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        with conn:
            conn.execute(
                "INSERT INTO messages (channel_name, dept, text, is_bot, ts) VALUES (?, ?, ?, ?, ?)",
                (channel_name, dept, truncated, 1 if is_bot else 0, ts),
            )
        conn.close()
    except Exception as exc:
        log.error("slack_logger: log_message failed: %s", exc)


def save_thread_message(thread_key: str, role: str, content: str) -> None:
    """Persist a single message from a thread to SQLite."""
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        with conn:
            conn.execute(
                "INSERT INTO thread_messages (thread_key, role, content) VALUES (?, ?, ?)",
                (thread_key, role, content[:10000]),
            )
        conn.close()
    except Exception as exc:
        log.error("slack_logger: save_thread_message failed: %s", exc)


def load_thread_history(thread_key: str, limit: int = 20) -> list[dict]:
    """Load the last N messages of a thread from SQLite, ordered oldest-first."""
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT role, content FROM ("
            "  SELECT role, content, id FROM thread_messages"
            "  WHERE thread_key = ? ORDER BY id DESC LIMIT ?"
            ") ORDER BY id ASC",
            (thread_key, limit),
        )
        rows = [{"role": r["role"], "content": r["content"]} for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        log.error("slack_logger: load_thread_history failed: %s", exc)
        return []


def save_task_context(thread_key: str, context: str) -> None:
    """Persist task+plan context for a channel thread. Survives bot restarts."""
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO thread_tasks (thread_key, context) VALUES (?, ?)",
                (thread_key, context),
            )
        conn.close()
    except Exception as exc:
        log.error("slack_logger: save_task_context failed: %s", exc)


def load_task_context(thread_key: str) -> str:
    """Load persisted task+plan context for a channel thread."""
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        cursor = conn.execute("SELECT context FROM thread_tasks WHERE thread_key = ?", (thread_key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception as exc:
        log.error("slack_logger: load_task_context failed: %s", exc)
        return ""


def get_messages_since(hours: int = 24) -> list[dict]:
    """Return messages from the last N hours, ordered by created_at ASC."""
    try:
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT channel_name, dept, text, is_bot, created_at "
            "FROM messages WHERE created_at >= ? ORDER BY created_at ASC",
            (since,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        log.error("slack_logger: get_messages_since failed: %s", exc)
        return []


def get_yesterday_activity() -> dict:
    """
    Return a summary dict of yesterday's activity:
      total_messages, by_channel, by_dept, oscar_messages, bot_responses
    """
    result: dict = {
        "total_messages": 0,
        "by_channel": {},
        "by_dept": {},
        "oscar_messages": [],
        "bot_responses": 0,
    }
    try:
        now = datetime.utcnow()
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_end = yesterday_start + timedelta(days=1)

        since = yesterday_start.strftime("%Y-%m-%d %H:%M:%S")
        until = yesterday_end.strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # All messages in window
        cursor = conn.execute(
            "SELECT channel_name, dept, text, is_bot, created_at "
            "FROM messages WHERE created_at >= ? AND created_at < ? ORDER BY created_at ASC",
            (since, until),
        )
        rows = cursor.fetchall()

        result["total_messages"] = len(rows)
        by_channel: dict[str, int] = {}
        by_dept: dict[str, int] = {}
        oscar_messages: list[dict] = []
        bot_responses = 0

        for r in rows:
            ch = r["channel_name"]
            dt = r["dept"]
            by_channel[ch] = by_channel.get(ch, 0) + 1
            by_dept[dt] = by_dept.get(dt, 0) + 1
            if r["is_bot"]:
                bot_responses += 1
            else:
                oscar_messages.append(dict(r))

        result["by_channel"] = by_channel
        result["by_dept"] = by_dept
        result["oscar_messages"] = oscar_messages[-50:]
        result["bot_responses"] = bot_responses

        conn.close()
    except Exception as exc:
        log.error("slack_logger: get_yesterday_activity failed: %s", exc)

    return result


def get_channel_history(channel_name: str, limit: int = 20) -> list[dict]:
    """Return the last N messages for a specific channel."""
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT channel_name, dept, text, is_bot, created_at "
            "FROM messages WHERE channel_name = ? ORDER BY created_at DESC LIMIT ?",
            (channel_name, limit),
        )
        rows = list(reversed([dict(r) for r in cursor.fetchall()]))
        conn.close()
        return rows
    except Exception as exc:
        log.error("slack_logger: get_channel_history failed: %s", exc)
        return []


def format_activity_for_brief(activity: dict) -> str:
    """Format yesterday's activity as a Slack-markdown text block for the brief."""
    lines = ["*Actividad AIOS (últimas 24h)*"]

    active_channels = sorted(activity.get("by_channel", {}).keys())
    if active_channels:
        lines.append(f"Canales activos: {', '.join('#' + c for c in active_channels)}")

    lines.append(f"Mensajes totales: {activity.get('total_messages', 0)}")
    lines.append(
        f"Respuestas del bot: {activity.get('bot_responses', 0)} · "
        f"Mensajes de Oscar: {len(activity.get('oscar_messages', []))}"
    )

    oscar_msgs = activity.get("oscar_messages", [])
    if oscar_msgs:
        lines.append("")
        # Group Oscar's messages by channel for a readable summary
        by_ch: dict[str, list[str]] = {}
        for m in oscar_msgs:
            ch = m.get("channel_name", "?")
            snippet = m.get("text", "")[:60].replace("\n", " ")
            by_ch.setdefault(ch, []).append(snippet)

        for ch, snippets in sorted(by_ch.items()):
            lines.append(f"• *#{ch}*: {' / '.join(snippets[:3])}")

    return "\n".join(lines)


def search_history(query: str, days: int = 30) -> list[dict]:
    """Full-text search over messages using parameterized LIKE query."""
    try:
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT channel_name, dept, text, is_bot, created_at "
            "FROM messages WHERE text LIKE ? AND created_at >= ? ORDER BY created_at ASC",
            (f"%{query}%", since),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        log.error("slack_logger: search_history failed: %s", exc)
        return []
