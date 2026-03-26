"""
Duendes AIOS — SDR Lead Management Module
Reads/writes leads directly to Airtable (Leads table, tblyTzWUXxpWeHJaB).
Engram is no longer used for lead storage — only for AI context/learnings.

Required Airtable fields on the Leads table:
  Empresa (text)          — business name
  Nombre (text)           — contact person
  Email (email)
  Teléfono (phone)
  Sector (single select)  — options: Fisioterapia, Clínica Dental, Bufete / Legal,
                            Gestoría, Centro de Estética, Otro, ...
  Estado (single select)  — options: Nuevo, Contactado, Reunión agendada,
                            Propuesta enviada, Negociación, Ganado, Perdido, Incorrecto
  Fuente (text/select)
  Notas (long text)
  Próximo seguimiento (date, YYYY-MM-DD)   ← add this field if not present
  Último contacto (date, YYYY-MM-DD)       ← add this field if not present
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from airtable_client import AirtableClient, AirtableError, TABLE_LEADS, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

logger = logging.getLogger("duendes-bot.sdr_leads")

# ---------------------------------------------------------------------------
# Re-export AirtableError under the old name so bot.py imports don't break
# ---------------------------------------------------------------------------

EngramConnectionError = AirtableError
EngramDataError = AirtableError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SECTORS: set[str] = {"dental", "fisio", "abogados", "gestoria", "estetica", "oficios", "otro"}
VALID_ESTADOS: set[str] = {"prospecto", "contactado", "respondio", "reunion", "descartado", "cliente"}
ESTADO_ORDER: dict[str, int] = {
    "prospecto": 0,
    "contactado": 1,
    "respondio": 2,
    "reunion": 3,
    "cliente": 4,
    "descartado": 5,
}

# ---------------------------------------------------------------------------
# Field mappings: internal ↔ Airtable
# ---------------------------------------------------------------------------

# Airtable sector select option → internal slug
_AT_SECTOR_MAP: dict[str, str] = {
    "fisioterapia":          "fisio",
    "clínica dental":        "dental",
    "clinica dental":        "dental",
    "bufete / legal":        "abogados",
    "bufete/legal":          "abogados",
    "gestoría":              "gestoria",
    "gestoria":              "gestoria",
    "consultoría":           "consultoria",
    "consultoria":           "consultoria",
    "centro de estética":    "estetica",
    "peluquería / barbería": "peluqueria",
    "fontanería":            "fontaneria",
    "electricidad":          "electricidad",
    "reformas":              "reformas",
    "comercio":              "comercio",
    "oficios":               "oficios",
    "otro":                  "otro",
}

# Internal sector slug → Airtable select option (for writes)
_SECTOR_TO_AT: dict[str, str] = {
    "fisio":       "Fisioterapia",
    "dental":      "Clínica Dental",
    "abogados":    "Bufete / Legal",
    "gestoria":    "Gestoría",
    "consultoria": "Consultoría",
    "estetica":    "Centro de Estética",
    "peluqueria":  "Peluquería / Barbería",
    "fontaneria":  "Fontanería",
    "electricidad":"Electricidad",
    "reformas":    "Reformas",
    "comercio":    "Comercio",
    "oficios":     "Oficios",
    "otro":        "Otro",
}

# Airtable estado select option → internal slug
_AT_ESTADO_MAP: dict[str, str] = {
    "nuevo":               "prospecto",
    "contactado":          "contactado",
    "reunión agendada":    "reunion",
    "reunion agendada":    "reunion",
    "propuesta enviada":   "reunion",
    "negociación":         "reunion",
    "negociacion":         "reunion",
    "ganado":              "cliente",
    "perdido":             "descartado",
    "incorrecto":          "descartado",
}

# Internal estado slug → Airtable select option (for writes)
_ESTADO_TO_AT: dict[str, str] = {
    "prospecto":  "Nuevo",
    "contactado": "Contactado",
    "respondio":  "Contactado",
    "reunion":    "Reunión agendada",
    "cliente":    "Ganado",
    "descartado": "Perdido",
}


def _norm_sector(raw: str) -> str:
    return _AT_SECTOR_MAP.get(raw.lower().strip(), raw.lower().strip() or "otro")


def _norm_estado(raw: str) -> str:
    return _AT_ESTADO_MAP.get(raw.lower().strip(), "prospecto")


def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, bool):
        return "sí" if v else "no"
    return str(v).strip()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Lead:
    id: str               # Airtable record ID (e.g. "recABCDEFGHIJKLMN")
    nombre: str           # Business name ("Empresa" in Airtable)
    contacto: str         # Contact person name ("Nombre" in Airtable)
    email: str
    telefono: str
    sector: str           # internal slug: fisio | dental | abogados | ...
    ciudad: str           # stored in Notas if not an Airtable field
    estado: str           # internal slug: prospecto | contactado | ...
    notas: str
    created_at: str       # ISO 8601 from Airtable createdTime
    last_contact: str     # YYYY-MM-DD ("Último contacto" if field exists)
    next_followup: str    # YYYY-MM-DD ("Próximo seguimiento" if field exists)
    source: str           # lead source ("Fuente" in Airtable)
    plan_objetivo: str    # pricing tier target (stored in Notas)

    @classmethod
    def from_airtable(cls, record: dict) -> "Lead":
        """Parse an Airtable record dict into a Lead."""
        f = record.get("fields", {})
        return cls(
            id=record["id"],
            nombre=_f(f, "Empresa"),
            contacto=_f(f, "Nombre"),
            email=_f(f, "Email"),
            telefono=_f(f, "Teléfono"),
            sector=_norm_sector(_f(f, "Sector")),
            ciudad=_f(f, "Ciudad"),
            estado=_norm_estado(_f(f, "Estado")),
            notas=_f(f, "Notas"),
            created_at=record.get("createdTime", ""),
            last_contact=_f(f, "Último contacto"),
            next_followup=_f(f, "Próximo seguimiento"),
            source=_f(f, "Fuente").lower() or "manual",
            plan_objetivo="",  # not in Airtable — stored in Notas if needed
        )

    def to_airtable_fields(self) -> dict:
        """
        Return a dict of Airtable field names → values for create/update.
        Only includes fields that exist in the Leads table schema.
        """
        fields: dict[str, Any] = {}
        if self.nombre:
            fields["Empresa"] = self.nombre
        if self.contacto:
            fields["Nombre"] = self.contacto
        if self.email:
            fields["Email"] = self.email
        if self.telefono:
            fields["Teléfono"] = self.telefono
        if self.sector:
            fields["Sector"] = _SECTOR_TO_AT.get(self.sector, self.sector.capitalize())
        if self.estado:
            fields["Estado"] = _ESTADO_TO_AT.get(self.estado, "Nuevo")
        if self.source:
            fields["Fuente"] = self.source
        if self.notas:
            fields["Notas"] = self.notas
        # Optional date fields — written only if field exists in Airtable
        # (Oscar should add "Próximo seguimiento" and "Último contacto" as Date fields)
        if self.next_followup:
            fields["Próximo seguimiento"] = self.next_followup
        if self.last_contact:
            fields["Último contacto"] = self.last_contact
        return fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_iso() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estado_sort_key(estado: str) -> int:
    return ESTADO_ORDER.get(estado, 99)


# ---------------------------------------------------------------------------
# CRUD — async (bot.py)
# ---------------------------------------------------------------------------

async def list_leads(
    estado: str | None = None,
    sector: str | None = None,
) -> list[Lead]:
    """
    Fetch leads from Airtable. Optional filters by estado and sector.
    Returns leads sorted by estado priority then createdTime.
    """
    at = get_client()
    formula_parts: list[str] = []
    if estado:
        at_estado = _ESTADO_TO_AT.get(estado, estado.capitalize())
        formula_parts.append(f"{{Estado}}='{at_estado}'")
    if sector:
        at_sector = _SECTOR_TO_AT.get(sector, sector.capitalize())
        formula_parts.append(f"{{Sector}}='{at_sector}'")

    formula = f"AND({','.join(formula_parts)})" if len(formula_parts) > 1 else (formula_parts[0] if formula_parts else None)

    records = await at.list_records(TABLE_LEADS, filter_formula=formula)
    leads = [Lead.from_airtable(r) for r in records if r.get("fields", {}).get("Empresa") or r.get("fields", {}).get("Nombre")]
    return sorted(leads, key=lambda l: (_estado_sort_key(l.estado), l.created_at))


async def get_lead(record_id: str) -> Lead | None:
    """
    Get a single lead by Airtable record ID.
    Returns None if the record doesn't exist.
    """
    at = get_client()
    # Fetch all and find — Airtable's single-record GET also works but
    # list_records allows us to reuse pagination logic.
    records = await at.list_records(TABLE_LEADS, filter_formula=f"RECORD_ID()='{record_id}'")
    if not records:
        return None
    return Lead.from_airtable(records[0])


async def add_lead(
    nombre: str,
    sector: str,
    ciudad: str = "",
    contacto: str = "",
    email: str = "",
    telefono: str = "",
    notas: str = "",
    source: str = "manual",
    plan_objetivo: str = "",
) -> Lead:
    """Create a new lead in Airtable. Returns the created Lead."""
    at = get_client()
    lead = Lead(
        id="",  # assigned by Airtable
        nombre=nombre.strip(),
        contacto=contacto.strip(),
        email=email.strip(),
        telefono=telefono.strip(),
        sector=sector.strip().lower(),
        ciudad=ciudad.strip(),
        estado="prospecto",
        notas=notas.strip(),
        created_at=_now_iso(),
        last_contact="",
        next_followup="",
        source=source,
        plan_objetivo=plan_objetivo.strip(),
    )
    fields = lead.to_airtable_fields()
    # Add ciudad to Notas if there's no Ciudad field
    if ciudad:
        city_prefix = f"[Ciudad: {ciudad}] "
        fields["Notas"] = city_prefix + (fields.get("Notas") or "")
    record = await at.create_record(TABLE_LEADS, fields)
    return Lead.from_airtable(record)


async def update_lead_estado(record_id: str, nuevo_estado: str) -> Lead | None:
    """
    Update the Estado field of a lead. Returns the updated Lead.
    Returns None if the record is not found (Airtable 404).
    """
    if nuevo_estado not in VALID_ESTADOS:
        raise ValueError(f"Invalid estado: {nuevo_estado!r}. Valid: {sorted(VALID_ESTADOS)}")

    at = get_client()
    at_estado = _ESTADO_TO_AT.get(nuevo_estado, "Nuevo")
    fields: dict[str, Any] = {"Estado": at_estado}

    # Update last_contact on outreach transitions
    if nuevo_estado in {"contactado", "respondio", "reunion"}:
        fields["Último contacto"] = _today_iso()

    try:
        record = await at.update_record(TABLE_LEADS, record_id, fields)
        return Lead.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc) or "NOT_FOUND" in str(exc):
            return None
        raise


async def add_lead_nota(record_id: str, nota: str) -> Lead | None:
    """Append a timestamped note to the Notas field. Returns updated Lead."""
    at = get_client()
    # First, get current notas
    records = await at.list_records(TABLE_LEADS, filter_formula=f"RECORD_ID()='{record_id}'")
    if not records:
        return None
    existing = _f(records[0].get("fields", {}), "Notas")
    new_entry = f"[{_today_iso()}] {nota.strip()}"
    updated = (existing + "\n" + new_entry) if existing else new_entry
    record = await at.update_record(TABLE_LEADS, record_id, {"Notas": updated})
    return Lead.from_airtable(record)


async def set_followup(record_id: str, fecha: str) -> Lead | None:
    """Set the 'Próximo seguimiento' date. Returns updated Lead."""
    at = get_client()
    try:
        record = await at.update_record(TABLE_LEADS, record_id, {"Próximo seguimiento": fecha})
        return Lead.from_airtable(record)
    except Exception as exc:
        if "UNKNOWN_FIELD_NAME" in str(exc):
            logger.warning(
                "Campo 'Próximo seguimiento' no existe en Airtable. "
                "Añádelo como campo Date para usar follow-ups."
            )
            return None
        raise


async def get_followup_leads() -> list[Lead]:
    """Return leads with 'Próximo seguimiento' <= today."""
    at = get_client()
    today = _today_iso()
    try:
        formula = f"AND({{Próximo seguimiento}}<='', IS_AFTER(TODAY(), {{Próximo seguimiento}}))"
        # Simpler: fetch all and filter in Python (Airtable date comparisons can be tricky)
        records = await at.list_records(TABLE_LEADS)
        leads = [Lead.from_airtable(r) for r in records]
        due = [l for l in leads if l.next_followup and l.next_followup <= today]
        return sorted(due, key=lambda l: l.next_followup)
    except AirtableError as exc:
        logger.error("Error fetching followup leads: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Sync variants (brief.py)
# ---------------------------------------------------------------------------

def get_followups_for_brief_sync() -> str:
    """Sync variant for brief.py. Returns formatted follow-up section."""
    at = get_client()
    today = _today_iso()
    try:
        records = at.list_records_sync(TABLE_LEADS)
        leads = [Lead.from_airtable(r) for r in records]
        due = sorted(
            [l for l in leads if l.next_followup and l.next_followup <= today],
            key=lambda l: l.next_followup,
        )
    except Exception as exc:
        logger.error("brief sync error: %s", exc)
        return "Error al cargar leads."

    if not due:
        return "No hay follow-ups pendientes."

    lines = ["Follow-ups pendientes:"]
    for lead in due:
        overdue = lead.next_followup < today
        label = "ATRASADO" if overdue else f"vence: {lead.next_followup}"
        lines.append(f"- {lead.nombre} [{lead.sector}] — {label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email generation (unchanged — uses Claude API)
# ---------------------------------------------------------------------------

async def generate_cold_email(
    lead: Lead,
    context_os: str,
    anthropic_client: Any,
    module_system: str = "",
) -> str:
    system = module_system or (
        "Eres un experto en prospección B2B en España. "
        "Escribe emails de prospección en frío directos, sin florituras, en español de España."
    )
    user_prompt = f"""Genera un email de prospección en frío en español de España para este lead.

LEAD:
- Empresa: {lead.nombre}
- Contacto: {lead.contacto or 'desconocido'}
- Sector: {lead.sector}
- Plan sugerido: {lead.plan_objetivo or 'esencial (79€/mes)'}

CONTEXTO DUENDES:
{context_os}

INSTRUCCIONES:
- Primera línea = Asunto: (escribe el asunto aquí)
- Línea en blanco
- Cuerpo del email (máximo 5-6 líneas)
- Problema específico del sector {lead.sector} en España
- CTA claro: proponer una llamada de 15 minutos
- Voz directa, tuteo, España Spanish
- NO empieces con "Hola, soy" genérico
- Firma como Oscar de Duendes"""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_ESTADO_EMOJI: dict[str, str] = {
    "prospecto":  "🎯",
    "contactado": "📞",
    "respondio":  "💬",
    "reunion":    "🤝",
    "cliente":    "✅",
    "descartado": "❌",
}


def format_lead_list(leads: list[Lead], title: str = "Leads") -> str:
    """
    Format leads grouped by estado as Telegram Markdown.
    Uses sequential display numbers (1, 2, 3...) — the caller should maintain
    a cache mapping display number → lead.id (Airtable record ID).
    """
    if not leads:
        return "No hay leads registrados."

    groups: dict[str, list[tuple[int, Lead]]] = {e: [] for e in ESTADO_ORDER}
    for i, lead in enumerate(leads, 1):
        groups.setdefault(lead.estado, []).append((i, lead))

    lines = [f"*{title}*\n"]
    for estado in sorted(ESTADO_ORDER, key=lambda e: ESTADO_ORDER[e]):
        group = groups.get(estado, [])
        if not group:
            continue
        emoji = _ESTADO_EMOJI.get(estado, "")
        lines.append(f"{emoji} *{estado.capitalize()}*")
        for display_id, lead in group:
            contact = f" ({lead.contacto})" if lead.contacto else ""
            followup = f" _(followup: {lead.next_followup})_" if lead.next_followup else ""
            lines.append(f"  #{display_id} {lead.nombre}{contact} [{lead.sector}]{followup}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_lead_detail(lead: Lead, display_id: int = 0) -> str:
    emoji = _ESTADO_EMOJI.get(lead.estado, "")
    id_label = f"#{display_id}" if display_id else lead.id[:8]
    lines = [
        f"*Lead {id_label} — {lead.nombre}*",
        f"Estado: {emoji} {lead.estado}",
        f"Sector: {lead.sector}",
    ]
    if lead.contacto:
        lines.append(f"Contacto: {lead.contacto}")
    if lead.email:
        lines.append(f"Email: {lead.email}")
    if lead.telefono:
        lines.append(f"Teléfono: {lead.telefono}")
    if lead.plan_objetivo:
        lines.append(f"Plan objetivo: {lead.plan_objetivo}")
    if lead.next_followup:
        lines.append(f"Próximo seguimiento: {lead.next_followup}")
    if lead.last_contact:
        lines.append(f"Último contacto: {lead.last_contact}")
    lines.append(f"Fuente: {lead.source} | Creado: {lead.created_at[:10]}")
    if lead.notas:
        lines.append(f"\nNotas:\n{lead.notas}")
    return "\n".join(lines)


def format_lead_added(lead: Lead) -> str:
    return f"Lead creado: {lead.nombre} [{lead.sector}] — estado: prospecto"


def format_lead_estado_updated(lead: Lead) -> str:
    emoji = _ESTADO_EMOJI.get(lead.estado, "")
    return f"Lead actualizado: {lead.nombre} → {emoji} {lead.estado}"


def format_followup_list(leads: list[Lead]) -> str:
    if not leads:
        return "No hay follow-ups pendientes para hoy."
    today = _today_iso()
    lines = ["*Follow-ups pendientes*\n"]
    for i, lead in enumerate(leads, 1):
        overdue = lead.next_followup < today
        flag = " _(ATRASADO)_" if overdue else ""
        emoji = _ESTADO_EMOJI.get(lead.estado, "")
        lines.append(
            f"{emoji} #{i} *{lead.nombre}* [{lead.sector}]"
            f" — {lead.next_followup}{flag}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Natural language detection (unchanged)
# ---------------------------------------------------------------------------

_LEAD_LIST_PATTERNS = [
    re.compile(r"mis\s+leads", re.IGNORECASE),
    re.compile(r"qu[eé]\s+prospectos\s+tengo", re.IGNORECASE),
    re.compile(r"lista\s+de\s+leads", re.IGNORECASE),
    re.compile(r"\bleads\s+activos\b", re.IGNORECASE),
    re.compile(r"ver\s+prospectos", re.IGNORECASE),
    re.compile(r"\bprospectos\b", re.IGNORECASE),
]

_FOLLOWUP_PATTERNS = [
    re.compile(r"followups?\s+de\s+hoy", re.IGNORECASE),
    re.compile(r"a\s+qui[eé]n\s+(?:tengo\s+que\s+)?contactar", re.IGNORECASE),
    re.compile(r"pendientes\s+de\s+seguimiento", re.IGNORECASE),
    re.compile(r"qui[eé]n\s+me\s+falta\s+contactar", re.IGNORECASE),
]

_LEAD_ADD_PATTERNS = [
    re.compile(r"(?:a[nñ]ade|agrega)\s+lead[:\s]+(.+)", re.IGNORECASE),
    re.compile(r"nuevo\s+lead[:\s]+(.+)", re.IGNORECASE),
]


def detect_lead_intent(text: str) -> tuple[str, dict] | None:
    text = text.strip()
    for pattern in _FOLLOWUP_PATTERNS:
        if pattern.search(text):
            return ("followup", {})
    for pattern in _LEAD_LIST_PATTERNS:
        if pattern.search(text):
            return ("list", {})
    for pattern in _LEAD_ADD_PATTERNS:
        m = pattern.search(text)
        if m:
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) >= 3:
                return ("add", {"nombre": parts[0], "sector": parts[1], "ciudad": parts[2]})
            elif parts:
                return ("add", {"nombre": raw, "sector": "", "ciudad": ""})
    return None
