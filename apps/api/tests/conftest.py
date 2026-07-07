"""
Scaffolding mínimo de pytest para `apps/api`.

`apps/api` usa imports planos (`from services...`, `from config import ...`), como
en `main.py`/`teams_main.py` (que corren con el cwd en `apps/api`). Insertamos el
directorio `apps/api` en `sys.path` para que los tests resuelvan esos imports sin
necesidad de instalar el paquete ni de un layout `src/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# apps/api (padre de tests/) al frente del path de imports.
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
