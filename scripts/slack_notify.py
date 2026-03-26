"""
Duendes AIOS — Slack Notifier (sync)
Sends messages to specific Slack channels from non-async scripts (brief, monitor).
Uses slack_sdk WebClient (sync) instead of Bolt.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("duendes-aios.slack-notify")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

# Channel name → channel ID cache
_channel_cache: dict = {}

def _get_client():
    from slack_sdk import WebClient
    return WebClient(token=SLACK_BOT_TOKEN)

def _resolve_channel(client, channel_name: str) -> str:
    """Resolve channel name to ID, with cache."""
    if channel_name in _channel_cache:
        return _channel_cache[channel_name]
    try:
        resp = client.conversations_list(limit=200)
        for ch in resp["channels"]:
            _channel_cache[ch["name"]] = ch["id"]
        return _channel_cache.get(channel_name, "")
    except Exception as e:
        logger.warning("Could not resolve channel %s: %s", channel_name, e)
        return ""

def send_to_channel(channel_name: str, text: str) -> bool:
    """Send a message to a Slack channel by name. Returns True on success."""
    if not SLACK_BOT_TOKEN:
        logger.debug("SLACK_BOT_TOKEN not set — skipping Slack notification")
        return False
    try:
        client = _get_client()
        channel_id = _resolve_channel(client, channel_name)
        if not channel_id:
            logger.warning("Channel #%s not found", channel_name)
            return False
        client.chat_postMessage(channel=channel_id, text=text, mrkdwn=True)
        logger.info("Slack notification sent to #%s", channel_name)
        return True
    except Exception as e:
        logger.warning("Slack notification failed for #%s: %s", channel_name, e)
        return False

def send_brief(text: str) -> bool:
    """Send the daily brief to #orquestador."""
    return send_to_channel("orquestador", text)

def send_weekly_report(text: str) -> bool:
    """Send the weekly report to #orquestador."""
    return send_to_channel("orquestador", text)

def send_monitor_alert(dept: str, text: str) -> bool:
    """Send a monitor alert to the relevant department channel."""
    dept_channels = {
        "cfo": "finanzas",
        "cs": "clientes",
        "sdr": "captacion",
        "ae": "ventas",
        "coo": "operaciones",
    }
    channel = dept_channels.get(dept, "orquestador")
    return send_to_channel(channel, text)
