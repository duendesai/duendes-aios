"""
Camino Twenty del power dialer (objeto custom `prospecto` en Twenty CRM).

ADITIVO: NO reemplaza el camino Airtable de `calls_service.py`. El router elige
uno u otro según `settings.dialer_backend` ("airtable" | "twenty"). Así el cutover
es flip de flag y el rollback es quitarlo (cero regresión en el camino vivo).

Diferencias respecto al camino Airtable, por diseño:
- La tabla `Emails` de Airtable se borró (incidente 2026-07-08), así que NO hay
  gating warm/cold/reservados por email: TODOS los elegibles son llamables. El orden
  es callbacks vencidos → nuevos (prioridad/score) → reintentos (menos intentos primero).
- No hay objeto `Calls` todavía: el resultado de la llamada actualiza el propio
  `prospecto` (estado/intentos/outcome/notas). El log granular por llamada se
  modelará como objeto `llamada` en una iteración posterior.

DTOs con la MISMA forma que `calls_service._to_prospect_dto` para que el frontend
(`apps/teams`) no cambie.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from services.crm.models import Lead, option_value

logger = logging.getLogger(__name__)

# ── Sets limpios (espejo de infra/twenty/create_prospecto_object.py) ────────────
ESTADO = ["Pendiente", "No contesta", "Contestador", "Comunica", "Gatekeeper",
          "Info solicitada", "Rellamar", "Interés cálido", "Demo agendada",
          "No interesa", "No interesa ahora", "No cualifica", "Ilocalizable",
          "Número erróneo", "Número inexistente", "No llamar"]
PRIORIDAD = ["Alta", "Media", "Baja", "Sin calificar"]
CAMPANA = ["Fisios Málaga", "Despachos Madrid", "Colegios Fisioterapia", "Webinar Colegios"]
OUTCOME = ["demo_agendada", "no_interesa", "callback", "no_llamar", "no_contesta"]

# value (UPPER_SNAKE) → label, para pintar en el frontend como el camino Airtable
_ESTADO_V2L = {option_value(x): x for x in ESTADO}
_PRIORIDAD_V2L = {option_value(x): x for x in PRIORIDAD}
_CAMPANA_V2L = {option_value(x): x for x in CAMPANA}

# Estados finales EXCLUIDOS de la cola (mismos que calls_service.EXCLUDED_FROM_QUEUE)
EXCLUDED_FROM_QUEUE = {
    "Demo agendada", "No interesa", "No llamar", "Número erróneo",
    "Número inexistente", "No cualifica", "Ilocalizable", "No interesa ahora",
    "Info solicitada",
}

# Mapeos disposition → estado/outcome (idénticos a calls_service)
DISPOSITION_TO_ESTADO: dict[str, str] = {
    "Agendada": "Demo agendada", "Pendiente": "Pendiente", "No contesta": "No contesta",
    "Contestador": "Contestador", "Comunica": "Comunica", "Gatekeeper": "Gatekeeper",
    "Info solicitada": "Info solicitada", "Rellamar": "Rellamar",
    "Interes calido": "Interés cálido", "No interesa": "No interesa",
    "Numero erroneo": "Número erróneo", "Numero inexistente": "Número inexistente",
    "No cualifica": "No cualifica", "Ilocalizable": "Ilocalizable",
    "No llamar": "No llamar", "No interesa ahora": "No interesa ahora",
}
DISPOSITION_TO_OUTCOME: dict[str, str] = {
    "Agendada": "demo_agendada", "No interesa": "no_interesa",
    "No interesa ahora": "no_interesa", "No cualifica": "no_interesa",
    "No llamar": "no_llamar", "Numero erroneo": "no_llamar",
    "Numero inexistente": "no_llamar", "Rellamar": "callback",
    "Info solicitada": "callback", "Interes calido": "callback",
    "No contesta": "no_contesta", "Contestador": "no_contesta",
    "Comunica": "no_contesta", "Gatekeeper": "no_contesta",
    "Ilocalizable": "no_contesta", "Pendiente": "no_contesta",
}
NEGATIVE_DISPOSITIONS = {
    "No interesa", "No interesa ahora", "No cualifica", "No llamar",
    "Numero erroneo", "Numero inexistente", "Ilocalizable",
}

# Campos del objeto prospecto a traer del GraphQL (para el DTO)
_NODE_FIELDS = (
    "id name phone estado prioridad campana outcome intentos ultimoIntento "
    "proximoIntento noLlamar categoria city website contactoNombre "
    "contactoAlcanzado motivoPerdida callbackSolicitado callbackNotas score "
    "tamano bookingOnline datosEnriquecidos crmUrl email notas"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datos(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        p = json.loads(raw)
        return p if isinstance(p, dict) else None
    except (ValueError, TypeError):
        return None


class TwentyProspectoClient:
    """CRUD mínimo del objeto `prospecto` en Twenty (REST + GraphQL)."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 20.0) -> None:
        if not base_url or not api_key:
            raise RuntimeError("TWENTY_BASE_URL / TWENTY_API_KEY vacíos")
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/graphql", headers=self._headers(),
                             json={"query": query, "variables": variables})
        r.raise_for_status()
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"Twenty GraphQL: {payload['errors']}")
        return payload.get("data", {})

    async def list_all(self) -> list[dict[str, Any]]:
        """Todos los prospectos como nodos crudos (paginado)."""
        out: list[dict[str, Any]] = []
        after: str | None = None
        q = ("query($after:String){ prospectos(first:60, after:$after){ edges{ node{ "
             + _NODE_FIELDS + " } } pageInfo{ hasNextPage endCursor } } }")
        while True:
            data = (await self._graphql(q, {"after": after})).get("prospectos")
            if not data:
                return out
            out += [e["node"] for e in data["edges"]]
            if not data["pageInfo"]["hasNextPage"]:
                return out
            after = data["pageInfo"]["endCursor"]

    async def get(self, prospecto_id: str) -> dict[str, Any] | None:
        q = ("query($id:UUID!){ prospecto(filter:{id:{eq:$id}}){ " + _NODE_FIELDS + " } }")
        data = await self._graphql(q, {"id": prospecto_id})
        return data.get("prospecto")

    async def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/rest/prospectos",
                             headers=self._headers(), json=fields)
        r.raise_for_status()
        return r.json()

    async def update(self, prospecto_id: str, fields: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.patch(f"{self._base}/rest/prospectos/{prospecto_id}",
                              headers=self._headers(), json=fields)
        r.raise_for_status()


# ── Nodo Twenty → DTO frontend (mismas claves que _to_prospect_dto) ────────────
def _to_dto(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node["id"],
        "title": node.get("name") or "(sin nombre)",
        "phone": node.get("phone"),
        "city": node.get("city"),
        "category_name": node.get("categoria"),
        "website": node.get("website"),
        "estado": _ESTADO_V2L.get(node.get("estado"), node.get("estado")),
        "lane": None,
        "intentos": int(node.get("intentos") or 0),
        "notas": node.get("notas"),
        "ultimo_intento": node.get("ultimoIntento"),
        "proximo_intento": node.get("proximoIntento"),
        "contacto_nombre": node.get("contactoNombre"),
        "contacto_alcanzado": node.get("contactoAlcanzado"),
        "motivo_perdida": node.get("motivoPerdida"),
        "callback_solicitado": node.get("callbackSolicitado"),
        "callback_notas": node.get("callbackNotas"),
        "prioridad": _PRIORIDAD_V2L.get(node.get("prioridad"), node.get("prioridad")),
        "score": node.get("score"),
        "tamano": node.get("tamano"),
        "booking_online": bool(node.get("bookingOnline")),
        "datos_enriquecidos": _parse_datos(node.get("datosEnriquecidos")),
        "crm_url": node.get("crmUrl"),
        "campaign": _CAMPANA_V2L.get(node.get("campana"), node.get("campana")),
        # sin tabla Emails: no hay señales de email
        "last_email": None,
        "email_count": 0,
        "has_email_contacto": bool(node.get("email")),
    }


def _is_callback_due(dto: dict[str, Any], now: datetime) -> bool:
    if dto.get("estado") != "Rellamar" or not dto.get("proximo_intento"):
        return False
    try:
        return datetime.fromisoformat(str(dto["proximo_intento"]).replace("Z", "+00:00")) <= now
    except (ValueError, TypeError):
        return False


# ── Casos de uso (misma firma/retorno que calls_service) ───────────────────────
async def fetch_queue(
    client: TwentyProspectoClient,
    max_records: int = 200,
    mode: str = "all",
    campaign: str | None = None,
) -> list[dict[str, Any]]:
    """Cola de llamadas desde Twenty. Sin gating por email (Emails no existe)."""
    nodes = await client.list_all()
    now = datetime.now(timezone.utc)
    dtos: list[dict[str, Any]] = []
    for n in nodes:
        dto = _to_dto(n)
        if not dto["phone"]:
            continue
        if bool(n.get("noLlamar")):
            continue
        if dto["estado"] in EXCLUDED_FROM_QUEUE:
            continue
        if campaign and _CAMPANA_V2L.get(option_value(campaign)) and \
                dto["campaign"] != _CAMPANA_V2L.get(option_value(campaign)):
            continue
        # Rellamar con próximo intento futuro → aún no toca
        if dto["estado"] == "Rellamar" and dto["proximo_intento"] and not _is_callback_due(dto, now):
            continue
        dtos.append(dto)

    callbacks_due = sorted([p for p in dtos if _is_callback_due(p, now)],
                           key=lambda p: str(p.get("proximo_intento") or ""))
    cb_ids = {p["id"] for p in callbacks_due}
    rest = [p for p in dtos if p["id"] not in cb_ids]
    nuevos = sorted([p for p in rest if int(p.get("intentos") or 0) == 0],
                    key=lambda p: (-(p.get("score") or 0), int(p.get("intentos") or 0)))
    reintentos = sorted([p for p in rest if int(p.get("intentos") or 0) >= 1],
                        key=lambda p: (int(p.get("intentos") or 0), str(p.get("ultimo_intento") or "")))
    return (callbacks_due + nuevos + reintentos)[:max_records]


async def count_campaigns(client: TwentyProspectoClient) -> list[dict[str, Any]]:
    """Campañas + nº de prospectos activos (con phone, no excluidos, no No llamar)."""
    nodes = await client.list_all()
    counts: dict[str, int] = {}
    for n in nodes:
        dto = _to_dto(n)
        if not dto["phone"] or bool(n.get("noLlamar")) or dto["estado"] in EXCLUDED_FROM_QUEUE:
            continue
        camp = dto["campaign"]
        if camp:
            counts[camp] = counts.get(camp, 0) + 1
    # slug = option_value del label, para casar con el selector del frontend
    return [{"id": option_value(label).lower(), "label": label, "count": counts[label]}
            for label in sorted(counts)]


async def fetch_agenda(
    client: TwentyProspectoClient, days_ahead: int = 14, campaign: str | None = None
) -> dict[str, Any]:
    """Callbacks programados (estado Rellamar + próximo intento), por buckets."""
    nodes = await client.list_all()
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)
    horizon = today_start + timedelta(days=days_ahead)
    buckets: dict[str, list[dict[str, Any]]] = {"overdue": [], "today": [], "week": [], "later": []}
    camp_label = _CAMPANA_V2L.get(option_value(campaign)) if campaign else None
    for n in nodes:
        dto = _to_dto(n)
        if dto["estado"] != "Rellamar" or not dto["proximo_intento"]:
            continue
        if camp_label and dto["campaign"] != camp_label:
            continue
        try:
            pdt = datetime.fromisoformat(str(dto["proximo_intento"]).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        dto["callback_at"] = pdt.isoformat()
        if pdt <= now:
            buckets["overdue"].append(dto)
        elif pdt < today_end:
            buckets["today"].append(dto)
        elif pdt < week_end:
            buckets["week"].append(dto)
        elif pdt < horizon:
            buckets["later"].append(dto)
    totals = {k: len(v) for k, v in buckets.items()}
    totals["all"] = sum(totals.values())
    return {**buckets, "totals": totals}


async def fetch_prospect_detail(
    client: TwentyProspectoClient, prospect_id: str
) -> dict[str, Any]:
    """Ficha del prospecto. Sin call_history/emails (tablas borradas)."""
    node = await client.get(prospect_id)
    if not node:
        raise RuntimeError(f"Prospecto {prospect_id} no encontrado en Twenty")
    dto = _to_dto(node)
    dto["call_history"] = []
    dto["emails"] = []
    return dto


async def submit_call_result(
    client: TwentyProspectoClient, payload: dict[str, Any]
) -> dict[str, Any]:
    """Actualiza el prospecto con el resultado de la llamada (sin log Calls aún)."""
    prospect_id = payload["prospect_id"]
    disposition = payload["disposition"]

    node = await client.get(prospect_id)
    if not node:
        raise RuntimeError(f"Prospecto {prospect_id} no encontrado en Twenty")
    prev_intentos = int(node.get("intentos") or 0)
    prev_notas = node.get("notas") or ""

    estado_label = DISPOSITION_TO_ESTADO.get(disposition, "Pendiente")
    outcome_label = DISPOSITION_TO_OUTCOME.get(disposition)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nota_nueva = payload.get("notas") or ""
    notas = (f"{prev_notas}\n---\n[{today} · {disposition}] {nota_nueva}".strip()
             if nota_nueva else prev_notas)

    fields: dict[str, Any] = {
        "estado": option_value(estado_label),
        "intentos": prev_intentos + 1,
        "ultimoIntento": _now_iso(),
        "notas": notas,
    }
    if outcome_label:
        fields["outcome"] = option_value(outcome_label)
    if payload.get("contacto_alcanzado"):
        fields["contactoAlcanzado"] = payload["contacto_alcanzado"]
    if payload.get("contacto_nombre"):
        fields["contactoNombre"] = payload["contacto_nombre"]
    if disposition in NEGATIVE_DISPOSITIONS and payload.get("motivo_perdida"):
        fields["motivoPerdida"] = payload["motivo_perdida"]
    if disposition == "No llamar":
        fields["noLlamar"] = True
    if disposition == "Rellamar":
        callback_at = payload.get("callback_at")
        if callback_at:
            fields["proximoIntento"] = callback_at
            fields["callbackSolicitado"] = callback_at
        if payload.get("callback_notas"):
            fields["callbackNotas"] = payload["callback_notas"]

    partial = False
    try:
        await client.update(prospect_id, fields)
    except Exception as exc:  # noqa: BLE001
        logger.error("PATCH prospecto Twenty falló (%s): %s", prospect_id, exc)
        partial = True

    return {"ok": True, "call_id": f"M-{uuid.uuid4().hex[:8]}",
            "call_record_id": None, "partial": partial}


async def patch_booking(
    client: TwentyProspectoClient, prospect_id: str, *,
    agendada_fecha: str, crm_url: str | None,
) -> None:
    """Marca el prospecto como Demo agendada tras un booking (para book_demo)."""
    fields: dict[str, Any] = {
        "agendadaFecha": agendada_fecha,
        "estado": option_value("Demo agendada"),
        "outcome": option_value("demo_agendada"),
    }
    if crm_url:
        fields["crmUrl"] = crm_url
    await client.update(prospect_id, fields)


async def book_demo_and_create_lead(
    calcom: Any, crm: Any, client: TwentyProspectoClient, payload: dict[str, Any]
) -> dict[str, Any]:
    """Igual que calls_service.book_demo_and_create_lead pero parchea el prospecto en
    Twenty (paso 3). Pasos 1 (Cal.com) y 2 (Lead vía puerto CRM) son idénticos."""
    prospect_id = payload["prospect_id"]
    slot_start = datetime.fromisoformat(payload["slot_start"].replace("Z", "+00:00"))

    notes_parts = []
    if payload.get("notes"):
        notes_parts.append(payload["notes"])
    notes_parts.append(f"Prospect Twenty ID: {prospect_id}")
    booking = await calcom.create_booking(
        slot_start=slot_start,
        attendee_name=payload["attendee_name"],
        attendee_email=payload["attendee_email"],
        attendee_phone=payload.get("attendee_phone"),
        notes="\n".join(notes_parts),
        metadata={"prospect_id": prospect_id, "source": "teams.duendes.net"},
    )

    lead_id: str | None = None
    crm_url: str | None = None
    crm_sync_failed = False
    crm_error: str | None = None
    try:
        lead = Lead(
            nombre=payload["attendee_name"],
            email=payload["attendee_email"],
            telefono=payload.get("attendee_phone"),
            empresa=payload.get("empresa"),
            sector=payload.get("sector"),
            fuente="Outreach",
            estado="Reunión agendada",
            fecha_reunion=booking["start"],
            cal_booking_id=booking["booking_uid"] or booking["booking_id"],
            notas=payload.get("notes")
            or f"Booking desde teams.duendes.net para prospect {prospect_id}",
        )
        ref = await crm.create_lead(lead)
        lead_id = ref.id
        crm_url = ref.url
    except Exception as exc:  # noqa: BLE001
        crm_sync_failed = True
        crm_error = str(exc)
        logger.error("Crear Lead CRM falló tras booking (Twenty path): %s", exc)

    try:
        await patch_booking(client, prospect_id, agendada_fecha=booking["start"], crm_url=crm_url)
    except Exception as exc:  # noqa: BLE001
        logger.error("PATCH prospecto Twenty tras booking falló (%s): %s", prospect_id, exc)

    return {
        "booking_uid": booking["booking_uid"],
        "booking_id": booking["booking_id"],
        "meeting_url": booking["meeting_url"],
        "start": booking["start"],
        "end": booking["end"],
        "lead_id": lead_id,
        "crm_url": crm_url,
        "crm_sync_failed": crm_sync_failed,
        "crm_error": crm_error,
    }
