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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from deps import get_airtable, get_calcom, get_zadarma
from services.airtable_multi import AirtableError, AirtableMultiClient
from services.calcom_service import CalcomError, CalcomService
from services.zadarma_service import ZadarmaError, ZadarmaService
from services.calls_service import (
    NEGATIVE_DISPOSITIONS,
    book_demo_and_create_lead,
    fetch_agenda,
    fetch_prospect_detail,
    fetch_queue,
    submit_call_result,
)

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


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/queue")
async def get_queue(
    max_records: int = Query(50, le=200),
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """Cola de prospectos pendientes de llamar."""
    try:
        prospects = await fetch_queue(air, max_records=max_records)
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"prospects": prospects, "total": len(prospects)}


@router.get("/agenda")
async def get_agenda(
    days_ahead: int = Query(14, ge=1, le=60),
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """Callbacks programados (Estado=Rellamar) categorizados por urgencia."""
    try:
        return await fetch_agenda(air, days_ahead=days_ahead)
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/prospect/{prospect_id}")
async def get_prospect(
    prospect_id: str,
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    try:
        return await fetch_prospect_detail(air, prospect_id)
    except AirtableError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Prospect not found")
        raise HTTPException(status_code=502, detail=str(exc))


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
    try:
        result = await submit_call_result(air, payload.model_dump())
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
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
) -> dict[str, Any]:
    try:
        return await book_demo_and_create_lead(air, calcom, payload.model_dump())
    except CalcomError as exc:
        raise HTTPException(status_code=422, detail=f"Cal.com rechazó el booking: {exc}")
    except AirtableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


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
