"""
Duendes AIOS — AgentOps Observabilidad
Instrumenta automáticamente todas las llamadas a Anthropic y OpenAI.
Importado al inicio de: bot.py, brief.py, aios_monitor.py

Si la key no está configurada, no hace nada (no rompe el sistema).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("duendes-aios.agentops")

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY", "")


def setup() -> bool:
    if not AGENTOPS_API_KEY:
        logger.debug("AgentOps: key no configurada — observabilidad desactivada")
        return False
    try:
        import agentops
        agentops.init(api_key=AGENTOPS_API_KEY, auto_start_session=False)
        logger.info("AgentOps: observabilidad activa")
        return True
    except Exception as exc:
        logger.warning("AgentOps: error al inicializar — %s", exc)
        return False


# Auto-setup al importar
setup()
