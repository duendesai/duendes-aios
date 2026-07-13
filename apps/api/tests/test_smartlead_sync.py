"""
Tests de `smartlead_sync.sync_campaign` marcando "No llamar" en el backend activo (D2).

Riesgo de cumplimiento (RGPD/opt-out): cuando un email se da de baja en Smartlead
(is_unsubscribed) o cae en categoría Not Interested / Do Not Contact, el `No llamar`
tiene que quedar marcado en el backend que el comercial usa de verdad:
  - dialer_backend="airtable" (default) → PATCH `No llamar=true` en `malaga` (Airtable).
  - dialer_backend="twenty"             → `noLlamar=true` en el `prospecto` de Twenty.

Todo el I/O de Airtable/Smartlead se sustituye con monkeypatch; no hay red.
"""
from __future__ import annotations

import pytest

from services import smartlead_sync
from services.crm.models import option_value


def _unsub_stat(email="baja@bufete.es"):
    return {
        "lead_email": email,
        "stats_id": "s1",
        "is_unsubscribed": True,
        "lead_category": None,
        "sent_time": "2026-07-01T10:00:00Z",
        "email_subject": "Asunto",
        "email_message": "<p>Cuerpo</p>",
    }


class _FakeProspecto:
    """Fake de TwentyProspectoClient: mapea email→id y captura updates."""

    def __init__(self, prospectos):
        # prospectos: lista de {"id", "email", "noLlamar"}
        self._nodes = prospectos
        self.updated: list[tuple[str, dict]] = []

    async def list_all(self):
        return self._nodes

    async def update(self, prospecto_id, fields):
        self.updated.append((prospecto_id, fields))


def _stub_airtable_io(monkeypatch, stats):
    """Neutraliza el I/O de Smartlead y Airtable dejando la lógica pura del sync."""

    async def fake_smartlead_stats(client, api_key, campaign_id):
        return stats

    async def fake_airtable_list(client, api_key, table, **params):
        return []  # malaga vacía + Emails vacíos: sin gemelo en Airtable

    async def fake_airtable(client, api_key, method, path, *, params=None, json=None):
        return {"id": "emailRec", "fields": {}}  # writes a Emails: no-op

    monkeypatch.setattr(smartlead_sync, "_smartlead_stats", fake_smartlead_stats)
    monkeypatch.setattr(smartlead_sync, "_airtable_list", fake_airtable_list)
    monkeypatch.setattr(smartlead_sync, "_airtable", fake_airtable)


async def test_unsubscribe_marks_no_llamar_in_twenty(monkeypatch):
    _stub_airtable_io(monkeypatch, [_unsub_stat("baja@bufete.es")])
    pc = _FakeProspecto([{"id": "tw1", "email": "baja@bufete.es", "noLlamar": False}])

    res = await smartlead_sync.sync_campaign(
        smartlead_api_key="SL",
        airtable_api_key="AK",
        campaign_id=1,
        campaign_name="Despachos Madrid",
        dialer_backend="twenty",
        prospecto_client=pc,
    )

    assert res["marked_no_llamar"] == 1
    assert len(pc.updated) == 1
    pid, fields = pc.updated[0]
    assert pid == "tw1"
    assert fields["noLlamar"] is True
    assert fields["estado"] == option_value("No llamar")


async def test_unsubscribe_unknown_email_in_twenty_marks_nothing(monkeypatch):
    """Si el email dado de baja no existe como prospecto en Twenty, no se marca nada."""
    _stub_airtable_io(monkeypatch, [_unsub_stat("fantasma@bufete.es")])
    pc = _FakeProspecto([{"id": "tw1", "email": "otro@bufete.es", "noLlamar": False}])

    res = await smartlead_sync.sync_campaign(
        smartlead_api_key="SL",
        airtable_api_key="AK",
        campaign_id=1,
        campaign_name="Despachos Madrid",
        dialer_backend="twenty",
        prospecto_client=pc,
    )

    assert res["marked_no_llamar"] == 0
    assert pc.updated == []


async def test_default_airtable_path_does_not_touch_twenty(monkeypatch):
    """Modo default (airtable): no toca Twenty aunque haya baja (regresión-cero)."""
    _stub_airtable_io(monkeypatch, [_unsub_stat("baja@bufete.es")])
    pc = _FakeProspecto([{"id": "tw1", "email": "baja@bufete.es", "noLlamar": False}])

    res = await smartlead_sync.sync_campaign(
        smartlead_api_key="SL",
        airtable_api_key="AK",
        campaign_id=1,
        campaign_name="Despachos Madrid",
    )

    # malaga vacía → no hay prospect_id en Airtable → nada que marcar allí,
    # y desde luego NADA en Twenty (no se le pasó cliente).
    assert pc.updated == []
    assert res["marked_no_llamar"] == 0
