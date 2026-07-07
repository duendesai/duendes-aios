"""
Paquete CRM — puerto hexagonal `CRMClient` y sus adaptadores.

El pipeline Leads/demos escribe contra el puerto (`port.CRMClient`), no contra un
proveedor concreto. Adaptadores intercambiables:

- `AirtableCRMAdapter` — envuelve `services.airtable_multi.AirtableMultiClient`.
- `TwentyCRMAdapter`  — REST/GraphQL contra Twenty self-hosted.
- `DualWriteCRMClient` — compone dos adaptadores (primary + secondary espejo).

El toggle vive en `config.Settings.crm_backend` y se resuelve en `deps.get_crm()`.
Ver `openspec/changes/crm/design.md`.
"""
from __future__ import annotations

from services.crm.airtable_adapter import AirtableCRMAdapter
from services.crm.dual_write import DualWriteCRMClient
from services.crm.errors import CRMError
from services.crm.models import Lead, LeadPatch, LeadRef
from services.crm.port import CRMClient
from services.crm.twenty_adapter import TwentyCRMAdapter

__all__ = [
    "AirtableCRMAdapter",
    "CRMClient",
    "CRMError",
    "DualWriteCRMClient",
    "Lead",
    "LeadPatch",
    "LeadRef",
    "TwentyCRMAdapter",
]
