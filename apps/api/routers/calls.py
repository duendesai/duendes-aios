"""
Router /calls — power dialer SDR de teams.duendes.net.

Endpoints:
- GET  /calls/queue
- GET  /calls/prospect/{id}
- POST /calls/result
- GET  /calls/calcom/slots
- POST /calls/calcom/book
- POST /calls/zadarma/dial
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from config import get_settings
from deps import get_airtable, get_calcom, get_crm, get_prospecto_twenty, get_zadarma
from services.airtable_multi import (
    BASE_LUCIA,
    TABLE_CALLS,
    AirtableError,
    AirtableMultiClient,
)
from services.calcom_service import CalcomError, CalcomService
from services.crm import CRMClient, CRMError
from services.crm.models import Lead
from services.zadarma_service import ZadarmaError, ZadarmaService
from services.call_analysis import CallAnalysisError, analyze_call
from services.calls_service import (
    NEGATIVE_DISPOSITIONS,
    book_demo_and_create_lead,
    count_campaigns,
    fetch_agenda,
    fetch_prospect_detail,
    fetch_queue,
    submit_call_result,
)
from services import prospecto_twenty as ptw

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])


# ─── Pydantic models (espejo de types.ts) ──────────────────────────────────────

Disposition = Literal[
    "Pendiente",
    "No contesta",
    "Contestador",
    "Comunica",
    "Gatekeeper",
    "Info solicitada",
    "Rellamar",
    "Interes calido",
    "Agendada",
    "No interesa",
    "Numero erroneo",
    "Numero inexistente",
    "No cualifica",
    "Ilocalizable",
    "No llamar",
    "No interesa ahora",
]

ContactoAlcanzado = Literal["Propietario", "Recepción", "Profesional", "Otro", "Ninguno"]
BuyingSignal = Literal["Cortesia", "Curiosidad", "Senal real", "N/A"]
MotivoPerdida = Literal[
    "Precio",
    "Tiempo",
    "Ya tiene solución",
    "Desconfianza IA",
    "No ICP",
    "Otra",
    "Robinson/DNC",
    "RGPD/Origen datos",
    "Amenaza denuncia",
    "DNC explícito",
    "Ilocalizable",
]
MotivoFin = Literal["customer-ended-call", "no-answer", "voicemail", "busy", "failed"]


class CallResultIn(BaseModel):
    prospect_id: str
    disposition: Disposition
    contacto_alcanzado: Optional[ContactoAlcanzado] = None
    buying_signal: BuyingSignal = "N/A"
    motivo_fin: Optional[MotivoFin] = None
    motivo_perdida: Optional[MotivoPerdida] = None
    objeciones: list[str] = Field(default_factory=list)
    discovery_completo: bool = False
    notas: str = ""
    transcripcion: str = ""
    duracion_seg: int = 0
    callback_at: Optional[str] = None  # ISO 8601
    callback_notas: Optional[str] = None
    contacto_nombre: Optional[str] = None


class BookingIn(BaseModel):
    prospect_id: str
    slot_start: str  # ISO 8601
    attendee_name: str
    attendee_email: EmailStr
    attendee_phone: Optional[str] = None
    empresa: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None


class DialIn(BaseModel):
    prospect_id: str
    phone: str  # número en formato internacional (con o sin +)


class AnalyzeIn(BaseModel):
    prospect_id: str
    phone: str
    prospect_name: Optional[str] = ""
    disposition: Optional[str] = ""
    call_record_id: Optional[str] = None  # registro Calls donde persistir el análisis


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/queue")
async def get_queue(
    max_records: int = Query(50, le=200),
    mode: str = Query(
        "warm_opened",
        regex="^(warm_opened|warm_not_opened|cold|warm|all)$",
    ),
    campaign: Optional[str] = Query(None),
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """
    Cola de prospectos pendientes de llamar.

    Modos:
    - `warm_opened` (default): YA abrieron el email (opened/clicked/replied).
      Sort: apertura más antigua primero (la curiosidad se enfría).
    - `warm_not_opened`: email enviado pero sin abrir. Reserva, cuando se
      acaben los abiertos. Sort: envío más antiguo primero.
    - `cold`: sin `Email contacto` (cold call puro, no van por Smartlead).
    - `warm` / `all`: legacy, compat con clientes antiguos.

    `campaign` (slug, opcional): filtra por campaña (p.ej. `despachos-madrid`). Sin él, todas.
    """
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            prospects = await ptw.fetch_queue(
                get_prospecto_twenty(), max_records=max_records, mode=mode, campaign=campaign
            )
        else:
            prospects = await fetch_queue(
                air, max_records=max_records, mode=mode, campaign=campaign
            )
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — camino Twenty (httpx/GraphQL)
        raise HTTPException(status_code=502, detail=f"dialer twenty: {exc}")
    return {
        "prospects": prospects,
        "total": len(prospects),
        "mode": mode,
        "campaign": campaign,
    }


@router.get("/agenda")
async def get_agenda(
    days_ahead: int = Query(14, ge=1, le=60),
    campaign: Optional[str] = Query(None),
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """Callbacks programados (Estado=Rellamar) categorizados por urgencia."""
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            return await ptw.fetch_agenda(
                get_prospecto_twenty(), days_ahead=days_ahead, campaign=campaign
            )
        return await fetch_agenda(air, days_ahead=days_ahead, campaign=campaign)
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — camino Twenty
        raise HTTPException(status_code=502, detail=f"dialer twenty: {exc}")


@router.get("/campaigns")
async def get_campaigns(
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """Campañas disponibles para el selector del dialer, con conteo de prospectos activos."""
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            campaigns = await ptw.count_campaigns(get_prospecto_twenty())
        else:
            campaigns = await count_campaigns(air)
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — camino Twenty
        raise HTTPException(status_code=502, detail=f"dialer twenty: {exc}")
    return {"campaigns": campaigns}


@router.get("/prospect/{prospect_id}")
async def get_prospect(
    prospect_id: str,
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            return await ptw.fetch_prospect_detail(get_prospecto_twenty(), prospect_id)
        return await fetch_prospect_detail(air, prospect_id)
    except AirtableError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Prospect not found")
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — camino Twenty
        raise HTTPException(status_code=502, detail=f"dialer twenty: {exc}")


@router.post("/result")
async def post_result(
    payload: CallResultIn,
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    # Validaciones de coherencia
    if payload.disposition == "Rellamar" and not payload.callback_at:
        raise HTTPException(status_code=422, detail="Rellamar requiere callback_at")
    if payload.disposition in NEGATIVE_DISPOSITIONS and not payload.motivo_perdida:
        raise HTTPException(
            status_code=422,
            detail=f"{payload.disposition} requiere motivo_perdida",
        )
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            result = await ptw.submit_call_result(
                get_prospecto_twenty(), payload.model_dump()
            )
        else:
            result = await submit_call_result(air, payload.model_dump())
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — camino Twenty
        raise HTTPException(status_code=502, detail=f"dialer twenty: {exc}")
    return result


@router.get("/calcom/slots")
async def get_slots(
    days: int = Query(7, ge=1, le=14),
    calcom: CalcomService = Depends(get_calcom),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    try:
        slots = await calcom.list_slots(start=now, end=now + timedelta(days=days))
    except CalcomError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"slots": slots, "total": len(slots)}


@router.post("/calcom/book")
async def post_booking(
    payload: BookingIn,
    air: AirtableMultiClient = Depends(get_airtable),
    calcom: CalcomService = Depends(get_calcom),
    crm: CRMClient = Depends(get_crm),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        if settings.dialer_backend == "twenty":
            return await ptw.book_demo_and_create_lead(
                calcom, crm, get_prospecto_twenty(), payload.model_dump()
            )
        return await book_demo_and_create_lead(air, calcom, crm, payload.model_dump())
    except CalcomError as exc:
        raise HTTPException(status_code=422, detail=f"Cal.com rechazó el booking: {exc}")
    except CRMError as exc:
        # Defensivo: book_demo_and_create_lead surfacea hoy los fallos de CRM en la
        # respuesta (crm_sync_failed=true), NO los propaga, para no reportar como
        # fallido un booking de Cal.com que sí se creó. Este 502 solo se alcanzaría
        # si un cambio futuro dejara escapar un CRMError.
        raise HTTPException(status_code=502, detail=f"CRM: {exc}")
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


class CrmLeadIn(BaseModel):
    """Payload para crear un Lead vía el puerto CRM (dual-write si CRM_BACKEND=dual).

    Pensado para fuentes EXTERNAS que hoy escriben el Lead directo en Airtable
    (p.ej. el workflow n8n de outcomes de llamadas): en vez de escribir a Airtable,
    llaman aquí y el puerto hace el dual-write. Solo `nombre` es obligatorio.
    """

    nombre: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    empresa: Optional[str] = None
    sector: Optional[str] = None
    fuente: Optional[str] = None
    estado: Optional[str] = None
    fecha_reunion: Optional[str] = None
    cal_booking_id: Optional[str] = None
    notas: Optional[str] = None


@router.post("/crm-lead")
async def post_crm_lead(
    payload: CrmLeadIn,
    x_admin_token: str = Header(default=""),
    crm: CRMClient = Depends(get_crm),
) -> dict[str, Any]:
    """Crea un Lead a través del puerto CRM (dual-write según CRM_BACKEND).

    Protegido con X-Admin-Token (el mismo ADMIN_TOKEN que ya usa n8n). Un fallo
    del CRM se surfacea en la respuesta (crm_sync_failed), no como 502 — igual que
    /calcom/book: el que llama puede reintentar/alertar sin perder el dato en silencio.
    """
    admin_token = get_settings().admin_token
    if admin_token and x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="X-Admin-Token inválido o ausente")

    lead = Lead(
        nombre=payload.nombre,
        email=payload.email or "",
        telefono=payload.telefono,
        empresa=payload.empresa,
        sector=payload.sector,
        fuente=payload.fuente,
        estado=payload.estado,
        fecha_reunion=payload.fecha_reunion,
        cal_booking_id=payload.cal_booking_id,
        notas=payload.notas,
    )
    lead_id: str | None = None
    crm_url: str | None = None
    crm_sync_failed = False
    crm_error: str | None = None
    try:
        ref = await crm.create_lead(lead)
        lead_id = ref.id
        crm_url = ref.url
    except Exception as exc:  # noqa: BLE001
        crm_sync_failed = True
        crm_error = str(exc)
        logger.error("POST /crm-lead: crear Lead falló: %s", exc)
    return {
        "lead_id": lead_id,
        "crm_url": crm_url,
        "crm_sync_failed": crm_sync_failed,
        "crm_error": crm_error,
    }


@router.post("/zadarma/dial")
async def post_dial(
    payload: DialIn,
    zadarma: ZadarmaService = Depends(get_zadarma),
) -> dict[str, Any]:
    """
    Inicia click-to-call vía Zadarma. Tu SIP suena primero, descuelgas, Zadarma
    marca al prospect. Devuelve la respuesta directa de Zadarma para debug.
    """
    try:
        result = await zadarma.callback(to_number=payload.phone, predicted=True)
    except ZadarmaError as exc:
        raise HTTPException(status_code=502, detail=f"Zadarma: {exc}")
    return {"ok": True, "zadarma": result}


@router.get("/zadarma/diagnose")
async def get_zadarma_diagnose(
    zadarma: ZadarmaService = Depends(get_zadarma),
) -> dict[str, Any]:
    """
    Diagnóstico end-to-end del estado Zadarma desde el backend.

    Útil para verificar SIN ESPECULAR:
    - Saldo actual
    - Estado online/offline de las extensiones PBX (100, 101)
    - Lista de usuarios WebRTC y dominios autorizados
    - Líneas SIP planas
    - Desvíos configurados a nivel PBX
    """
    return await zadarma.diagnose()


@router.get("/webrtc/key")
async def get_webrtc_key(
    sip: Optional[str] = Query(default=None),
    zadarma: ZadarmaService = Depends(get_zadarma),
) -> dict[str, Any]:
    """
    Devuelve la clave temporal Zadarma que el frontend usa para inicializar el
    widget WebRTC embebido en el dialer.

    Sin `sip`, usa el SIP configurado del backend (ZADARMA_SIP_USERNAME),
    que en producción debería ser la extensión PBX (`561989-100`) para que las
    llamadas se graben y aparezcan en /v1/statistics/pbx/.
    """
    try:
        result = await zadarma.get_webrtc_key(sip)
    except ZadarmaError as exc:
        raise HTTPException(status_code=502, detail=f"Zadarma: {exc}")
    return result


def _format_analysis(a: dict[str, Any]) -> str:
    parts: list[str] = []
    if a.get("resumen"):
        parts.append(f"RESUMEN:\n{a['resumen']}")
    if a.get("puntos_clave"):
        parts.append("PUNTOS CLAVE:\n- " + "\n- ".join(a["puntos_clave"]))
    if a.get("proximos_pasos"):
        parts.append("PRÓXIMOS PASOS:\n- " + "\n- ".join(a["proximos_pasos"]))
    if a.get("necesita_email") and a.get("email_cuerpo"):
        parts.append(
            f"EMAIL SUGERIDO:\nAsunto: {a.get('email_asunto', '')}\n\n{a['email_cuerpo']}"
        )
    return "\n\n".join(parts)


@router.post("/analyze")
async def post_analyze(
    payload: AnalyzeIn,
    air: AirtableMultiClient = Depends(get_airtable),
    zadarma: ZadarmaService = Depends(get_zadarma),
) -> dict[str, Any]:
    """Analiza la última llamada a un número: grabación → transcripción → resumen + email."""
    settings = get_settings()
    try:
        result = await analyze_call(
            zadarma=zadarma,
            groq_api_key=settings.groq_api_key,
            to_number=payload.phone,
            prospect_name=payload.prospect_name or "",
            disposition=payload.disposition or "",
        )
    except CallAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ZadarmaError as exc:
        raise HTTPException(status_code=502, detail=f"Zadarma: {exc}")

    if result.get("ok") and payload.call_record_id:
        try:
            await air.update_record(
                BASE_LUCIA,
                TABLE_CALLS,
                payload.call_record_id,
                {
                    "Transcripcion": result.get("transcript", ""),
                    "Análisis IA": _format_analysis(result.get("analysis", {})),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo guardar el análisis en Calls: %s", exc)

    return result
