"""
`DualWriteCRMClient` — compositor del puerto `CRMClient` que escribe en dos
adaptadores (`primary` + `secondary`) durante la ventana de validación del piloto
y durante la ventana de seguridad post-cutover.

Genérico en roles (design §4):
- Piloto:        `primary=Airtable, secondary=Twenty`.
- Post-cutover:  `primary=Twenty,   secondary=Airtable` (dual-write invertido).

Semántica (spec crm-dual-write, Requirement: orden y semántica de fallo):
- `create_lead`: escribe primero en `primary`. Si `primary` falla, propaga el
  error TAL CUAL y NO toca `secondary`. Si `primary` tiene éxito, intenta
  `secondary`; si `secondary` falla, se captura y loguea (`logger.error`), NUNCA
  propaga ni bloquea al caller. Devuelve SIEMPRE el `LeadRef` de `primary`.
- La idempotencia de cada escritura la resuelve internamente cada adaptador
  (pre-check `find_lead`, D1). Este compositor NO reimplementa ese pre-check.
- Lecturas y `update_lead`/`find_lead`/`get_lead` delegan en `primary` (fuente de
  verdad activa).
"""
from __future__ import annotations

import logging

from services.crm.models import Lead, LeadPatch, LeadRef
from services.crm.port import CRMClient

logger = logging.getLogger(__name__)


class DualWriteCRMClient:
    """Escribe en `primary` (bloqueante) y espeja en `secondary` (best-effort)."""

    def __init__(self, primary: CRMClient, secondary: CRMClient) -> None:
        self._primary = primary
        self._secondary = secondary

    async def create_lead(self, lead: Lead) -> LeadRef:
        # 1. primary bloqueante: si falla, propaga y NO toca secondary.
        ref = await self._primary.create_lead(lead)

        # 2. secondary best-effort: fallo capturado + logueado, nunca propaga.
        try:
            await self._secondary.create_lead(lead)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Dual-write secondary create_lead falló (primary_ref=%s, "
                "email=%s, cal_booking_id=%s): %s",
                ref.id,
                lead.email,
                lead.cal_booking_id,
                exc,
            )
        return ref

    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef:
        # update delega en primary (fuente de verdad). El espejo del secondary en
        # updates se resolvería por reconciliación/paridad, no en caliente
        # (design §4: reads/update delegan en primary).
        return await self._primary.update_lead(ref, changes)

    async def get_lead(self, ref: LeadRef) -> Lead | None:
        return await self._primary.get_lead(ref)

    async def find_lead(
        self,
        *,
        email: str | None = None,
        cal_booking_id: str | None = None,
    ) -> LeadRef | None:
        return await self._primary.find_lead(
            email=email, cal_booking_id=cal_booking_id
        )
