"""
Tests de `despachos_import.import_sent_leads` respetando `DIALER_BACKEND` (D1).

El import recurrente trae al dialer los leads que ya recibieron email. El ORIGEN de
lectura sigue siendo Airtable (base "duendes OUTREACH"), pero el DESTINO de escritura
debe seguir el backend activo del dialer:
  - dialer_backend="airtable" (default) → crea en `malaga` de Airtable (flujo vivo).
  - dialer_backend="twenty"             → crea el `prospecto` en Twenty, NO en Airtable.

El cliente Twenty y Smartlead se sustituyen por fakes; no hay red.
"""
from __future__ import annotations

import pytest

from services import despachos_import
from services.airtable_multi import BASE_LUCIA, TABLE_MALAGA
from services.crm.models import option_value


async def _fake_stats(client, api_key, campaign_id):
    """Un solo email enviado en Smartlead."""
    return [{"lead_email": "abogado@bufete.es", "sent_time": "2026-07-01T10:00:00Z"}]


_SOURCE_LEAD = {
    "id": "recSrc",
    "fields": {
        "email": "abogado@bufete.es",
        "company_name": "Bufete X",
        "phone": "+34600111222",
        "city": "Madrid",
        "sector": "Legal",
        "contact_name": "Ana",
    },
}


class _FakeAir:
    """Fake de AirtableMultiClient: sirve el origen y captura las escrituras."""

    def __init__(self, source_records, existing_malaga=None):
        self._source = source_records
        self._existing = existing_malaga or []
        self.created: list[dict] = []

    async def list_records(self, base_id, table, *, fields=None, max_records=None, **kw):
        if base_id == BASE_LUCIA and table == TABLE_MALAGA:
            return self._existing
        return self._source

    async def create_record(self, base_id, table, fields, *, typecast=False):
        self.created.append(fields)
        return {"id": "recNew"}


class _FakeProspecto:
    """Fake de TwentyProspectoClient: idempotencia por email + captura de creates."""

    def __init__(self, existing_emails=()):
        self._existing = list(existing_emails)
        self.created: list[dict] = []

    async def list_all(self):
        return [{"email": e} for e in self._existing]

    async def create(self, fields):
        self.created.append(fields)
        return {"id": "twNew"}


async def test_import_creates_in_twenty_when_dialer_backend_twenty(monkeypatch):
    monkeypatch.setattr(despachos_import, "_smartlead_stats", _fake_stats)
    air = _FakeAir(source_records=[_SOURCE_LEAD])
    pc = _FakeProspecto(existing_emails=[])

    res = await despachos_import.import_sent_leads(
        air, "SL_KEY", "despachos-madrid",
        dialer_backend="twenty", prospecto_client=pc,
    )

    assert res["created"] == 1
    # Creado en Twenty...
    assert len(pc.created) == 1
    payload = pc.created[0]
    assert payload["email"] == "abogado@bufete.es"
    assert payload["campana"] == option_value("Despachos Madrid")
    assert payload["estado"] == option_value("Pendiente")
    # ...y NUNCA en Airtable en modo twenty.
    assert air.created == []


async def test_import_creates_in_airtable_by_default(monkeypatch):
    monkeypatch.setattr(despachos_import, "_smartlead_stats", _fake_stats)
    air = _FakeAir(source_records=[_SOURCE_LEAD], existing_malaga=[])

    res = await despachos_import.import_sent_leads(air, "SL_KEY", "despachos-madrid")

    assert res["created"] == 1
    assert len(air.created) == 1
    assert air.created[0]["Email contacto"] == "abogado@bufete.es"


async def test_import_twenty_is_idempotent_by_email(monkeypatch):
    monkeypatch.setattr(despachos_import, "_smartlead_stats", _fake_stats)
    air = _FakeAir(source_records=[_SOURCE_LEAD])
    pc = _FakeProspecto(existing_emails=["abogado@bufete.es"])  # ya está en Twenty

    res = await despachos_import.import_sent_leads(
        air, "SL_KEY", "despachos-madrid",
        dialer_backend="twenty", prospecto_client=pc,
    )

    assert res["created"] == 0
    assert pc.created == []
    assert air.created == []
