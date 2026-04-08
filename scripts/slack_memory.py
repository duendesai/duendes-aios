"""
Duendes AIOS — Slack Memory Bridge
Connects Slack bot conversations to Engram persistent memory.
"""
import logging
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("duendes-slack.memory")
ENGRAM_URL = os.getenv("ENGRAM_URL", "http://127.0.0.1:7437")
PROJECT = "gentleman-ai"

DEPT_TOPIC_KEYS = {
    "orchestrator": "slack/orquestador",
    "cmo": "slack/marketing",
    "sdr": "slack/captacion",
    "ae": "slack/ventas",
    "coo": "slack/operaciones",
    "cfo": "slack/finanzas",
    "cs": "slack/clientes",
}


async def search_dept_memory(dept: str, query: str, max_results: int = 3) -> str:
    """Search Engram for relevant memories for a department.

    Returns a formatted string of relevant memories, or "" if nothing found
    or Engram is unavailable.
    """
    try:
        # Truncar query a 200 chars — URLs largas revientan Engram con 500
        search_query = query[:200]
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{ENGRAM_URL}/search",
                params={"q": search_query, "project": PROJECT, "limit": max_results},
            )
            r.raise_for_status()
            results = r.json()
            if not results:
                return ""

        topic_key = DEPT_TOPIC_KEYS.get(dept, f"slack/{dept}")
        dept_results = [res for res in results if res.get("topic_key") == topic_key]
        if not dept_results:
            dept_results = results[:max_results]

        lines = []
        for res in dept_results[:max_results]:
            title = res.get("title", "")
            content = res.get("content", "")
            snippet = content[:200].replace("\n", " ") if content else ""
            if title or snippet:
                lines.append(f"- {title}: {snippet}")

        if not lines:
            return ""

        return "[Memoria relevante]\n" + "\n".join(lines)
    except Exception:
        return ""


async def save_dept_memory(dept: str, title: str, content: str) -> bool:
    """Save an observation to Engram for a department.

    Returns True on success, False on any failure. Never raises.
    """
    topic_key = DEPT_TOPIC_KEYS.get(dept, f"slack/{dept}")
    payload = {
        "type": "decision",
        "title": title,
        "content": content,
        "project": PROJECT,
        "scope": "project",
        "topic_key": topic_key,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{ENGRAM_URL}/observations", json=payload)
            r.raise_for_status()
        return True
    except Exception:
        return False


def should_save_memory(text: str, response: str) -> bool:
    """Heuristic to determine if an interaction is worth persisting.

    Saves if the response is substantial AND the user message contains
    business-relevant keywords.
    """
    if len(response) <= 200:
        return False

    keywords = (
        "propuesta", "precio", "cliente", "deal", "decisión", "acuerdo",
        "contrato", "€", "cerrado", "ganado", "perdido", "objetivo",
    )
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


async def get_dept_context(dept: str) -> str:
    """Retrieve recent context for a department from Engram.

    Returns a formatted snippet of the last 3 observations, or "".
    """
    topic_key = DEPT_TOPIC_KEYS.get(dept, f"slack/{dept}")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{ENGRAM_URL}/search",
                params={"q": topic_key, "project": PROJECT, "limit": 3},
            )
            r.raise_for_status()
            results = r.json()
            if not results:
                return ""

        dept_results = [res for res in results if res.get("topic_key") == topic_key]
        if not dept_results:
            return ""

        lines = []
        for res in dept_results:
            title = res.get("title", "")
            content = res.get("content", "")
            snippet = content[:200].replace("\n", " ") if content else ""
            if title or snippet:
                lines.append(f"- {title}: {snippet}")

        if not lines:
            return ""

        return "[Contexto reciente]\n" + "\n".join(lines)
    except Exception:
        return ""
