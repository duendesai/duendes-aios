"""
Tests de `book_demo_and_create_lead`: semántica de la escritura CRM tras el
booking de Cal.com (finding #4 de la revisión, 2026-07-03).

Decisión de Oscar: un fallo del CRM NO debe reportarse como booking fallido (el
booking de Cal.com ya se creó). Se surfacea en la respuesta vía `crm_sync_failed`
(200 + flag), no se propaga como 502. Estos tests fijan ese contrato.
"""
from __future__ import annotations

from services.calls_service import book_demo_and_create_lead
from services.crm.errors import CRMError
from services.crm.models import LeadRef


class _FakeCalcom:
    async def create_booking(self, **kwargs):
        return {
            "booking_uid": "BK-UID-1",
            "booking_id": "BK-1",
            "meeting_url": "https://meet.example/abc",
            "start": "2026-07-10T09:00:00+00:00",
            "end": "2026-07-10T09:30:00+00:00",
        }


class _FakeAir:
    def __init__(self) -> None:
        self.updates: list[tuple] = []

    async def update_record(self, base, table, record_id, fields):
        self.updates.append((base, table, record_id, fields))
        return {}


class _FakeCrmOK:
    async def create_lead(self, lead):
        return LeadRef(id="p1", provider="twenty", url="https://crm.duendes.net/p1")


class _FakeCrmFail:
    async def create_lead(self, lead):
        raise CRMError("Twenty devolvió 500", status_code=500)


_PAYLOAD = {
    "prospect_id": "recABC",
    "slot_start": "2026-07-10T09:00:00Z",
    "attendee_name": "Ana Pérez",
    "attendee_email": "ana@clinica.example",
    "attendee_phone": "+34600000000",
    "notes": "Interesada en recepcionista",
    "empresa": "Clínica Ana",
    "sector": "Clínica Dental",
}


async def test_booking_crm_ok_reports_success():
    air = _FakeAir()
    result = await book_demo_and_create_lead(air, _FakeCalcom(), _FakeCrmOK(), dict(_PAYLOAD))

    assert result["crm_sync_failed"] is False
    assert result["crm_error"] is None
    assert result["lead_id"] == "p1"
    assert result["crm_url"] == "https://crm.duendes.net/p1"
    assert result["booking_uid"] == "BK-UID-1"


async def test_booking_crm_failure_is_surfaced_not_silent():
    air = _FakeAir()
    result = await book_demo_and_create_lead(air, _FakeCalcom(), _FakeCrmFail(), dict(_PAYLOAD))

    # El booking de Cal.com se creó → se reporta con todos sus datos.
    assert result["booking_uid"] == "BK-UID-1"
    assert result["meeting_url"] == "https://meet.example/abc"

    # ...pero el CRM falló → surfaceado explícitamente, nunca en silencio.
    assert result["crm_sync_failed"] is True
    assert "500" in (result["crm_error"] or "")
    assert result["lead_id"] is None
    assert result["crm_url"] is None

    # El paso 3 (PATCH a malaga) se intenta igual: queda breadcrumb "Demo agendada".
    assert air.updates, "el PATCH a malaga debe intentarse aunque falle el CRM"
