"""
Duendes AIOS — CS (Customer Success) Module
Reads/writes clients directly to Airtable (Clients table, tbl4Z31UWesy9NmB2).

Required Airtable fields on the Clients table (existing + to add):
  EXISTING: Empresa, Nombre, Email, Teléfono, Sector, Servicio, Estado,
            Valor contrato, Stripe Customer ID, Drive Folder URL, Fecha inicio
  ADD THESE:
    Último check-in  (Date field, YYYY-MM-DD)
    Churn risk       (Single select: Bajo, Medio, Alto)
    Notas CS         (Long text)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from airtable_client import AirtableClient, AirtableError, TABLE_CLIENTS, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
logger = logging.getLogger("duendes-bot.cs_clients")

# Re-export under old names so bot.py imports don't break
EngramConnectionError = AirtableError
EngramDataError = AirtableError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SECTORES: set[str] = {"fisio", "quiro", "dental", "abogados", "estetica", "general"}
VALID_ESTADOS: set[str] = {"activo", "pausado", "churned"}
VALID_CHURN_RISK: set[str] = {"bajo", "medio", "alto"}
CHECKIN_STALE_DAYS: int = 14
_CFO_AVAILABLE = True  # exported for bot.py compatibility

# ---------------------------------------------------------------------------
# Field mappings
# ---------------------------------------------------------------------------

_AT_SECTOR_MAP: dict[str, str] = {
    "fisioterapia":       "fisio",
    "quiropráctica":      "quiro",
    "quiropraxia":        "quiro",
    "clínica dental":     "dental",
    "clinica dental":     "dental",
    "bufete / legal":     "abogados",
    "centro de estética": "estetica",
    "otro":               "general",
}

_AT_ESTADO_MAP: dict[str, str] = {
    "activo":     "activo",
    "pausado":    "pausado",
    "completado": "pausado",
    "churn":      "churned",
}

_SECTOR_TO_AT: dict[str, str] = {
    "fisio":    "Fisioterapia",
    "quiro":    "Quiropráctica",
    "dental":   "Clínica Dental",
    "abogados": "Bufete / Legal",
    "estetica": "Centro de Estética",
    "general":  "Otro",
}

_ESTADO_TO_AT: dict[str, str] = {
    "activo":  "Activo",
    "pausado": "Pausado",
    "churned": "Churn",
}

_RISK_TO_AT: dict[str, str] = {"bajo": "Bajo", "medio": "Medio", "alto": "Alto"}
_AT_RISK_MAP: dict[str, str] = {"bajo": "bajo", "medio": "medio", "alto": "alto"}


def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).strip()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Client:
    id: str                      # Airtable record ID
    nombre: str                  # Business name ("Empresa")
    contacto: str                # Contact person ("Nombre")
    sector: str                  # internal slug
    mrr: float                   # Monthly recurring revenue ("Valor contrato")
    estado: str                  # activo | pausado | churned
    fecha_inicio: str            # YYYY-MM-DD
    ultimo_checkin: str | None   # YYYY-MM-DD or None
    churn_risk: str              # bajo | medio | alto
    notas: str                   # free text notes

    @classmethod
    def from_airtable(cls, record: dict) -> "Client":
        f = record.get("fields", {})
        raw_mrr = _f(f, "Valor contrato")
        try:
            mrr = float(str(raw_mrr).replace("€", "").replace(",", ".").strip() or 0)
        except ValueError:
            mrr = 0.0
        checkin = _f(f, "Último check-in") or None
        return cls(
            id=record["id"],
            nombre=_f(f, "Empresa"),
            contacto=_f(f, "Nombre"),
            sector=_AT_SECTOR_MAP.get(_f(f, "Sector").lower(), "general"),
            mrr=mrr,
            estado=_AT_ESTADO_MAP.get(_f(f, "Estado").lower(), "activo"),
            fecha_inicio=_f(f, "Fecha inicio"),
            ultimo_checkin=checkin if checkin else None,
            churn_risk=_AT_RISK_MAP.get(_f(f, "Churn risk").lower(), "bajo"),
            notas=_f(f, "Notas CS"),
        )

    def to_airtable_fields(self) -> dict:
        fields: dict[str, Any] = {}
        if self.nombre:
            fields["Empresa"] = self.nombre
        if self.contacto:
            fields["Nombre"] = self.contacto
        if self.sector:
            fields["Sector"] = _SECTOR_TO_AT.get(self.sector, "Otro")
        if self.mrr:
            fields["Valor contrato"] = str(self.mrr)
        if self.estado:
            fields["Estado"] = _ESTADO_TO_AT.get(self.estado, "Activo")
        if self.fecha_inicio:
            fields["Fecha inicio"] = self.fecha_inicio
        if self.ultimo_checkin:
            fields["Último check-in"] = self.ultimo_checkin
        if self.churn_risk:
            fields["Churn risk"] = _RISK_TO_AT.get(self.churn_risk, "Bajo")
        if self.notas:
            fields["Notas CS"] = self.notas
        return fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _churn_risk_sort_key(risk: str) -> int:
    return {"alto": 0, "medio": 1, "bajo": 2}.get(risk, 1)


def _needs_checkin(client: Client) -> bool:
    if client.ultimo_checkin is None:
        return True
    cutoff = (datetime.now(timezone.utc) - timedelta(days=CHECKIN_STALE_DAYS)).date().isoformat()
    return client.ultimo_checkin < cutoff


# ---------------------------------------------------------------------------
# CRUD — async (bot.py)
# ---------------------------------------------------------------------------

async def get_clients() -> list[Client]:
    """Return raw list of Client objects for bot cache."""
    at = get_client()
    records = await at.list_records(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
    return [Client.from_airtable(r) for r in records if r.get("fields", {}).get("Empresa")]


async def add_client(nombre: str, contacto: str, sector: str, mrr: float) -> Client:
    at = get_client()
    client = Client(
        id="",
        nombre=nombre.strip(),
        contacto=contacto.strip(),
        sector=sector.strip().lower(),
        mrr=float(mrr or 0.0),
        estado="activo",
        fecha_inicio=_today_iso(),
        ultimo_checkin=None,
        churn_risk="bajo",
        notas="",
    )
    record = await at.create_record(TABLE_CLIENTS, client.to_airtable_fields())
    return Client.from_airtable(record)


async def list_clients() -> str:
    at = get_client()
    records = await at.list_records(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
    active = [Client.from_airtable(r) for r in records if r.get("fields", {}).get("Empresa")]
    if not active:
        return "No hay clientes activos."

    active_sorted = sorted(active, key=lambda c: (_churn_risk_sort_key(c.churn_risk), c.nombre))
    lines = ["*Clientes activos*\n"]
    for i, c in enumerate(active_sorted, 1):
        risk_emoji = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}.get(c.churn_risk, "⚪")
        checkin_str = f"último check-in: {c.ultimo_checkin}" if c.ultimo_checkin else "sin check-in"
        lines.append(
            f"{risk_emoji} #{i} *{c.nombre}* [{c.sector}] — {c.mrr:.0f}€/mes\n"
            f"  Contacto: {c.contacto} | {checkin_str}"
        )

    total_mrr = sum(c.mrr for c in active)
    lines.append(f"\n*MRR total: {total_mrr:.0f}€/mes*")
    return "\n".join(lines)


async def log_checkin(record_id: str, notas: str = "") -> Client | None:
    at = get_client()
    fields: dict[str, Any] = {"Último check-in": _today_iso()}
    if notas.strip():
        # Get current notes to append
        records = await at.list_records(TABLE_CLIENTS, filter_formula=f"RECORD_ID()='{record_id}'")
        if records:
            existing = _f(records[0].get("fields", {}), "Notas CS")
            entry = f"[{_today_iso()}] {notas.strip()}"
            fields["Notas CS"] = (existing + "\n" + entry) if existing else entry
    try:
        record = await at.update_record(TABLE_CLIENTS, record_id, fields)
        return Client.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def set_churn_risk(record_id: str, risk: str) -> Client | None:
    if risk not in VALID_CHURN_RISK:
        raise ValueError(f"Invalid churn_risk: {risk!r}")
    at = get_client()
    try:
        record = await at.update_record(TABLE_CLIENTS, record_id, {"Churn risk": _RISK_TO_AT[risk]})
        return Client.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def get_churn_report() -> str:
    at = get_client()
    records = await at.list_records(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
    clients = [Client.from_airtable(r) for r in records]
    at_risk = sorted(
        [c for c in clients if c.churn_risk in {"alto", "medio"}],
        key=lambda c: _churn_risk_sort_key(c.churn_risk),
    )
    if not at_risk:
        return "No hay clientes en riesgo de churn."

    lines = ["*Clientes en riesgo de churn*\n"]
    for c in at_risk:
        risk_emoji = {"alto": "🔴", "medio": "🟡"}.get(c.churn_risk, "⚪")
        checkin_str = f"último check-in: {c.ultimo_checkin}" if c.ultimo_checkin else "sin check-in"
        lines.append(
            f"{risk_emoji} *{c.nombre}* [{c.sector}] — {c.mrr:.0f}€/mes\n"
            f"  Contacto: {c.contacto} | {checkin_str}"
        )
    return "\n".join(lines)


async def get_total_mrr() -> float:
    at = get_client()
    records = await at.list_records(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
    clients = [Client.from_airtable(r) for r in records]
    return sum(c.mrr for c in clients)


# ---------------------------------------------------------------------------
# Brief sync helper
# ---------------------------------------------------------------------------

def get_checkins_for_brief_sync() -> str | None:
    at = get_client()
    try:
        records = at.list_records_sync(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
        clients = [Client.from_airtable(r) for r in records]
        stale = [c for c in clients if _needs_checkin(c)]
    except Exception as exc:
        logger.error("brief cs sync error: %s", exc)
        return None

    if not stale:
        return None

    lines = ["Check-in pendiente (>14 días):"]
    for c in stale:
        last = c.ultimo_checkin or "nunca"
        lines.append(f"- {c.nombre} [{c.sector}] — último: {last}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NL intent detection (unchanged)
# ---------------------------------------------------------------------------

_CS_PATTERNS = [
    re.compile(r"\bclientes?\s+activos?\b", re.IGNORECASE),
    re.compile(r"\bcheck[\s-]?ins?\b", re.IGNORECASE),
    re.compile(r"\bchurn\b", re.IGNORECASE),
    re.compile(r"qui[eé]n\s+(?:est[aá]|lleva)\s+(?:bien|mal|en\s+riesgo)", re.IGNORECASE),
    re.compile(r"\bMRR\b"),
]


def detect_cs_intent(text: str) -> tuple[str, dict] | None:
    text = text.strip()
    if re.search(r"\bchurn\b", text, re.IGNORECASE):
        return ("churn", {})
    if re.search(r"\bMRR\b", text):
        return ("mrr", {})
    for p in _CS_PATTERNS:
        if p.search(text):
            return ("list", {})
    return None


# Formatters
def format_client_added(client: Client) -> str:
    return f"Cliente añadido: {client.nombre} [{client.sector}] — {client.mrr:.0f}€/mes"


def format_checkin_logged(client: Client) -> str:
    return f"Check-in registrado para {client.nombre} ({_today_iso()})"


def format_churn_risk_updated(client: Client) -> str:
    risk_emoji = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}.get(client.churn_risk, "⚪")
    return f"Churn risk actualizado para {client.nombre}: {risk_emoji} {client.churn_risk}"
