"""
AirtableMultiClient — wrapper async sobre Airtable REST API parametrizado por base.

Centraliza el acceso a las dos bases que usa el power dialer:
- BASE_LUCIA (LUCIA Bienestar): `malaga` (prospectos) + `Calls` (log de llamadas)
- BASE_CRM (Duendes CRM): `Leads` (cuando se agenda demo)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.airtable.com/v0"

# IDs de bases (verificados 2026-05-18)
BASE_LUCIA = "app5WbiXR0qXGTc3r"  # LUCIA Bienestar
BASE_CRM = "appFIn3ntFb39vGXF"  # Duendes CRM

# Tablas
TABLE_MALAGA = "malaga"
TABLE_CALLS = "Calls"
TABLE_EMAILS = "Emails"
TABLE_LEADS = "Leads"

# Alias semántico: la tabla física `malaga` es ahora la tabla ÚNICA de prospectos
# multi-campaña, filtrada por el campo {Campaña}. Mantiene el nombre "malaga" en
# Airtable para no romper los enlaces (Emails.Prospect, Calls.Prospect) existentes.
TABLE_PROSPECTOS = TABLE_MALAGA

# Campañas del power dialer. `label` = valor EXACTO del campo {Campaña} en la
# tabla de prospectos. `smartlead_id` = ID de campaña en Smartlead para el sync.
# `import_source` (opcional): de dónde se importan los prospectos a medida que
# reciben email. Sin él, la campaña no se auto-importa (sus prospectos ya viven
# en la tabla del dialer, p.ej. fisios).
CAMPAIGNS: dict[str, dict[str, Any]] = {
    "fisios-malaga": {
        "label": "Fisios Málaga",
        "smartlead_id": 3368353,
    },
    "despachos-madrid": {
        "label": "Despachos Madrid",
        "smartlead_id": 3404016,
        "import_source": {
            # Base "duendes OUTREACH" (cold-outreach CrewAI) → tabla Leads.
            "base_id": "apptD14jq6NCq5qIM",
            "table": "Leads",
            # Record de la campaña en la tabla Campaigns (para filtrar los leads).
            "campaign_record": "rechQQIXSdUML1AsQ",
        },
    },
}
DEFAULT_CAMPAIGN = "fisios-malaga"


def campaign_label(slug: str | None) -> str | None:
    """Resuelve el slug de campaña (p.ej. 'despachos-madrid') a su label Airtable."""
    if not slug:
        return None
    cfg = CAMPAIGNS.get(slug)
    return cfg["label"] if cfg else None


class AirtableError(Exception):
    """Error al hablar con Airtable. status_code y body para debug."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AirtableMultiClient:
    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise AirtableError("AIRTABLE_API_KEY vacío — añádelo al .env de la raíz")
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, base_id: str, table: str) -> str:
        return f"{_BASE_URL}/{base_id}/{table}"

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                method, url, headers=self._headers(), params=params, json=json
            )
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                logger.error("Airtable %s %s → %s: %s", method, url, resp.status_code, body)
                raise AirtableError(
                    f"Airtable {resp.status_code}: {body}",
                    status_code=resp.status_code,
                    body=body,
                )
            return resp.json()

    async def list_records(
        self,
        base_id: str,
        table: str,
        *,
        filter_formula: Optional[str] = None,
        sort: Optional[list[dict[str, str]]] = None,
        fields: Optional[list[str]] = None,
        max_records: int | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Lista registros paginando automáticamente."""
        params: dict[str, Any] = {"pageSize": min(page_size, 100)}
        if max_records:
            params["maxRecords"] = max_records
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if sort:
            for i, s in enumerate(sort):
                params[f"sort[{i}][field]"] = s["field"]
                params[f"sort[{i}][direction]"] = s.get("direction", "asc")
        if fields:
            for i, f in enumerate(fields):
                params[f"fields[{i}]"] = f

        url = self._url(base_id, table)
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            page_params = dict(params)
            if offset:
                page_params["offset"] = offset
            data = await self._request("GET", url, params=page_params)
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset or (max_records and len(records) >= max_records):
                break
        if max_records:
            records = records[:max_records]
        return records

    async def get_record(self, base_id: str, table: str, record_id: str) -> dict[str, Any]:
        url = f"{self._url(base_id, table)}/{record_id}"
        return await self._request("GET", url)

    async def create_record(
        self,
        base_id: str,
        table: str,
        fields: dict[str, Any],
        *,
        typecast: bool = False,
    ) -> dict[str, Any]:
        url = self._url(base_id, table)
        body: dict[str, Any] = {"fields": _clean_fields(fields)}
        if typecast:
            body["typecast"] = True
        return await self._request("POST", url, json=body)

    async def update_record(
        self,
        base_id: str,
        table: str,
        record_id: str,
        fields: dict[str, Any],
        *,
        typecast: bool = False,
    ) -> dict[str, Any]:
        url = f"{self._url(base_id, table)}/{record_id}"
        body: dict[str, Any] = {"fields": _clean_fields(fields)}
        if typecast:
            body["typecast"] = True
        return await self._request("PATCH", url, json=body)


def _clean_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Quita claves con valor None para no sobreescribir campos en Airtable."""
    return {k: v for k, v in fields.items() if v is not None}
