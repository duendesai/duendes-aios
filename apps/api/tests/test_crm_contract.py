"""
Test de contrato ligero del puerto `CRMClient` (Fase 8, spec crm-port +
crm-twenty-adapter).

Ejercita `AirtableCRMAdapter` y `TwentyCRMAdapter` contra las MISMAS aserciones,
con el HTTP de cada proveedor mockeado por respx sobre un backend en memoria
(stateful) que reproduce la forma real de las respuestas. Cubre:

- create/get/update/find_lead devuelven `lead_id`/`crm_url`.
- find_lead por email y por cal_booking_id → LeadRef esperado o None.
- Idempotencia: reintentar create_lead con la misma clave (email o cal_booking_id)
  devuelve el lead existente y NO crea un segundo registro, con el adaptador
  operando en solitario (sin DualWriteCRMClient).
- Patch parcial: update_lead con un solo campo + get_lead confirma que el resto
  de campos conservan su valor previo.

No sustituye la medición de paridad real (crm-dual-write); es verificación barata
de forma/contrato, no de datos de producción.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Callable

import httpx
import pytest
import respx

from services.airtable_multi import BASE_CRM, TABLE_LEADS, AirtableMultiClient
from services.crm.airtable_adapter import AirtableCRMAdapter
from services.crm.errors import (
    CRMAuthError,
    CRMError,
    CRMValidationError,
)
from services.crm.models import Lead, LeadPatch, LeadRef
from services.crm.twenty_adapter import TwentyCRMAdapter

TWENTY_BASE = "https://crm.test.local"
AIRTABLE_TABLE = f"https://api.airtable.com/v0/{BASE_CRM}/{TABLE_LEADS}"


def _same_instant(a: str | None, b: str | None) -> bool:
    """Compara dos fechas ISO-8601 por instante (no por string), asumiendo UTC si
    alguna viene sin zona (política de TZ, design §3/§4)."""
    from datetime import timezone

    if a is None or b is None:
        return a == b

    def _parse(v: str) -> datetime:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return _parse(a) == _parse(b)


# ─── Fake Airtable backend (stateful, sobre la REST API real) ──────────────────


class _FakeAirtable:
    """Store en memoria que responde como la REST API de Airtable para la tabla
    `Leads`: list (filterByFormula), get, create, patch. Guarda `fields` tal cual,
    de forma que create con typecast y patch parcial se comportan como el real.
    """

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self._table_url = f"https://api.airtable.com/v0/{BASE_CRM}/{TABLE_LEADS}"

    def register(self, router: respx.Router) -> None:
        # Path base con record-id opcional y query-string opcional. Sin `$` tras el
        # path para tolerar `?pageSize=...&filterByFormula=...`.
        pattern = re.escape(self._table_url) + r"(/rec[A-Za-z0-9]+)?(\?.*)?$"
        router.get(url__regex=pattern).mock(side_effect=self._on_get)
        router.post(url__regex=pattern).mock(side_effect=self._on_post)
        router.patch(url__regex=pattern).mock(side_effect=self._on_patch)

    def _match_record_id(self, url: str) -> str | None:
        m = re.search(r"/(rec[A-Za-z0-9]+)$", url)
        return m.group(1) if m else None

    def _on_get(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        rid = self._match_record_id(url)
        if rid:
            rec = self.records.get(rid)
            if not rec:
                return httpx.Response(404, json={"error": "NOT_FOUND"})
            return httpx.Response(200, json=rec)
        # list con filterByFormula: {Campo}="valor"
        formula = request.url.params.get("filterByFormula", "")
        matched = self._filter(formula)
        return httpx.Response(200, json={"records": matched})

    def _filter(self, formula: str) -> list[dict[str, Any]]:
        m = re.match(r'\{(?P<field>[^}]+)\}="(?P<value>.*)"$', formula)
        if not m:
            return []
        field = m.group("field")
        value = m.group("value").replace('\\"', '"')
        return [
            rec
            for rec in self.records.values()
            if rec.get("fields", {}).get(field) == value
        ]

    def _on_post(self, request: httpx.Request) -> httpx.Response:
        body = _json_body(request)
        fields = body.get("fields", {})
        rid = f"rec{uuid.uuid4().hex[:14]}"
        rec = {"id": rid, "fields": dict(fields)}
        self.records[rid] = rec
        return httpx.Response(200, json=rec)

    def _on_patch(self, request: httpx.Request) -> httpx.Response:
        rid = self._match_record_id(str(request.url).split("?")[0])
        if not rid or rid not in self.records:
            return httpx.Response(404, json={"error": "NOT_FOUND"})
        body = _json_body(request)
        fields = body.get("fields", {})
        # PATCH parcial: fusiona (Airtable solo sobreescribe los campos enviados).
        self.records[rid]["fields"].update(fields)
        return httpx.Response(200, json=self.records[rid])


# ─── Fake Twenty backend (stateful, REST + GraphQL) ────────────────────────────


class _FakeTwenty:
    """Store en memoria que responde como Twenty: REST `/rest/people` (create/get/
    patch) + GraphQL `people(filter)` para find_lead. Guarda el objeto Person con
    los mismos campos que produce el adaptador.
    """

    def __init__(self) -> None:
        self.people: dict[str, dict[str, Any]] = {}

    def register(self, router: respx.Router) -> None:
        pattern = re.escape(f"{TWENTY_BASE}/rest/people") + r"(/[A-Za-z0-9-]+)?(\?.*)?$"
        # GraphQL registrado ANTES para que /graphql no caiga en el pattern REST
        # (rutas respx: la primera que matchea gana; /graphql no matchea, pero es
        # más claro registrarla explícitamente aparte de todos modos).
        router.post(f"{TWENTY_BASE}/graphql").mock(side_effect=self._on_graphql)
        router.post(url__regex=pattern).mock(side_effect=self._on_create)
        router.get(url__regex=pattern).mock(side_effect=self._on_get)
        router.patch(url__regex=pattern).mock(side_effect=self._on_patch)

    def _on_create(self, request: httpx.Request) -> httpx.Response:
        body = _json_body(request)
        pid = str(uuid.uuid4())
        person = dict(body)
        person["id"] = pid
        self.people[pid] = person
        return httpx.Response(201, json={"data": {"createPerson": person}})

    def _on_get(self, request: httpx.Request) -> httpx.Response:
        m = re.search(r"/rest/people/([A-Za-z0-9-]+)$", str(request.url))
        if not m:
            return httpx.Response(404, json={"messages": ["not found"]})
        pid = m.group(1)
        person = self.people.get(pid)
        if not person:
            return httpx.Response(404, json={"messages": ["not found"]})
        return httpx.Response(200, json={"data": {"person": person}})

    def _on_patch(self, request: httpx.Request) -> httpx.Response:
        m = re.search(r"/rest/people/([A-Za-z0-9-]+)$", str(request.url))
        if not m:
            return httpx.Response(404, json={"messages": ["not found"]})
        pid = m.group(1)
        if pid not in self.people:
            return httpx.Response(404, json={"messages": ["not found"]})
        body = _json_body(request)
        # PATCH parcial: fusiona solo los campos presentes.
        self.people[pid].update(body)
        return httpx.Response(200, json={"data": {"updatePerson": self.people[pid]}})

    def _on_graphql(self, request: httpx.Request) -> httpx.Response:
        body = _json_body(request)
        variables = body.get("variables", {})
        where = variables.get("filter", {})
        matched = [p for p in self.people.values() if self._matches(p, where)]
        edges = [{"node": {"id": p["id"]}} for p in matched[:1]]
        return httpx.Response(200, json={"data": {"people": {"edges": edges}}})

    @staticmethod
    def _matches(person: dict[str, Any], where: dict[str, Any]) -> bool:
        if "emails" in where:
            wanted = where["emails"]["primaryEmail"]["eq"]
            return (person.get("emails") or {}).get("primaryEmail") == wanted
        if "calBookingId" in where:
            wanted = where["calBookingId"]["eq"]
            return person.get("calBookingId") == wanted
        return False


def _json_body(request: httpx.Request) -> dict[str, Any]:
    import json

    if not request.content:
        return {}
    return json.loads(request.content.decode("utf-8"))


# ─── Fixtures: cada adaptador con su fake + router respx activo ────────────────

AdapterFactory = Callable[[respx.Router], Any]


@pytest.fixture
def airtable_setup():
    fake = _FakeAirtable()
    adapter = AirtableCRMAdapter(AirtableMultiClient(api_key="test-key"))
    return adapter, fake


@pytest.fixture
def twenty_setup():
    fake = _FakeTwenty()
    adapter = TwentyCRMAdapter(base_url=TWENTY_BASE, api_key="test-key")
    return adapter, fake


def _sample_lead(**overrides: Any) -> Lead:
    data: dict[str, Any] = {
        "nombre": "Ana Pérez",
        "email": "ana@clinica.test",
        "telefono": "+34600111222",
        "empresa": "Clínica Test",
        "sector": "Clínica Dental",
        "fuente": "Outreach",
        "estado": "Reunión agendada",
        "fecha_reunion": "2026-07-10T09:00:00+00:00",
        "cal_booking_id": "cal-abc-123",
        "notas": "Nota inicial",
    }
    data.update(overrides)
    return Lead(**data)


def _params(request_case: str):
    """Devuelve la lista de casos (adaptador, fake, provider) parametrizados."""
    return request_case


# El id del parámetro identifica el adaptador; el fixture correspondiente se
# resuelve dinámicamente vía request.getfixturevalue.
ADAPTERS = ["airtable_setup", "twenty_setup"]


@pytest.fixture(params=ADAPTERS)
def adapter_case(request):
    adapter, fake = request.getfixturevalue(request.param)
    provider = "airtable" if request.param == "airtable_setup" else "twenty"
    with respx.mock(assert_all_called=False) as router:
        fake.register(router)
        yield adapter, fake, provider


# ─── Tests de contrato (ambos adaptadores) ─────────────────────────────────────


async def test_create_lead_returns_ref(adapter_case):
    adapter, _fake, provider = adapter_case
    ref = await adapter.create_lead(_sample_lead())
    assert ref.id
    assert ref.provider == provider
    assert ref.url  # crm_url presente en ambos adaptadores


async def test_get_lead_roundtrips_fields(adapter_case):
    """Los 10 campos de `Lead` sobreviven create→get en AMBOS adaptadores.

    `fecha_reunion` se compara por instante (UTC), no por string, porque Twenty la
    normaliza a UTC canónico antes de escribir (design §3).
    """
    adapter, _fake, _provider = adapter_case
    ref = await adapter.create_lead(_sample_lead())
    fetched = await adapter.get_lead(ref)
    assert fetched is not None
    assert fetched.nombre == "Ana Pérez"
    assert fetched.email == "ana@clinica.test"
    assert fetched.telefono == "+34600111222"
    assert fetched.empresa == "Clínica Test"
    assert fetched.sector == "Clínica Dental"
    assert fetched.fuente == "Outreach"
    assert fetched.estado == "Reunión agendada"
    assert _same_instant(fetched.fecha_reunion, "2026-07-10T09:00:00+00:00")
    assert fetched.cal_booking_id == "cal-abc-123"
    assert fetched.notas == "Nota inicial"


async def test_find_lead_by_email(adapter_case):
    adapter, _fake, _provider = adapter_case
    ref = await adapter.create_lead(_sample_lead())
    found = await adapter.find_lead(email="ana@clinica.test")
    assert found is not None
    assert found.id == ref.id


async def test_find_lead_by_cal_booking_id(adapter_case):
    adapter, _fake, _provider = adapter_case
    ref = await adapter.create_lead(_sample_lead())
    found = await adapter.find_lead(cal_booking_id="cal-abc-123")
    assert found is not None
    assert found.id == ref.id


async def test_find_lead_missing_returns_none(adapter_case):
    adapter, _fake, _provider = adapter_case
    found = await adapter.find_lead(email="nobody@nowhere.test")
    assert found is None


async def test_create_lead_is_idempotent_by_email(adapter_case):
    """Reintentar create con el mismo email devuelve el existente, sin duplicar.

    El adaptador opera EN SOLITARIO (sin DualWriteCRMClient): la idempotencia
    vive en el pre-check find_lead de cada adaptador (D1).
    """
    adapter, fake, provider = adapter_case
    ref1 = await adapter.create_lead(_sample_lead())
    ref2 = await adapter.create_lead(_sample_lead(cal_booking_id="cal-different-999"))
    assert ref1.id == ref2.id
    _assert_store_count(fake, provider, 1)


async def test_create_lead_is_idempotent_by_cal_booking_id(adapter_case):
    """Email distinto pero mismo cal_booking_id → mismo lead (guardia webhook)."""
    adapter, fake, provider = adapter_case
    ref1 = await adapter.create_lead(_sample_lead())
    ref2 = await adapter.create_lead(
        _sample_lead(email="ana.otro@clinica.test", cal_booking_id="cal-abc-123")
    )
    assert ref1.id == ref2.id
    _assert_store_count(fake, provider, 1)


async def test_update_lead_partial_patch_preserves_other_fields(adapter_case):
    """update_lead con un solo campo NO debe tocar el resto (patch parcial).

    Se verifica vía get_lead: sector/notas/fecha_reunion conservan su valor.
    """
    adapter, _fake, _provider = adapter_case
    ref = await adapter.create_lead(_sample_lead())

    patched = await adapter.update_lead(ref, LeadPatch(estado="Propuesta enviada"))
    assert patched.id == ref.id

    after = await adapter.get_lead(ref)
    assert after is not None
    assert after.estado == "Propuesta enviada"
    # Campos NO incluidos en el patch: intactos.
    assert after.sector == "Clínica Dental"
    assert after.notas == "Nota inicial"
    assert after.cal_booking_id == "cal-abc-123"
    assert after.email == "ana@clinica.test"
    # fecha_reunion (que el docstring afirma pero antes no comprobaba): intacta,
    # comparada por instante porque Twenty la normaliza a UTC canónico.
    assert _same_instant(after.fecha_reunion, "2026-07-10T09:00:00+00:00")


def _assert_store_count(fake: Any, provider: str, expected: int) -> None:
    if provider == "airtable":
        assert len(fake.records) == expected
    else:
        assert len(fake.people) == expected


# ─── Test específico Twenty: normalización de valores heredados ────────────────


async def test_twenty_normalizes_legacy_sector_and_estado(twenty_setup):
    """SOLO Twenty: Sector="Clínicas" → Salud, Estado="Nuevo" → estado inicial."""
    adapter, fake = twenty_setup
    with respx.mock(assert_all_called=False) as router:
        fake.register(router)
        ref = await adapter.create_lead(
            _sample_lead(sector="Clínicas", estado="Nuevo", email="norm@test.test",
                         cal_booking_id="cal-norm-1")
        )
        person = fake.people[ref.id]
        assert person["sector"] == "Salud"
        assert person["estadoDemo"] == "Reunión agendada"


async def test_airtable_does_not_normalize_legacy_values(airtable_setup):
    """SOLO Airtable: escribe Sector/Estado tal cual, sin normalizar (flujo vivo)."""
    adapter, fake = airtable_setup
    with respx.mock(assert_all_called=False) as router:
        fake.register(router)
        ref = await adapter.create_lead(
            _sample_lead(sector="Clínicas", estado="Nuevo", email="raw@test.test",
                         cal_booking_id="cal-raw-1")
        )
        rec = fake.records[ref.id]
        assert rec["fields"]["Sector"] == "Clínicas"
        assert rec["fields"]["Estado"] == "Nuevo"


# ─── T-precedence: email gana sobre cal_booking_id en find_lead (ambos) ─────────


async def test_find_lead_email_takes_precedence_over_cal_booking_id(adapter_case):
    """find_lead: el email es la clave primaria y gana; si el email no matchea,
    cae al guardia por cal_booking_id (design §1, D1). Se verifica en AMBOS
    adaptadores con dos leads distintos en el store.
    """
    adapter, _fake, _provider = adapter_case
    ref_a = await adapter.create_lead(
        _sample_lead(email="a@x.test", cal_booking_id="cal-A")
    )
    ref_b = await adapter.create_lead(
        _sample_lead(email="b@x.test", cal_booking_id="cal-B")
    )
    assert ref_a.id != ref_b.id

    # email=E1 + cal=C2 → gana el email → A.
    by_email = await adapter.find_lead(email="a@x.test", cal_booking_id="cal-B")
    assert by_email is not None
    assert by_email.id == ref_a.id

    # email inexistente + cal=C2 → cae al guardia por cal → B.
    by_cal = await adapter.find_lead(email="nadie@x.com", cal_booking_id="cal-B")
    assert by_cal is not None
    assert by_cal.id == ref_b.id


# ─── T-fecha: Twenty normaliza fechaReunion a UTC canónico antes de escribir ────


async def test_twenty_normalizes_fecha_reunion_to_canonical_utc(twenty_setup):
    """SOLO Twenty: `fecha_reunion` con offset no-UTC y naive se escriben ambas como
    UTC ISO-8601 canónico (`2026-07-10T09:00:00+00:00`) en `person['fechaReunion']`.
    """
    adapter, fake = twenty_setup
    with respx.mock(assert_all_called=False) as router:
        fake.register(router)

        # Offset +02:00 → 09:00 UTC.
        ref_off = await adapter.create_lead(
            _sample_lead(
                fecha_reunion="2026-07-10T11:00:00+02:00",
                email="tz@test.test",
                cal_booking_id="cal-tz-1",
            )
        )
        assert fake.people[ref_off.id]["fechaReunion"] == "2026-07-10T09:00:00+00:00"

        # Naive (sin zona) → se asume UTC.
        ref_naive = await adapter.create_lead(
            _sample_lead(
                fecha_reunion="2026-07-10T09:00:00",
                email="naive@test.test",
                cal_booking_id="cal-naive-1",
            )
        )
        assert fake.people[ref_naive.id]["fechaReunion"] == "2026-07-10T09:00:00+00:00"


# ─── T-errors: errores HTTP → CRMError tipado (ambos adaptadores) ──────────────


async def test_twenty_find_lead_auth_error(twenty_setup):
    """Twenty 401 en GraphQL (find_lead) → CRMAuthError con status/detail del proveedor."""
    adapter, _fake = twenty_setup
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{TWENTY_BASE}/graphql").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        with pytest.raises(CRMAuthError) as excinfo:
            await adapter.find_lead(email="x@y.test")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == {"error": "unauthorized"}


async def test_twenty_create_lead_validation_error(twenty_setup):
    """Twenty 422 en el POST de create → CRMValidationError (el pre-check find va vacío)."""
    adapter, _fake = twenty_setup
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{TWENTY_BASE}/graphql").mock(
            return_value=httpx.Response(200, json={"data": {"people": {"edges": []}}})
        )
        router.post(f"{TWENTY_BASE}/rest/people").mock(
            return_value=httpx.Response(422, json={"messages": ["invalid"]})
        )
        with pytest.raises(CRMValidationError) as excinfo:
            await adapter.create_lead(_sample_lead())
    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == {"messages": ["invalid"]}


async def test_twenty_update_lead_server_error(twenty_setup):
    """Twenty 500 en el PATCH de update → CRMError con el status del proveedor."""
    adapter, _fake = twenty_setup
    ref = LeadRef(id="p-500", provider="twenty")
    with respx.mock(assert_all_called=False) as router:
        router.patch(f"{TWENTY_BASE}/rest/people/p-500").mock(
            return_value=httpx.Response(500, json={"messages": ["boom"]})
        )
        with pytest.raises(CRMError) as excinfo:
            await adapter.update_lead(ref, LeadPatch(estado="Ganado"))
    assert excinfo.value.status_code == 500


async def test_twenty_get_lead_missing_returns_none(twenty_setup):
    """Twenty 404 en get → None (no excepción)."""
    adapter, _fake = twenty_setup
    ref = LeadRef(id="missing", provider="twenty")
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{TWENTY_BASE}/rest/people/missing").mock(
            return_value=httpx.Response(404, json={"messages": ["not found"]})
        )
        result = await adapter.get_lead(ref)
    assert result is None


async def test_twenty_create_lead_tolerates_precheck_read_failure(twenty_setup, caplog):
    """FIX 3: si la LECTURA del pre-check (GraphQL) falla, create NO aborta: loguea
    warning y procede a crear. El error del POST de create sí propagaría (otros tests).
    """
    adapter, _fake = twenty_setup
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{TWENTY_BASE}/graphql").mock(
            return_value=httpx.Response(500, json={"messages": ["read boom"]})
        )
        router.post(f"{TWENTY_BASE}/rest/people").mock(
            return_value=httpx.Response(201, json={"data": {"createPerson": {"id": "new-1"}}})
        )
        with caplog.at_level(logging.WARNING):
            ref = await adapter.create_lead(_sample_lead())
    assert ref.id == "new-1"
    assert any("pre-check" in r.getMessage() for r in caplog.records)


async def test_airtable_find_lead_server_error(airtable_setup):
    """Airtable 500 en list (find_lead) → CRMError con status/detail del proveedor."""
    adapter, _fake = airtable_setup
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=re.escape(AIRTABLE_TABLE) + r"(\?.*)?$").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        with pytest.raises(CRMError) as excinfo:
            await adapter.find_lead(email="x@y.test")
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == {"error": "boom"}


async def test_airtable_create_lead_validation_error(airtable_setup):
    """Airtable 422 en el POST de create → CRMError (el pre-check find va vacío)."""
    adapter, _fake = airtable_setup
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=re.escape(AIRTABLE_TABLE) + r"(\?.*)?$").mock(
            return_value=httpx.Response(200, json={"records": []})
        )
        router.post(url__regex=re.escape(AIRTABLE_TABLE) + r"(\?.*)?$").mock(
            return_value=httpx.Response(422, json={"error": "INVALID_VALUE"})
        )
        with pytest.raises(CRMError) as excinfo:
            await adapter.create_lead(_sample_lead())
    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == {"error": "INVALID_VALUE"}


async def test_airtable_update_lead_server_error(airtable_setup):
    """Airtable 500 en el PATCH de update → CRMError."""
    adapter, _fake = airtable_setup
    ref = LeadRef(id="recSERVERERR", provider="airtable")
    with respx.mock(assert_all_called=False) as router:
        router.patch(url__regex=re.escape(AIRTABLE_TABLE) + r"/recSERVERERR$").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        with pytest.raises(CRMError) as excinfo:
            await adapter.update_lead(ref, LeadPatch(estado="Ganado"))
    assert excinfo.value.status_code == 500


async def test_airtable_get_lead_missing_returns_none(airtable_setup):
    """Airtable 404 en get → None (no excepción)."""
    adapter, _fake = airtable_setup
    ref = LeadRef(id="recMISSING", provider="airtable")
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=re.escape(AIRTABLE_TABLE) + r"/recMISSING$").mock(
            return_value=httpx.Response(404, json={"error": "NOT_FOUND"})
        )
        result = await adapter.get_lead(ref)
    assert result is None


async def test_airtable_create_lead_tolerates_precheck_read_failure(airtable_setup, caplog):
    """FIX 3: si la LECTURA del pre-check (list) falla, create NO aborta: loguea
    warning y procede a crear.
    """
    adapter, _fake = airtable_setup
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=re.escape(AIRTABLE_TABLE) + r"(\?.*)?$").mock(
            return_value=httpx.Response(500, json={"error": "read boom"})
        )
        router.post(url__regex=re.escape(AIRTABLE_TABLE) + r"(\?.*)?$").mock(
            return_value=httpx.Response(200, json={"id": "recNEW", "fields": {}})
        )
        with caplog.at_level(logging.WARNING):
            ref = await adapter.create_lead(_sample_lead())
    assert ref.id == "recNEW"
    assert any("pre-check" in r.getMessage() for r in caplog.records)
