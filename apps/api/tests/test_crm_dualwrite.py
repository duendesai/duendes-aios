"""
Tests de semántica de `DualWriteCRMClient` (spec crm-dual-write, Requirement:
orden y semántica de fallo).

Usa dos adaptadores fake en memoria que satisfacen el puerto `CRMClient` (sin
HTTP): así se aísla la lógica del compositor de cualquier proveedor real. Cubre:

- Fallo en `secondary` → `create_lead` devuelve el `LeadRef` de `primary`, NO
  propaga, y loguea el fallo (best-effort espejo).
- Fallo en `primary` → propaga tal cual y `secondary` NO se invoca.
- Simétrico en la dirección invertida (primary=Twenty-like, secondary=Airtable-like),
  que es el modo post-cutover (design §4).
"""
from __future__ import annotations

import logging

import pytest

from services.crm.dual_write import DualWriteCRMClient
from services.crm.errors import CRMError
from services.crm.models import Lead, LeadPatch, LeadRef


class _FakeCRMClient:
    """Adaptador CRMClient en memoria, configurable para fallar en `create_lead`."""

    def __init__(self, provider: str, *, raise_on_create: bool = False) -> None:
        self.provider = provider
        self.raise_on_create = raise_on_create
        self.create_calls: list[Lead] = []
        self._store: dict[str, Lead] = {}

    async def create_lead(self, lead: Lead) -> LeadRef:
        self.create_calls.append(lead)
        if self.raise_on_create:
            raise CRMError(f"{self.provider} create boom", status_code=500)
        rid = f"{self.provider}-{len(self._store) + 1}"
        self._store[rid] = lead
        return LeadRef(id=rid, provider=self.provider)  # type: ignore[arg-type]

    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef:
        return ref

    async def get_lead(self, ref: LeadRef) -> Lead | None:
        return self._store.get(ref.id)

    async def find_lead(
        self,
        *,
        email: str | None = None,
        cal_booking_id: str | None = None,
    ) -> LeadRef | None:
        return None


def _lead() -> Lead:
    return Lead(nombre="Ana Pérez", email="ana@x.test", cal_booking_id="cal-dw-1")


# ─── Dirección piloto: primary=Airtable-like, secondary=Twenty-like ────────────


async def test_secondary_failure_does_not_block_and_logs(caplog):
    primary = _FakeCRMClient("airtable")
    secondary = _FakeCRMClient("twenty", raise_on_create=True)
    dual = DualWriteCRMClient(primary, secondary)

    with caplog.at_level(logging.ERROR):
        ref = await dual.create_lead(_lead())

    # Devuelve el ref de PRIMARY, no propaga el fallo del secondary.
    assert ref.provider == "airtable"
    assert ref.id == "airtable-1"
    # secondary SÍ se intentó (best-effort), y su fallo quedó logueado.
    assert len(secondary.create_calls) == 1
    assert any("secondary" in r.getMessage() for r in caplog.records)


async def test_primary_failure_propagates_and_skips_secondary():
    primary = _FakeCRMClient("airtable", raise_on_create=True)
    secondary = _FakeCRMClient("twenty")
    dual = DualWriteCRMClient(primary, secondary)

    with pytest.raises(CRMError):
        await dual.create_lead(_lead())

    # Si primary falla, secondary NO se toca.
    assert len(secondary.create_calls) == 0


# ─── Dirección invertida (post-cutover): primary=Twenty-like, secondary=Airtable-like ─


async def test_inverted_secondary_failure_does_not_block_and_logs(caplog):
    primary = _FakeCRMClient("twenty")
    secondary = _FakeCRMClient("airtable", raise_on_create=True)
    dual = DualWriteCRMClient(primary, secondary)

    with caplog.at_level(logging.ERROR):
        ref = await dual.create_lead(_lead())

    assert ref.provider == "twenty"
    assert ref.id == "twenty-1"
    assert len(secondary.create_calls) == 1
    assert any("secondary" in r.getMessage() for r in caplog.records)


async def test_inverted_primary_failure_propagates_and_skips_secondary():
    primary = _FakeCRMClient("twenty", raise_on_create=True)
    secondary = _FakeCRMClient("airtable")
    dual = DualWriteCRMClient(primary, secondary)

    with pytest.raises(CRMError):
        await dual.create_lead(_lead())

    assert len(secondary.create_calls) == 0
