"""
Lógica de negocio del power dialer SDR.

Vive en services/ para que routers/calls.py sea fino (parsing + return).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.airtable_multi import (
    AirtableMultiClient,
    BASE_CRM,
    BASE_LUCIA,
    TABLE_CALLS,
    TABLE_LEADS,
    TABLE_MALAGA,
)
from services.calcom_service import CalcomService

logger = logging.getLogger(__name__)


# ─── Mapeos canonical ─────────────────────────────────────────────────────────

# Disposition (Calls) → Estado (malaga). En malaga "Agendada" es "Demo agendada".
DISPOSITION_TO_ESTADO: dict[str, str] = {
    "Agendada": "Demo agendada",
    "Pendiente": "Pendiente",
    "No contesta": "No contesta",
    "Contestador": "Contestador",
    "Comunica": "Comunica",
    "Gatekeeper": "Gatekeeper",
    "Info solicitada": "Info solicitada",
    "Rellamar": "Rellamar",
    "Interes calido": "Interés cálido",
    "No interesa": "No interesa",
    "Numero erroneo": "Número erróneo",
    "Numero inexistente": "Número inexistente",
    "No cualifica": "No cualifica",
    "Ilocalizable": "Ilocalizable",
    "No llamar": "No llamar",
    "No interesa ahora": "No interesa ahora",
}

DISPOSITION_TO_OUTCOME: dict[str, str] = {
    "Agendada": "demo_agendada",
    "No interesa": "no_interesa",
    "No interesa ahora": "no_interesa",
    "No cualifica": "no_interesa",
    "No llamar": "no_llamar",
    "Numero erroneo": "no_llamar",
    "Numero inexistente": "no_llamar",
    "Rellamar": "callback",
    "Info solicitada": "callback",
    "Interes calido": "callback",
    "No contesta": "no_contesta",
    "Contestador": "no_contesta",
    "Comunica": "no_contesta",
    "Gatekeeper": "no_contesta",
    "Ilocalizable": "no_contesta",
    "Pendiente": "no_contesta",
}

NEGATIVE_DISPOSITIONS = {
    "No interesa",
    "No interesa ahora",
    "No cualifica",
    "No llamar",
    "Numero erroneo",
    "Numero inexistente",
    "Ilocalizable",
}

# Estados finales que deben EXCLUIRSE de la cola (ya cerrados o muertos)
EXCLUDED_FROM_QUEUE = [
    "Demo agendada",
    "No interesa",
    "No llamar",
    "Numero erroneo",
    "Numero inexistente",
    "No cualifica",
    "Ilocalizable",
    "No interesa ahora",
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datos_enriquecidos(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        return None


def _to_prospect_dto(record: dict[str, Any]) -> dict[str, Any]:
    """Mapea record Airtable → dict para frontend usando los nombres reales."""
    f = record.get("fields", {})
    return {
        "id": record["id"],
        "title": f.get("title") or "(sin nombre)",
        "phone": f.get("phone"),
        "city": f.get("city"),
        "category_name": f.get("categoryName"),
        "website": f.get("website"),
        "estado": f.get("Estado"),
        "lane": f.get("Lane"),
        "intentos": int(f.get("Intentos") or 0),
        "notas": f.get("Notas"),
        "ultimo_intento": f.get("Último intento"),
        "proximo_intento": f.get("Próximo intento"),
        "contacto_nombre": f.get("Contacto nombre"),
        "contacto_alcanzado": f.get("Contacto alcanzado"),
        "motivo_perdida": f.get("Motivo pérdida"),
        "callback_solicitado": f.get("Callback solicitado"),
        "callback_notas": f.get("Callback notas"),
        "prioridad": f.get("Prioridad"),
        "score": f.get("Score"),
        "tamano": f.get("Tamaño"),
        "booking_online": bool(f.get("Booking online")),
        "datos_enriquecidos": _parse_datos_enriquecidos(f.get("Datos enriquecidos")),
        "crm_url": f.get("CRM Duendes URL"),
    }


def _to_call_history_item(record: dict[str, Any]) -> dict[str, Any]:
    f = record.get("fields", {})
    return {
        "id": record["id"],
        "fecha": f.get("Fecha y hora"),
        "disposition": f.get("Disposition"),
        "buying_signal": f.get("Buying signal"),
        "notas": f.get("Notas"),
        "duracion_seg": f.get("Duracion (seg)"),
    }


# ─── Casos de uso ──────────────────────────────────────────────────────────────


async def fetch_queue(air: AirtableMultiClient, max_records: int = 50) -> list[dict[str, Any]]:
    """
    Lista prospectos elegibles para llamar.
    Filtros aplicados:
    - `phone` no vacío
    - `No llamar` = false
    - `Estado` no en lista de finales
    """
    excluded = ", ".join(f'{{Estado}}="{e}"' for e in EXCLUDED_FROM_QUEUE)
    filter_formula = (
        f"AND("
        f"  {{phone}}!='',"
        f"  NOT({{No llamar}}),"
        f"  NOT(OR({excluded}))"
        f")"
    )
    sort = [
        {"field": "Prioridad", "direction": "asc"},
        {"field": "Intentos", "direction": "asc"},
    ]
    records = await air.list_records(
        BASE_LUCIA,
        TABLE_MALAGA,
        filter_formula=filter_formula,
        sort=sort,
        max_records=max_records,
    )

    # Post-filtro: si Estado=Rellamar y Próximo intento > ahora, excluir
    now = datetime.now(timezone.utc)
    eligible: list[dict[str, Any]] = []
    for r in records:
        f = r.get("fields", {})
        estado = f.get("Estado")
        proximo = f.get("Próximo intento")
        if estado == "Rellamar" and proximo:
            try:
                proximo_dt = datetime.fromisoformat(str(proximo).replace("Z", "+00:00"))
                if proximo_dt > now:
                    continue
            except (ValueError, TypeError):
                pass
        eligible.append(r)

    return [_to_prospect_dto(r) for r in eligible]


async def fetch_agenda(
    air: AirtableMultiClient, days_ahead: int = 14
) -> dict[str, Any]:
    """
    Devuelve todos los prospectos con callback programado (Estado=Rellamar y
    Próximo intento NO vacío), categorizados temporalmente.

    Buckets:
    - overdue: callback vencido (<= ahora)
    - today: hoy (próximas horas del día actual)
    - week: dentro de los próximos 7 días
    - later: 8 a `days_ahead` días
    """
    from datetime import date

    filter_formula = (
        "AND("
        "  {Estado}='Rellamar',"
        "  {Próximo intento}!=''"
        ")"
    )
    sort = [{"field": "Próximo intento", "direction": "asc"}]
    records = await air.list_records(
        BASE_LUCIA,
        TABLE_MALAGA,
        filter_formula=filter_formula,
        sort=sort,
        max_records=200,
    )

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(
        date.today(), datetime.min.time(), tzinfo=timezone.utc
    )
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)
    horizon = today_start + timedelta(days=days_ahead)

    overdue: list[dict[str, Any]] = []
    today: list[dict[str, Any]] = []
    week: list[dict[str, Any]] = []
    later: list[dict[str, Any]] = []

    for r in records:
        proximo_raw = r.get("fields", {}).get("Próximo intento")
        if not proximo_raw:
            continue
        try:
            proximo_dt = datetime.fromisoformat(
                str(proximo_raw).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        dto = _to_prospect_dto(r)
        dto["callback_at"] = proximo_dt.isoformat()

        if proximo_dt <= now:
            overdue.append(dto)
        elif proximo_dt < today_end:
            today.append(dto)
        elif proximo_dt < week_end:
            week.append(dto)
        elif proximo_dt < horizon:
            later.append(dto)

    return {
        "overdue": overdue,
        "today": today,
        "week": week,
        "later": later,
        "totals": {
            "overdue": len(overdue),
            "today": len(today),
            "week": len(week),
            "later": len(later),
            "all": len(overdue) + len(today) + len(week) + len(later),
        },
    }


async def fetch_prospect_detail(
    air: AirtableMultiClient, prospect_id: str
) -> dict[str, Any]:
    """Detalle de un prospecto + últimas 3 llamadas vinculadas."""
    record = await air.get_record(BASE_LUCIA, TABLE_MALAGA, prospect_id)
    dto = _to_prospect_dto(record)

    # Historial
    try:
        calls_filter = f"FIND('{prospect_id}', ARRAYJOIN({{Prospect}})) > 0"
        history = await air.list_records(
            BASE_LUCIA,
            TABLE_CALLS,
            filter_formula=calls_filter,
            sort=[{"field": "Fecha y hora", "direction": "desc"}],
            max_records=3,
        )
        dto["call_history"] = [_to_call_history_item(r) for r in history]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo al cargar call_history para %s: %s", prospect_id, exc)
        dto["call_history"] = []

    return dto


async def submit_call_result(
    air: AirtableMultiClient, payload: dict[str, Any]
) -> dict[str, Any]:
    """
    Operación dual:
    1. POST en Calls con el log de la llamada
    2. PATCH en malaga con el nuevo estado, intentos+1, notas append, etc.

    Si el POST en Calls falla, no se hace el PATCH (transaccional best-effort).
    Si el PATCH falla, se devuelve `partial: true`.
    """
    prospect_id = payload["prospect_id"]
    disposition = payload["disposition"]

    # 1. Leer prospecto para calcular Intentos+1 y hacer append a Notas
    prev = await air.get_record(BASE_LUCIA, TABLE_MALAGA, prospect_id)
    prev_fields = prev.get("fields", {})
    prev_intentos = int(prev_fields.get("Intentos") or 0)
    prev_notas = prev_fields.get("Notas") or ""

    # 2. Crear log en Calls
    call_id = f"M-{uuid.uuid4().hex[:8]}"
    call_fields: dict[str, Any] = {
        "Call ID": call_id,
        "Prospect": [prospect_id],
        "Fecha y hora": _now_iso(),
        "Disposition": disposition,
        "Buying signal": payload.get("buying_signal") or "N/A",
        "Discovery completo": bool(payload.get("discovery_completo")),
        "Duracion (seg)": payload.get("duracion_seg") or 0,
        "Notas": payload.get("notas") or "",
        "Transcripcion": payload.get("transcripcion") or "",
        "outcome": DISPOSITION_TO_OUTCOME.get(disposition),
    }
    if payload.get("objeciones"):
        call_fields["Objeciones"] = payload["objeciones"]
    if payload.get("motivo_fin"):
        call_fields["Motivo fin"] = payload["motivo_fin"]

    call_record = await air.create_record(BASE_LUCIA, TABLE_CALLS, call_fields)

    # 3. Actualizar malaga
    estado = DISPOSITION_TO_ESTADO.get(disposition, "Pendiente")
    outcome = DISPOSITION_TO_OUTCOME.get(disposition)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nota_nueva = payload.get("notas") or ""
    if nota_nueva:
        notas_combinadas = (
            f"{prev_notas}\n---\n[{today} · {disposition}] {nota_nueva}".strip()
        )
    else:
        notas_combinadas = prev_notas

    update_fields: dict[str, Any] = {
        "Estado": estado,
        "Intentos": prev_intentos + 1,
        "Último intento": _now_iso(),
        "outcome": outcome,
        "Notas": notas_combinadas,
        "Contacto alcanzado": payload.get("contacto_alcanzado"),
    }
    if payload.get("contacto_nombre"):
        update_fields["Contacto nombre"] = payload["contacto_nombre"]
    if disposition in NEGATIVE_DISPOSITIONS and payload.get("motivo_perdida"):
        update_fields["Motivo pérdida"] = payload["motivo_perdida"]
    if disposition == "No llamar":
        update_fields["No llamar"] = True
    if disposition == "Rellamar":
        callback_at = payload.get("callback_at")
        if callback_at:
            update_fields["Próximo intento"] = callback_at
            update_fields["Callback solicitado"] = callback_at
        if payload.get("callback_notas"):
            update_fields["Callback notas"] = payload["callback_notas"]

    partial = False
    try:
        await air.update_record(BASE_LUCIA, TABLE_MALAGA, prospect_id, update_fields)
    except Exception as exc:  # noqa: BLE001
        logger.error("PATCH malaga falló tras POST Calls OK (%s): %s", prospect_id, exc)
        partial = True

    return {
        "ok": True,
        "call_id": call_id,
        "call_record_id": call_record["id"],
        "partial": partial,
    }


async def book_demo_and_create_lead(
    air: AirtableMultiClient,
    calcom: CalcomService,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Operación en cadena:
    1. POST Cal.com /bookings
    2. POST appFIn3ntFb39vGXF/Leads (CRM)
    3. PATCH malaga con Agendada fecha + CRM Duendes URL
    """
    prospect_id = payload["prospect_id"]
    slot_start_str = payload["slot_start"]
    slot_start = datetime.fromisoformat(slot_start_str.replace("Z", "+00:00"))

    # 1. Cal.com booking
    notes_parts = []
    if payload.get("notes"):
        notes_parts.append(payload["notes"])
    notes_parts.append(f"Prospect Airtable ID: {prospect_id}")
    booking = await calcom.create_booking(
        slot_start=slot_start,
        attendee_name=payload["attendee_name"],
        attendee_email=payload["attendee_email"],
        attendee_phone=payload.get("attendee_phone"),
        notes="\n".join(notes_parts),
        metadata={"prospect_id": prospect_id, "source": "teams.duendes.net"},
    )

    # 2. Crear Lead en CRM
    lead_id: str | None = None
    crm_url: str | None = None
    try:
        lead_fields = {
            "Nombre": payload["attendee_name"],
            "Email": payload["attendee_email"],
            "Empresa": payload.get("empresa"),
            "Teléfono": payload.get("attendee_phone"),
            "Sector": payload.get("sector"),
            "Fuente": "SDR Manual",
            "Estado": "Demo agendada",
            "Fecha reunión": booking["start"],
            "Cal Booking ID": booking["booking_uid"] or booking["booking_id"],
            "Notas": payload.get("notes") or f"Booking creado desde teams.duendes.net para prospect {prospect_id}",
        }
        lead = await air.create_record(BASE_CRM, TABLE_LEADS, lead_fields)
        lead_id = lead["id"]
        crm_url = f"https://airtable.com/{BASE_CRM}/{TABLE_LEADS}/{lead_id}"
    except Exception as exc:  # noqa: BLE001
        logger.error("Crear Lead CRM falló tras booking Cal.com OK: %s", exc)

    # 3. Actualizar malaga con la fecha y enlace al CRM
    try:
        update_fields: dict[str, Any] = {
            "Agendada fecha": booking["start"],
            "Estado": "Demo agendada",
            "outcome": "demo_agendada",
        }
        if crm_url:
            update_fields["CRM Duendes URL"] = crm_url
        await air.update_record(BASE_LUCIA, TABLE_MALAGA, prospect_id, update_fields)
    except Exception as exc:  # noqa: BLE001
        logger.error("PATCH malaga tras booking falló (%s): %s", prospect_id, exc)

    return {
        "booking_uid": booking["booking_uid"],
        "booking_id": booking["booking_id"],
        "meeting_url": booking["meeting_url"],
        "start": booking["start"],
        "end": booking["end"],
        "lead_id": lead_id,
        "crm_url": crm_url,
    }
