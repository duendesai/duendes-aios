"""
Agent service — wraps the existing Python bot logic.
Imports from scripts/ which is added to sys.path in main.py.
"""
import logging
from typing import Optional

logger = logging.getLogger("aios-api")

DEPT_MAP = {
    "orchestrator": "orchestrator",
    "cmo": "cmo",
    "sdr": "sdr",
    "cfo": "cfo",
    "cs": "cs",
    "ae": "ae",
    "coo": "coo",
}


async def run_agent(dept: str, message: str, thread_key: Optional[str] = None) -> str:
    """
    Run an agent for a given department.
    Wraps ask_department() from slack_bot.py.
    """
    if dept not in DEPT_MAP:
        raise ValueError(f"Unknown dept: {dept}")

    try:
        # Lazy import to avoid startup failures if scripts/ isn't available
        from slack_bot import ask_department

        thread_key = thread_key or f"api:{dept}"
        response = await ask_department(dept, message, thread_key)
        return response
    except ImportError as e:
        logger.warning(f"Could not import slack_bot: {e} — using mock response")
        return _mock_response(dept, message)
    except Exception as e:
        logger.error(f"Agent error for dept={dept}: {e}")
        raise


def _mock_response(dept: str, message: str) -> str:
    """Fallback when slack_bot.py is not available (dev mode)."""
    return (
        f"**[{dept.upper()} — modo desarrollo]**\n\n"
        f"Recibí tu mensaje: _{message}_\n\n"
        "El backend de agentes no está conectado todavía. "
        "Cuando arranques el motor Python completo, las respuestas reales aparecerán aquí."
    )
