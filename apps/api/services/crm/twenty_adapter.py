"""
`TwentyCRMAdapter` — adaptador del puerto `CRMClient` contra una instancia
Twenty self-hosted. **Person-only** (design §2): el lead se modela como el objeto
estándar `Person` + campos custom; el piloto NO crea `Company` ni `Opportunity`.

- create/update/get → REST (`/rest/people`, `/rest/people/{id}`): CRUD 1:1 simple.
- find_lead        → GraphQL (`/graphql`): filtro server-side por `emails` o por
  el custom field `calBookingId` en una sola request.

Responsabilidades EXCLUSIVAS de este adaptador (no del Airtable):
- Normalizar valores heredados rotos del workflow Meta (`Sector="Clínicas"`,
  `Estado="Nuevo"`) a opciones válidas del SELECT ANTES de escribir (design §3).
- Normalizar `fechaReunion` a UTC ISO-8601 canónico antes de escribir (design §3).
- Pre-check de idempotencia (D1) dentro de `create_lead` vía `find_lead`.
- Traducir errores HTTP/GraphQL de Twenty a `CRMError` (o subclase).

Auth por API key (`TWENTY_API_KEY`) inyectada desde config; sin credenciales
hardcodeadas. Falla explícito al construirse si falta la key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from services.crm.errors import (
    CRMAuthError,
    CRMError,
    CRMNotFoundError,
    CRMValidationError,
)
from services.crm.models import Lead, LeadPatch, LeadRef

logger = logging.getLogger(__name__)

# ── Normalización de valores heredados (SOLO Twenty) ───────────────────────────
# El workflow Meta hoy escribe Sector="Clínicas" y Estado="Nuevo", valores que NO
# existen en el SELECT de Twenty (dependían de typecast en Airtable). Se traducen
# a la opción válida equivalente antes de escribir (design §3, spec crm-twenty).
_SECTOR_NORMALIZATION: dict[str, str] = {
    "Clínicas": "Salud",
    "Clinicas": "Salud",
}
# Estado inicial válido del SELECT `estadoDemo` para un lead recién entrado.
_ESTADO_INITIAL = "Reunión agendada"
_ESTADO_NORMALIZATION: dict[str, str] = {
    "Nuevo": _ESTADO_INITIAL,
}


def _normalize_sector(value: str | None) -> str | None:
    if value is None:
        return None
    return _SECTOR_NORMALIZATION.get(value, value)


def _normalize_estado(value: str | None) -> str | None:
    if value is None:
        return None
    return _ESTADO_NORMALIZATION.get(value, value)


def _normalize_fecha_utc(value: str | None) -> str | None:
    """Normaliza una fecha ISO-8601 a UTC ISO-8601 canónico.

    Compara por instante, no por string (design §3, política de TZ). Si el valor
    no trae zona horaria, se asume UTC. Si no parsea, se devuelve tal cual (mejor
    escribir algo que perder el dato — el parity check por instante lo detectará).
    """
    if not value:
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _split_name(nombre: str | None) -> dict[str, str]:
    """`"Ana Pérez López"` → `{firstName: "Ana", lastName: "Pérez López"}`.

    Split simple por el primer espacio (design §3).
    """
    if not nombre:
        return {"firstName": "", "lastName": ""}
    parts = nombre.strip().split(" ", 1)
    if len(parts) == 1:
        return {"firstName": parts[0], "lastName": ""}
    return {"firstName": parts[0], "lastName": parts[1]}


class TwentyCRMAdapter:
    """Adaptador Twenty del puerto `CRMClient` (Person-only, REST + GraphQL)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
    ) -> None:
        if not api_key:
            raise CRMError(
                "TWENTY_API_KEY vacío — añádelo al .env (config.twenty_api_key)"
            )
        if not base_url:
            raise CRMError(
                "TWENTY_BASE_URL vacío — añádelo al .env (config.twenty_base_url)"
            )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _rest_url(self, path: str) -> str:
        return f"{self._base_url}/rest{path}"

    def _graphql_url(self) -> str:
        return f"{self._base_url}/graphql"

    def _crm_url(self, person_id: str) -> str:
        return f"{self._base_url}/object/person/{person_id}"

    # ── Error translation ─────────────────────────────────────────────────────

    @staticmethod
    def _raise_for_status(resp: httpx.Response, op: str) -> None:
        if resp.status_code < 400:
            return
        try:
            body: Any = resp.json()
        except Exception:  # noqa: BLE001
            body = resp.text
        logger.error("Twenty %s → %s: %s", op, resp.status_code, body)
        message = f"Twenty {op} {resp.status_code}: {body}"
        if resp.status_code in (401, 403):
            raise CRMAuthError(message, status_code=resp.status_code, detail=body)
        if resp.status_code in (400, 422):
            raise CRMValidationError(message, status_code=resp.status_code, detail=body)
        if resp.status_code == 404:
            raise CRMNotFoundError(message, status_code=resp.status_code, detail=body)
        raise CRMError(message, status_code=resp.status_code, detail=body)

    async def _rest_request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method, self._rest_url(path), headers=self._headers(), json=json
                )
        except httpx.HTTPError as exc:
            raise CRMError(f"Twenty {method} {path} fallo de red: {exc}") from exc
        self._raise_for_status(resp, f"{method} {path}")
        return resp.json()

    async def _graphql_request(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._graphql_url(),
                    headers=self._headers(),
                    json={"query": query, "variables": variables},
                )
        except httpx.HTTPError as exc:
            raise CRMError(f"Twenty GraphQL fallo de red: {exc}") from exc
        self._raise_for_status(resp, "GraphQL")
        payload = resp.json()
        if payload.get("errors"):
            raise CRMError(
                f"Twenty GraphQL errors: {payload['errors']}",
                status_code=resp.status_code,
                detail=payload["errors"],
            )
        return payload.get("data", {})

    # ── Traducción dominio → payload Twenty Person ────────────────────────────

    def _lead_to_person_payload(self, lead: Lead) -> dict[str, Any]:
        """`Lead` → payload REST de Person, aplicando normalizaciones y omitiendo
        los campos `None`. Person-only, con custom fields del pipeline de demos.
        """
        payload: dict[str, Any] = {}
        if lead.nombre is not None:
            payload["name"] = _split_name(lead.nombre)
        if lead.email is not None:
            payload["emails"] = {"primaryEmail": lead.email}
        if lead.telefono is not None:
            payload["phones"] = {"primaryPhoneNumber": lead.telefono}
        if lead.empresa is not None:
            payload["companyName"] = lead.empresa
        sector = _normalize_sector(lead.sector)
        if sector is not None:
            payload["sector"] = sector
        if lead.fuente is not None:
            payload["fuente"] = lead.fuente
        estado = _normalize_estado(lead.estado)
        if estado is not None:
            payload["estadoDemo"] = estado
        fecha = _normalize_fecha_utc(lead.fecha_reunion)
        if fecha is not None:
            payload["fechaReunion"] = fecha
        if lead.cal_booking_id is not None:
            payload["calBookingId"] = lead.cal_booking_id
        if lead.notas is not None:
            payload["notas"] = lead.notas
        return payload

    def _patch_to_person_payload(self, changes: LeadPatch) -> dict[str, Any]:
        """`LeadPatch` → payload REST con SOLO los campos no-`None` (patch parcial).

        Aplica las mismas normalizaciones que la creación a los campos presentes.
        """
        changed = changes.changed_fields()
        payload: dict[str, Any] = {}
        if "nombre" in changed:
            payload["name"] = _split_name(changed["nombre"])
        if "email" in changed:
            payload["emails"] = {"primaryEmail": changed["email"]}
        if "telefono" in changed:
            payload["phones"] = {"primaryPhoneNumber": changed["telefono"]}
        if "empresa" in changed:
            payload["companyName"] = changed["empresa"]
        if "sector" in changed:
            payload["sector"] = _normalize_sector(changed["sector"])
        if "fuente" in changed:
            payload["fuente"] = changed["fuente"]
        if "estado" in changed:
            payload["estadoDemo"] = _normalize_estado(changed["estado"])
        if "fecha_reunion" in changed:
            payload["fechaReunion"] = _normalize_fecha_utc(changed["fecha_reunion"])
        if "cal_booking_id" in changed:
            payload["calBookingId"] = changed["cal_booking_id"]
        if "notas" in changed:
            payload["notas"] = changed["notas"]
        return payload

    def _person_to_lead(self, person: dict[str, Any]) -> Lead:
        name = person.get("name") or {}
        first = name.get("firstName") or ""
        last = name.get("lastName") or ""
        nombre = f"{first} {last}".strip()
        emails = person.get("emails") or {}
        phones = person.get("phones") or {}
        return Lead(
            nombre=nombre,
            email=emails.get("primaryEmail") or "",
            telefono=phones.get("primaryPhoneNumber"),
            empresa=person.get("companyName"),
            sector=person.get("sector"),
            fuente=person.get("fuente"),
            estado=person.get("estadoDemo"),
            fecha_reunion=person.get("fechaReunion"),
            cal_booking_id=person.get("calBookingId"),
            notas=person.get("notas"),
        )

    def _person_to_ref(self, person: dict[str, Any]) -> LeadRef:
        pid = person.get("id")
        if not pid:
            raise CRMError(
                "Twenty devolvió una respuesta sin id de Person",
                detail=person,
            )
        return LeadRef(
            id=pid,
            provider="twenty",
            url=self._crm_url(pid),
        )

    @staticmethod
    def _unwrap_person(data: dict[str, Any]) -> dict[str, Any]:
        """La REST API de Twenty envuelve la entidad en `{"data": {"person": {...}}}`
        o `{"data": {"createPerson": {...}}}`. Devuelve el objeto Person crudo.
        """
        inner = data.get("data", data)
        if isinstance(inner, dict):
            for key in ("person", "createPerson", "updatePerson"):
                if key in inner:
                    return inner[key]
        return inner

    # ── Puerto CRMClient ──────────────────────────────────────────────────────

    async def create_lead(self, lead: Lead) -> LeadRef:
        # Pre-check de idempotencia (D1): email y/o cal_booking_id. El pre-check es
        # best-effort: si la LECTURA falla (transitorio), no abortamos la creación
        # — "no se pudo verificar" se trata como "no existe" y se procede a crear.
        # La creación es la operación crítica; el dedup es best-effort. El error del
        # POST de creación (más abajo) SÍ propaga.
        try:
            existing = await self.find_lead(
                email=lead.email or None,
                cal_booking_id=lead.cal_booking_id or None,
            )
        except CRMError as exc:
            logger.warning(
                "Twenty create_lead pre-check find_lead falló (email=%s, "
                "cal_booking_id=%s): %s — se procede a crear sin dedup",
                lead.email,
                lead.cal_booking_id,
                exc,
            )
        else:
            if existing is not None:
                return existing

        payload = self._lead_to_person_payload(lead)
        data = await self._rest_request("POST", "/people", json=payload)
        person = self._unwrap_person(data)
        return self._person_to_ref(person)

    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef:
        payload = self._patch_to_person_payload(changes)
        if not payload:
            return ref
        data = await self._rest_request("PATCH", f"/people/{ref.id}", json=payload)
        person = self._unwrap_person(data)
        return self._person_to_ref(person)

    async def get_lead(self, ref: LeadRef) -> Lead | None:
        try:
            data = await self._rest_request("GET", f"/people/{ref.id}")
        except CRMNotFoundError:
            return None
        person = self._unwrap_person(data)
        if not person:
            return None
        return self._person_to_lead(person)

    async def find_lead(
        self,
        *,
        email: str | None = None,
        cal_booking_id: str | None = None,
    ) -> LeadRef | None:
        # Email es la clave primaria: se busca primero. Si no matchea, se cae al
        # guardia por calBookingId (design §1/§2, D1).
        if email:
            ref = await self._find_by_filter({"emails": {"primaryEmail": {"eq": email}}})
            if ref is not None:
                return ref
        if cal_booking_id:
            ref = await self._find_by_filter({"calBookingId": {"eq": cal_booking_id}})
            if ref is not None:
                return ref
        return None

    async def _find_by_filter(self, where: dict[str, Any]) -> LeadRef | None:
        query = """
        query FindPeople($filter: PersonFilterInput, $first: Int) {
          people(filter: $filter, first: $first) {
            edges { node { id } }
          }
        }
        """
        data = await self._graphql_request(query, {"filter": where, "first": 1})
        edges = ((data.get("people") or {}).get("edges")) or []
        if not edges:
            return None
        node = edges[0].get("node") or {}
        if not node.get("id"):
            return None
        return self._person_to_ref(node)
