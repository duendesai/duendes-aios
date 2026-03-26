"""
Duendes AIOS — CFO Invoice & MRR Management Module
Reads/writes invoices directly to Airtable (Invoices table, tbl0ee0GLpZjQtrGe).

Required Airtable fields on the Invoices table:
  EXISTING: Número factura, Importe, Fecha, Estado, Stripe Payment ID, Gmail Link
  ADD THESE:
    Cliente          (Text)          — who the invoice is for
    Concepto         (Long text)     — description of service
    Fecha vencimiento (Date, YYYY-MM-DD)
    Notas            (Long text)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from airtable_client import AirtableClient, AirtableError, TABLE_INVOICES, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
logger = logging.getLogger("duendes-bot.cfo_invoices")

# Re-export under old names so bot.py imports don't break
EngramConnectionError = AirtableError
EngramDataError = AirtableError
_CFO_AVAILABLE = True

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ESTADOS: set[str] = {"pendiente", "pagada", "vencida"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _due_date_default() -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()


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
class Invoice:
    id: str                       # Airtable record ID
    numero: str                   # "Número factura"
    cliente: str                  # Display name (resolved from client cache)
    cliente_record_id: str | None # Airtable record ID of linked Client
    concepto: str                 # "Concepto"
    importe: float                # "Importe"
    estado: str                   # pendiente | pagada | vencida
    fecha_emision: str            # "Fecha" (creation date)
    fecha_vencimiento: str        # "Fecha vencimiento"
    notas: str                    # "Notas"

    @classmethod
    def from_airtable(cls, record: dict) -> "Invoice":
        f = record.get("fields", {})
        raw_importe = _f(f, "Importe")
        try:
            importe = float(str(raw_importe).replace("€", "").replace(",", ".").strip() or 0)
        except ValueError:
            importe = 0.0
        # "Cliente" is multipleRecordLinks — returns list of record IDs
        cliente_raw = f.get("Cliente", [])
        if isinstance(cliente_raw, list) and cliente_raw:
            cliente_record_id: str | None = cliente_raw[0]
            cliente = ""  # resolved later by bot via client cache
        else:
            cliente_record_id = None
            cliente = str(cliente_raw).strip() if cliente_raw else ""
        return cls(
            id=record["id"],
            numero=_f(f, "Número factura"),
            cliente=cliente,
            cliente_record_id=cliente_record_id,
            concepto=_f(f, "Concepto"),
            importe=importe,
            estado=_f(f, "Estado").lower() or "pendiente",
            fecha_emision=_f(f, "Fecha") or record.get("createdTime", "")[:10],
            fecha_vencimiento=_f(f, "Fecha vencimiento") or _due_date_default(),
            notas=_f(f, "Notas"),
        )

    def to_airtable_fields(self) -> dict:
        fields: dict[str, Any] = {}
        if self.numero:
            fields["Número factura"] = self.numero
        if self.cliente_record_id:
            fields["Cliente"] = [self.cliente_record_id]  # linked record: list of IDs
        if self.concepto:
            fields["Concepto"] = self.concepto
        if self.importe:
            fields["Importe"] = str(self.importe)
        if self.estado:
            fields["Estado"] = self.estado.capitalize()
        if self.fecha_emision:
            fields["Fecha"] = self.fecha_emision
        if self.fecha_vencimiento:
            fields["Fecha vencimiento"] = self.fecha_vencimiento
        if self.notas:
            fields["Notas"] = self.notas
        return fields


def _is_overdue(invoice: Invoice) -> bool:
    return invoice.fecha_vencimiento < _today_iso() and invoice.estado == "pendiente"


# ---------------------------------------------------------------------------
# CRUD — async (bot.py)
# ---------------------------------------------------------------------------

async def get_invoices() -> "list[Invoice]":
    """Return raw list of Invoice objects for bot cache."""
    at = get_client()
    records = await at.list_records(TABLE_INVOICES)
    return [Invoice.from_airtable(r) for r in records if r.get("fields")]


async def add_invoice(
    cliente_record_id: str,
    cliente_nombre: str,
    concepto: str,
    importe: float,
    fecha_vencimiento: str | None = None,
) -> Invoice:
    at = get_client()
    invoice = Invoice(
        id="",
        numero=f"F-{_today_iso().replace('-', '')}",
        cliente=cliente_nombre,
        cliente_record_id=cliente_record_id,
        concepto=concepto.strip(),
        importe=float(importe),
        estado="pendiente",
        fecha_emision=_today_iso(),
        fecha_vencimiento=fecha_vencimiento or _due_date_default(),
        notas="",
    )
    record = await at.create_record(TABLE_INVOICES, invoice.to_airtable_fields())
    inv = Invoice.from_airtable(record)
    inv.cliente = cliente_nombre  # restore name since Airtable returns only the record ID
    return inv


async def list_invoices(client_names: dict[str, str] | None = None) -> str:
    """List invoices. client_names: {record_id -> display name} for resolving linked clients."""
    at = get_client()
    records = await at.list_records(TABLE_INVOICES)
    invoices = [Invoice.from_airtable(r) for r in records if r.get("fields")]
    if client_names:
        for inv in invoices:
            if inv.cliente_record_id and not inv.cliente:
                inv.cliente = client_names.get(inv.cliente_record_id, "")
    if not invoices:
        return "No hay facturas registradas."

    groups: dict[str, list[Invoice]] = {"pendiente": [], "vencida": [], "pagada": []}
    for inv in invoices:
        groups.setdefault(inv.estado, []).append(inv)

    lines = ["*Facturas*\n"]
    for estado, emoji, label in [
        ("vencida",   "🔴", "Vencidas"),
        ("pendiente", "🟡", "Pendientes"),
        ("pagada",    "✅", "Pagadas"),
    ]:
        group = groups.get(estado, [])
        if not group:
            continue
        lines.append(f"{emoji} *{label}*")
        for inv in sorted(group, key=lambda i: i.fecha_vencimiento):
            lines.append(
                f"  {inv.numero or inv.id[:8]} {inv.cliente} — {inv.importe:.2f}€"
                f" | {inv.concepto[:30] if inv.concepto else '—'}"
                f" | vence: {inv.fecha_vencimiento}"
            )
        lines.append("")

    total_pendiente = sum(i.importe for i in invoices if i.estado in {"pendiente", "vencida"})
    lines.append(f"💶 *Pendiente de cobro: {total_pendiente:.2f}€*")
    return "\n".join(lines).rstrip()


async def mark_paid(record_id: str) -> Invoice | None:
    at = get_client()
    try:
        record = await at.update_record(TABLE_INVOICES, record_id, {"Estado": "Pagada"})
        return Invoice.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def check_overdue() -> int:
    """Auto-mark pendiente invoices past vencimiento as vencida. Returns count updated."""
    at = get_client()
    records = await at.list_records(
        TABLE_INVOICES,
        filter_formula="{Estado}='Pendiente'",
    )
    today = _today_iso()
    count = 0
    for r in records:
        f = r.get("fields", {})
        vencimiento = _f(f, "Fecha vencimiento")
        if vencimiento and vencimiento < today:
            await at.update_record(TABLE_INVOICES, r["id"], {"Estado": "Vencida"})
            count += 1
    if count:
        logger.info("Marked %d invoices as vencida", count)
    return count


async def get_mrr() -> str:
    at = get_client()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
    records = await at.list_records(TABLE_INVOICES, filter_formula="{Estado}='Pagada'")
    pagadas_30d = [
        Invoice.from_airtable(r) for r in records
        if _f(r.get("fields", {}), "Fecha") >= cutoff
    ]
    total_mrr = sum(i.importe for i in pagadas_30d)
    if not pagadas_30d:
        return "MRR (últimos 30 días): 0,00€ — sin facturas pagadas en este periodo."

    lines = [
        "📊 *MRR — últimos 30 días*",
        f"Facturas pagadas: {len(pagadas_30d)}",
        f"Total cobrado: {total_mrr:.2f}€",
        "",
        "*Detalle:*",
    ]
    for inv in sorted(pagadas_30d, key=lambda i: i.fecha_emision, reverse=True):
        lines.append(f"  {inv.numero or inv.id[:8]} {inv.cliente} — {inv.importe:.2f}€ ({inv.fecha_emision})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Brief sync helper
# ---------------------------------------------------------------------------

def get_pending_summary_for_brief_sync() -> str:
    at = get_client()
    today = _today_iso()
    try:
        records = at.list_records_sync(TABLE_INVOICES)
        invoices = [Invoice.from_airtable(r) for r in records if r.get("fields")]
    except Exception as exc:
        logger.error("brief cfo sync error: %s", exc)
        return "No hay facturas pendientes."

    pending = [i for i in invoices if i.estado in {"pendiente", "vencida"}]
    if not pending:
        return "No hay facturas pendientes."

    vencidas  = [i for i in pending if i.estado == "vencida" or (i.estado == "pendiente" and i.fecha_vencimiento < today)]
    pendientes = [i for i in pending if i not in vencidas]

    lines: list[str] = []
    if vencidas:
        lines.append("🔴 Vencidas:")
        for inv in sorted(vencidas, key=lambda i: i.fecha_vencimiento):
            lines.append(f"- {inv.cliente} — {inv.importe:.2f}€ (vencida: {inv.fecha_vencimiento})")
        lines.append("")
    if pendientes:
        lines.append("🟡 Pendientes de cobro:")
        for inv in sorted(pendientes, key=lambda i: i.fecha_vencimiento):
            lines.append(f"- {inv.cliente} — {inv.importe:.2f}€ (vence: {inv.fecha_vencimiento})")

    total = sum(i.importe for i in pending)
    lines.append(f"\nTotal pendiente: {total:.2f}€")
    return "\n".join(lines).rstrip()
