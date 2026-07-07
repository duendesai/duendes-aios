"""
Puerto hexagonal `CRMClient` — contrato CRUD provider-agnostic del pipeline
Leads/demos.

Todo llamador (`routers/calls.py`, workflow n8n vía endpoint) escribe contra esta
interfaz, nunca contra un SDK de proveedor. Los adaptadores concretos
(`AirtableCRMAdapter`, `TwentyCRMAdapter`, `DualWriteCRMClient`) la satisfacen.

Ver `openspec/changes/crm/specs/crm-port/spec.md`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from services.crm.models import Lead, LeadPatch, LeadRef


@runtime_checkable
class CRMClient(Protocol):
    """Contrato mínimo del pipeline Leads/demos.

    Firmas agnósticas de proveedor: no exponen `base_id` de Airtable ni
    `objectMetadataId` de Twenty. Cualquier detalle de proveedor se resuelve dentro
    del adaptador.
    """

    async def create_lead(self, lead: Lead) -> LeadRef:
        """Crea (o reutiliza, por idempotencia) el lead y devuelve su `LeadRef`.

        Idempotente por email + guardia por `cal_booking_id`: si ya existe un lead
        con ese email o ese `cal_booking_id`, devuelve el existente sin duplicar.
        El pre-check vive DENTRO de cada adaptador (no solo en el compositor
        dual-write), para sobrevivir al cutover con un único backend activo.
        """
        ...

    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef:
        """Actualiza parcialmente el lead. Los campos `None` del patch NO se tocan."""
        ...

    async def get_lead(self, ref: LeadRef) -> Lead | None:
        """Lee el lead por su referencia. `None` si no existe."""
        ...

    async def find_lead(
        self,
        *,
        email: str | None = None,
        cal_booking_id: str | None = None,
    ) -> LeadRef | None:
        """Busca un lead por email y/o `cal_booking_id`.

        Devuelve el `LeadRef` que matchea por email; si no matchea por email pero sí
        por `cal_booking_id`, devuelve ese. `None` si ningún criterio matchea.
        """
        ...
