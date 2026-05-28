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
    CAMPAIGNS,
    TABLE_CALLS,
    TABLE_EMAILS,
    TABLE_LEADS,
    TABLE_MALAGA,
    campaign_label,
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
        "campaign": f.get("Campaña"),
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


def _to_email_dto(record: dict[str, Any]) -> dict[str, Any]:
    f = record.get("fields", {})
    return {
        "id": record["id"],
        "email_id": f.get("Email ID"),
        "fecha_envio": f.get("Fecha envío"),
        "destino": f.get("Email destino"),
        "asunto": f.get("Asunto"),
        "cuerpo": f.get("Cuerpo"),
        "status": f.get("Status") or "sent",
        "fecha_apertura": f.get("Fecha apertura"),
        "fecha_respuesta": f.get("Fecha respuesta"),
        "respuesta": f.get("Respuesta"),
        "campaign": f.get("Campaign"),
    }


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except (ValueError, TypeError):
        return None


async def _fetch_emails_for_prospects(
    air: AirtableMultiClient, prospect_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """
    Carga todos los emails linkados a estos prospects. Devuelve dict {prospect_id: [emails...]}
    ordenados por Fecha envío descendente (más reciente primero).

    Nota: Airtable `ARRAYJOIN({Prospect})` devuelve los nombres (primary field),
    NO los record IDs. Por eso no podemos filtrar server-side por prospect_id.
    Cargamos todos los emails y filtramos en Python (la tabla es pequeña).
    """
    if not prospect_ids:
        return {}

    wanted = set(prospect_ids)
    out: dict[str, list[dict[str, Any]]] = {pid: [] for pid in prospect_ids}

    try:
        records = await air.list_records(
            BASE_LUCIA,
            TABLE_EMAILS,
            sort=[{"field": "Fecha envío", "direction": "desc"}],
            max_records=1000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo cargando emails: %s", exc)
        return out

    for r in records:
        linked = r.get("fields", {}).get("Prospect") or []
        # El campo Prospect es array de record IDs (strings tipo "rec...")
        for pid in linked:
            if pid in wanted:
                out[pid].append(_to_email_dto(r))
    return out


# ─── Casos de uso ──────────────────────────────────────────────────────────────


async def fetch_queue(
    air: AirtableMultiClient,
    max_records: int = 200,
    mode: str = "all",
    campaign: str | None = None,
) -> list[dict[str, Any]]:
    """
    Lista prospectos elegibles para llamar.

    Filtros base (siempre):
    - `phone` no vacío
    - `No llamar` = false
    - `Estado` no en lista de finales
    - Si `Estado=Rellamar` y `Próximo intento > now`, excluir

    Modo `mode` filtra ADEMÁS:
    - `warm`: solo los que tienen ≥1 email enviado. Sort por D+2..D+5 primero.
    - `cold`: solo los que NO tienen `Email contacto` (= no en ninguna campaña Smartlead). Sort por Score desc.
    - `all`: warm + cold (excluye los "reservados": con Email contacto pero sin envío todavía). Sort: warm primero.

    El motivo de excluir "reservados" en `all`: si Smartlead va a mandarles el email
    en los próximos días, llamarles AHORA los quemaría — el email llegará después.
    """
    excluded = ", ".join(f'{{Estado}}="{e}"' for e in EXCLUDED_FROM_QUEUE)
    clauses = ["{phone}!=''", "NOT({No llamar})", f"NOT(OR({excluded}))"]
    label = campaign_label(campaign)
    if label:
        clauses.append(f'{{Campaña}}="{label}"')
    filter_formula = "AND(" + ", ".join(clauses) + ")"
    # No limitamos por max_records aquí — filtramos en Python primero por modo
    # y devolvemos solo el top max_records al final.
    records = await air.list_records(
        BASE_LUCIA,
        TABLE_MALAGA,
        filter_formula=filter_formula,
        sort=[
            {"field": "Prioridad", "direction": "asc"},
            {"field": "Intentos", "direction": "asc"},
        ],
        max_records=500,
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

    # Cargar emails linkados
    prospect_ids = [r["id"] for r in eligible]
    emails_by_prospect = await _fetch_emails_for_prospects(air, prospect_ids)

    # Construir DTOs con last_email
    dtos: list[dict[str, Any]] = []
    for r in eligible:
        dto = _to_prospect_dto(r)
        emails = emails_by_prospect.get(r["id"], [])
        f = r.get("fields", {})
        has_email_contacto = bool(f.get("Email contacto"))

        if emails:
            last = emails[0]
            days = _days_since(last.get("fecha_envio"))
            dto["last_email"] = {
                "asunto": last.get("asunto"),
                "fecha_envio": last.get("fecha_envio"),
                "status": last.get("status"),
                "days_ago": days,
            }
            dto["email_count"] = len(emails)
        else:
            dto["last_email"] = None
            dto["email_count"] = 0

        dto["has_email_contacto"] = has_email_contacto
        dtos.append(dto)

    # Filtro por modo
    mode = (mode or "all").lower()
    if mode == "warm":
        filtered = [p for p in dtos if p["email_count"] > 0]
    elif mode == "cold":
        filtered = [p for p in dtos if not p["has_email_contacto"]]
    else:  # 'all'
        # Excluir "reservados": con email contacto pero sin email enviado todavía
        filtered = [
            p for p in dtos
            if p["email_count"] > 0 or not p["has_email_contacto"]
        ]

    # Sort distinto por modo
    if mode == "cold":
        # Score desc (los más cualificados primero), después Intentos asc
        filtered.sort(
            key=lambda p: (
                -(p.get("score") or 0),
                p.get("intentos", 0),
            )
        )
    elif mode == "warm":
        # Sweet spot D+2..D+5 primero
        filtered.sort(key=_warm_sort_key)
    else:  # 'all'
        # Sweet spot primero, después por score
        filtered.sort(key=_warm_sort_key)

    return filtered[:max_records]


def _warm_sort_key(p: dict[str, Any]) -> tuple:
    """Sort: D+2..D+5 primero, después D+6..D+14, después muy reciente, después sin email."""
    le = p.get("last_email")
    if le and le.get("days_ago") is not None:
        d = le["days_ago"]
        if 2 <= d <= 5:
            return (0, d, -(p.get("score") or 0))
        if 6 <= d <= 14:
            return (1, d, -(p.get("score") or 0))
        if d < 2:
            return (3, d, -(p.get("score") or 0))
        return (2, d, -(p.get("score") or 0))
    return (4, p.get("intentos", 0), -(p.get("score") or 0))


async def count_campaigns(air: AirtableMultiClient) -> list[dict[str, Any]]:
    """Campañas disponibles + nº de prospectos activos (con phone, no excluidos).

    Alimenta el selector de campañas del frontend.
    """
    excluded = ", ".join(f'{{Estado}}="{e}"' for e in EXCLUDED_FROM_QUEUE)
    out: list[dict[str, Any]] = []
    for slug, cfg in CAMPAIGNS.items():
        label = cfg["label"]
        filt = (
            f'AND({{Campaña}}="{label}", {{phone}}!=\'\', '
            f"NOT({{No llamar}}), NOT(OR({excluded})))"
        )
        try:
            recs = await air.list_records(
                BASE_LUCIA,
                TABLE_MALAGA,
                filter_formula=filt,
                fields=["title"],
                max_records=1000,
            )
            count = len(recs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Conteo campaña %s falló: %s", slug, exc)
            count = 0
        out.append({"id": slug, "label": label, "count": count})
    return out


async def fetch_agenda(
    air: AirtableMultiClient, days_ahead: int = 14, campaign: str | None = None
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

    clauses = ["{Estado}='Rellamar'", "{Próximo intento}!=''"]
    label = campaign_label(campaign)
    if label:
        clauses.append(f'{{Campaña}}="{label}"')
    filter_formula = "AND(" + ", ".join(clauses) + ")"
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
    """Detalle de un prospecto + últimas 3 llamadas + emails enviados."""
    record = await air.get_record(BASE_LUCIA, TABLE_MALAGA, prospect_id)
    dto = _to_prospect_dto(record)

    # Historial de llamadas
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

    # Historial de emails (toda la secuencia)
    try:
        emails_by = await _fetch_emails_for_prospects(air, [prospect_id])
        emails = emails_by.get(prospect_id, [])
        dto["emails"] = emails  # ordenados desc (más reciente primero)
        if emails:
            last = emails[0]
            dto["last_email"] = {
                "asunto": last.get("asunto"),
                "fecha_envio": last.get("fecha_envio"),
                "status": last.get("status"),
                "days_ago": _days_since(last.get("fecha_envio")),
            }
        else:
            dto["last_email"] = None
        dto["email_count"] = len(emails)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo al cargar emails para %s: %s", prospect_id, exc)
        dto["emails"] = []
        dto["last_email"] = None
        dto["email_count"] = 0

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
