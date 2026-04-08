"""
Duendes AIOS — AE Deal Management Module
Reads/writes deals directly to Airtable (Deals table, tblWzOHSU16QusG9s).

Airtable fields:
  Empresa, Sector, Ciudad, Contacto
  Estado           (Single select: Nuevo, Demo, Propuesta, Negociacion, Ganado, Perdido)
  Valor mensual    (Currency)
  Setup            (Currency)
  Siguiente paso   (Single line text)
  Objeciones       (Long text — newline-separated entries)
  Propuesta        (Long text)
  Notas            (Long text)
  Razón perdido    (Single line text)
  Source           (Single line text)
  Fecha creación, Fecha actualización, Fecha cierre  (Date, YYYY-MM-DD)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from airtable_client import AirtableClient, AirtableError, TABLE_DEALS, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
logger = logging.getLogger("duendes-bot.ae_deals")

# Re-export for bot.py compatibility
EngramConnectionError = AirtableError
EngramDataError = AirtableError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ESTADOS: set[str] = {"nuevo", "demo", "propuesta", "negociacion", "ganado", "perdido"}

ESTADO_ORDER: dict[str, int] = {
    "nuevo": 0, "demo": 1, "propuesta": 2, "negociacion": 3, "ganado": 4, "perdido": 5,
}

_AT_ESTADO_MAP: dict[str, str] = {
    "nuevo": "nuevo", "demo": "demo", "propuesta": "propuesta",
    "negociacion": "negociacion", "ganado": "ganado", "perdido": "perdido",
}

_ESTADO_TO_AT: dict[str, str] = {
    "nuevo": "Nuevo", "demo": "Demo", "propuesta": "Propuesta",
    "negociacion": "Negociacion", "ganado": "Ganado", "perdido": "Perdido",
}


def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).strip()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estado_sort_key(estado: str) -> int:
    return ESTADO_ORDER.get(estado, 99)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Deal:
    id: str                 # Airtable record ID
    empresa: str
    sector: str
    ciudad: str
    contacto: str
    estado: str             # nuevo | demo | propuesta | negociacion | ganado | perdido
    valor_mensual: float
    setup: float
    propuesta: str
    objeciones: list[str]   # stored as newline-separated text in Airtable
    siguiente_paso: str
    created_at: str         # YYYY-MM-DD
    updated_at: str         # YYYY-MM-DD
    closed_at: str          # YYYY-MM-DD or ""
    razon_perdido: str
    notas: str
    source: str

    @classmethod
    def from_airtable(cls, record: dict) -> "Deal":
        f = record.get("fields", {})
        raw_estado = _f(f, "Estado").lower()
        raw_valor = _f(f, "Valor mensual")
        raw_setup = _f(f, "Setup")
        try:
            valor_mensual = float(str(raw_valor).replace("€", "").replace(",", ".").strip() or 0)
        except ValueError:
            valor_mensual = 0.0
        try:
            setup = float(str(raw_setup).replace("€", "").replace(",", ".").strip() or 0)
        except ValueError:
            setup = 0.0
        raw_objeciones = _f(f, "Objeciones")
        objeciones = [o for o in raw_objeciones.split("\n") if o.strip()] if raw_objeciones else []
        return cls(
            id=record["id"],
            empresa=_f(f, "Empresa"),
            sector=_f(f, "Sector"),
            ciudad=_f(f, "Ciudad"),
            contacto=_f(f, "Contacto"),
            estado=_AT_ESTADO_MAP.get(raw_estado, "nuevo"),
            valor_mensual=valor_mensual,
            setup=setup,
            propuesta=_f(f, "Propuesta"),
            objeciones=objeciones,
            siguiente_paso=_f(f, "Siguiente paso"),
            created_at=_f(f, "Fecha creación") or record.get("createdTime", "")[:10],
            updated_at=_f(f, "Fecha actualización") or _today_iso(),
            closed_at=_f(f, "Fecha cierre"),
            razon_perdido=_f(f, "Razón perdido"),
            notas=_f(f, "Notas"),
            source=_f(f, "Source") or "manual",
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if self.empresa:
            fields["Empresa"] = self.empresa
        if self.sector:
            fields["Sector"] = self.sector
        if self.ciudad:
            fields["Ciudad"] = self.ciudad
        if self.contacto:
            fields["Contacto"] = self.contacto
        if self.estado:
            fields["Estado"] = _ESTADO_TO_AT.get(self.estado, "Nuevo")
        if self.valor_mensual:
            fields["Valor mensual"] = self.valor_mensual
        if self.setup:
            fields["Setup"] = self.setup
        if self.propuesta:
            fields["Propuesta"] = self.propuesta
        if self.objeciones:
            fields["Objeciones"] = "\n".join(self.objeciones)
        if self.siguiente_paso:
            fields["Siguiente paso"] = self.siguiente_paso
        if self.created_at:
            fields["Fecha creación"] = self.created_at[:10]
        if self.updated_at:
            fields["Fecha actualización"] = self.updated_at[:10]
        if self.closed_at:
            fields["Fecha cierre"] = self.closed_at[:10]
        if self.razon_perdido:
            fields["Razón perdido"] = self.razon_perdido
        if self.notas:
            fields["Notas"] = self.notas
        if self.source:
            fields["Source"] = self.source
        return fields


# ---------------------------------------------------------------------------
# CRUD — async (bot.py)
# ---------------------------------------------------------------------------

async def add_deal(
    empresa: str,
    sector: str,
    ciudad: str = "",
    contacto: str = "",
    valor_mensual: float = 0.0,
    setup: float = 0.0,
    siguiente_paso: str = "",
    source: str = "manual",
) -> Deal:
    at = get_client()
    deal = Deal(
        id="",
        empresa=empresa.strip(),
        sector=sector.strip().lower(),
        ciudad=ciudad.strip(),
        contacto=contacto.strip(),
        estado="nuevo",
        valor_mensual=float(valor_mensual or 0.0),
        setup=float(setup or 0.0),
        propuesta="",
        objeciones=[],
        siguiente_paso=siguiente_paso.strip(),
        created_at=_today_iso(),
        updated_at=_today_iso(),
        closed_at="",
        razon_perdido="",
        notas="",
        source=source,
    )
    record = await at.create_record(TABLE_DEALS, deal.to_airtable_fields())
    return Deal.from_airtable(record)


async def list_deals(estado: str | None = None) -> list[Deal]:
    at = get_client()
    formula = None
    if estado:
        at_estado = _ESTADO_TO_AT.get(estado, estado.capitalize())
        formula = f"{{Estado}}='{at_estado}'"
    records = await at.list_records(TABLE_DEALS, filter_formula=formula)
    deals = [Deal.from_airtable(r) for r in records if r.get("fields", {}).get("Empresa")]
    return sorted(deals, key=lambda d: (_estado_sort_key(d.estado), d.updated_at))


async def get_deal(record_id: str) -> Deal | None:
    at = get_client()
    try:
        records = await at.list_records(
            TABLE_DEALS, filter_formula=f"RECORD_ID()='{record_id}'"
        )
        return Deal.from_airtable(records[0]) if records else None
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def update_deal_estado(
    record_id: str,
    nuevo_estado: str,
    razon_perdido: str = "",
) -> Deal | None:
    if nuevo_estado not in VALID_ESTADOS:
        raise ValueError(f"Invalid estado: {nuevo_estado!r}. Valid: {sorted(VALID_ESTADOS)}")
    at = get_client()
    fields: dict[str, Any] = {
        "Estado": _ESTADO_TO_AT[nuevo_estado],
        "Fecha actualización": _today_iso(),
    }
    if nuevo_estado in {"ganado", "perdido"}:
        fields["Fecha cierre"] = _today_iso()
    if nuevo_estado == "perdido" and razon_perdido.strip():
        fields["Razón perdido"] = razon_perdido.strip()
    try:
        record = await at.update_record(TABLE_DEALS, record_id, fields)
        deal = Deal.from_airtable(record)
        # Cross-dept automations
        try:
            import asyncio
            from cross_dept import on_deal_lost, on_deal_won
            if nuevo_estado == "ganado":
                asyncio.create_task(on_deal_won(deal.empresa, deal.sector, deal.notas or ""))
            elif nuevo_estado == "perdido":
                asyncio.create_task(on_deal_lost(deal.empresa, deal.sector))
        except Exception:
            pass
        return deal
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def save_propuesta(record_id: str, propuesta_texto: str, siguiente_paso: str = "") -> Deal | None:
    at = get_client()
    fields: dict[str, Any] = {
        "Propuesta": propuesta_texto.strip(),
        "Estado": "Propuesta",
        "Fecha actualización": _today_iso(),
        "Siguiente paso": (siguiente_paso or "Enviar propuesta y agendar revisión en 48h").strip(),
    }
    try:
        record = await at.update_record(TABLE_DEALS, record_id, fields)
        return Deal.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def update_deal_nota(record_id: str, nota_text: str) -> Deal | None:
    at = get_client()
    # Get current notas first
    records = await at.list_records(TABLE_DEALS, filter_formula=f"RECORD_ID()='{record_id}'")
    if not records:
        return None
    existing = records[0].get("fields", {}).get("Notas", "") or ""
    text = nota_text.strip()
    new_notas = (existing + "\n" + text).strip() if existing else text
    record = await at.update_record(
        TABLE_DEALS, record_id,
        {"Notas": new_notas, "Fecha actualización": _today_iso()}
    )
    return Deal.from_airtable(record)


async def add_objecion(record_id: str, objecion: str) -> Deal | None:
    at = get_client()
    records = await at.list_records(TABLE_DEALS, filter_formula=f"RECORD_ID()='{record_id}'")
    if not records:
        return None
    existing = records[0].get("fields", {}).get("Objeciones", "") or ""
    entry = f"[{_today_iso()}] {objecion.strip()}"
    new_objeciones = (existing + "\n" + entry).strip() if existing else entry
    record = await at.update_record(
        TABLE_DEALS, record_id,
        {"Objeciones": new_objeciones, "Fecha actualización": _today_iso()}
    )
    return Deal.from_airtable(record)


# ---------------------------------------------------------------------------
# Proposal generation
# ---------------------------------------------------------------------------

async def generate_propuesta(
    deal: Deal,
    context_os: str,
    anthropic_client: Any,
    module_system: str = "",
) -> str:
    system = module_system or (
        "Eres el AE (Account Executive) de Duendes. "
        "Redactas propuestas comerciales claras, directas y en español de España. "
        "No vendes tecnología: vendes resultado de negocio."
    )
    user_prompt = f"""Redacta una propuesta comercial para este prospecto.

DEAL:
- Empresa: {deal.empresa}
- Sector: {deal.sector or 'general'}
- Ciudad: {deal.ciudad or 'N/A'}
- Contacto: {deal.contacto or 'N/A'}
- Estado actual: {deal.estado}
- Objeciones registradas: {deal.objeciones if deal.objeciones else 'ninguna'}

CONTEXTO DE DUENDES:
{context_os[:2800] if context_os else '(sin contexto)'}

ESTRUCTURA OBLIGATORIA:
1) Problema del cliente (en sus palabras)
2) Lo que hace Duendes (concreto)
3) Cómo funciona (implementación simple)
4) Qué incluye
5) Inversión (setup + mensual, rango según ofertas)
6) Próximos pasos (una sola acción clara)

REGLAS:
- Máximo 350 palabras
- Directo, sin florituras
- En español de España
- No usar jerga técnica innecesaria
- Cierre con una CTA clara para agendar la demo/revisión"""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Brief sync helper
# ---------------------------------------------------------------------------

def get_hot_deals_for_brief_sync() -> str:
    at = get_client()
    try:
        records = at.list_records_sync(TABLE_DEALS)
        deals = [Deal.from_airtable(r) for r in records if r.get("fields", {}).get("Empresa")]
    except Exception as exc:
        logger.error("brief ae sync error: %s", exc)
        return "No hay oportunidades AE calientes."

    hot = [d for d in deals if d.estado in {"demo", "propuesta", "negociacion"}]
    if not hot:
        return "No hay oportunidades AE calientes."

    hot = sorted(hot, key=lambda d: (_estado_sort_key(d.estado), d.updated_at))
    lines = ["Pipeline AE (oportunidades calientes):"]
    for deal in hot:
        next_step = f" | siguiente: {deal.siguiente_paso}" if deal.siguiente_paso else ""
        lines.append(f"- {deal.empresa} [{deal.sector}] — {deal.estado}{next_step}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_ESTADO_EMOJI: dict[str, str] = {
    "nuevo": "🆕", "demo": "🎥", "propuesta": "📄",
    "negociacion": "🤝", "ganado": "✅", "perdido": "❌",
}


def format_deal_list(deals: list[Deal], title: str = "Deals") -> str:
    if not deals:
        return "No hay oportunidades registradas."
    estado_order = ["nuevo", "demo", "propuesta", "negociacion", "ganado", "perdido"]
    groups: dict[str, list[Deal]] = {e: [] for e in estado_order}
    for d in deals:
        groups.setdefault(d.estado, []).append(d)
    lines = [f"*{title}*\n"]
    for estado in estado_order:
        group = groups.get(estado, [])
        if not group:
            continue
        emoji = _ESTADO_EMOJI.get(estado, "")
        lines.append(f"{emoji} *{estado.capitalize()}*")
        for d in group:
            city = f", {d.ciudad}" if d.ciudad else ""
            dn = f"#{d._display_id} " if hasattr(d, "_display_id") else ""
            lines.append(f"  {dn}{d.empresa} [{d.sector}{city}]")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_deal_added(deal: Deal) -> str:
    city = f", {deal.ciudad}" if deal.ciudad else ""
    return f"Deal creado: {deal.empresa} [{deal.sector}{city}] — estado: nuevo"


def format_deal_estado_updated(deal: Deal) -> str:
    emoji = _ESTADO_EMOJI.get(deal.estado, "")
    return f"Deal actualizado: {deal.empresa} → {emoji} {deal.estado}"


def format_deal_detail(deal: Deal) -> str:
    emoji = _ESTADO_EMOJI.get(deal.estado, "")
    lines = [
        f"*Deal — {deal.empresa}*",
        f"Estado: {emoji} {deal.estado}",
        f"Sector: {deal.sector} | Ciudad: {deal.ciudad or 'N/A'}",
    ]
    if deal.contacto:
        lines.append(f"Contacto: {deal.contacto}")
    if deal.valor_mensual > 0 or deal.setup > 0:
        lines.append(f"Inversión objetivo: setup {deal.setup:.0f}€ | mensual {deal.valor_mensual:.0f}€")
    if deal.siguiente_paso:
        lines.append(f"Siguiente paso: {deal.siguiente_paso}")
    if deal.objeciones:
        lines.append("\nObjeciones:")
        for obj in deal.objeciones[-5:]:
            lines.append(f"- {obj}")
    if deal.razon_perdido:
        lines.append(f"Razón de pérdida: {deal.razon_perdido}")
    if deal.propuesta:
        preview = deal.propuesta[:280].replace("\n", " ").strip()
        suffix = "..." if len(deal.propuesta) > 280 else ""
        lines.append(f"\nPropuesta (preview): {preview}{suffix}")
    lines.append(f"\nActualizado: {deal.updated_at[:10]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Natural language detection
# ---------------------------------------------------------------------------

_DEAL_LIST_PATTERNS = [
    re.compile(r"\bmis\s+deals\b", re.IGNORECASE),
    re.compile(r"\bpipeline\b", re.IGNORECASE),
    re.compile(r"oportunidades\s+de\s+venta", re.IGNORECASE),
    re.compile(r"en\s+qu[eé]\s+estado\s+van\s+los\s+cierres", re.IGNORECASE),
]

_DEAL_ADD_PATTERNS = [
    re.compile(r"(?:a[nñ]ade|agrega)\s+deal[:\s]+(.+)", re.IGNORECASE),
    re.compile(r"nueva\s+oportunidad[:\s]+(.+)", re.IGNORECASE),
]


def detect_deal_intent(text: str) -> tuple[str, dict] | None:
    text = text.strip()
    for p in _DEAL_LIST_PATTERNS:
        if p.search(text):
            return ("list", {})
    for p in _DEAL_ADD_PATTERNS:
        m = p.search(text)
        if m:
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) >= 2:
                ciudad = parts[2] if len(parts) > 2 else ""
                return ("add", {"empresa": parts[0], "sector": parts[1], "ciudad": ciudad})
    return None
