"""
Duendes AIOS — Autonomous Monitor
Runs every 4 hours via launchd. Performs silent background work and escalates
only when something requires Oscar's attention.

Checks (in order):
  1. CFO: Mark overdue invoices as Vencida → alert if any found
  2. CS:  Alert on clients with churn_risk=Alto + check-in stale > 14 days
  3. SDR: Remind about leads stuck as Nuevo > 3 days
  4. AE:  Nudge about deals not updated > 7 days in active states

Each check is independent — one failure doesn't block the others.
Alerts are sent directly via Telegram HTTP API (no bot process needed).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
import langfuse_init  # noqa: F401 — instrumenta Anthropic automáticamente

try:
    from slack_notify import send_monitor_alert
    _SLACK_AVAILABLE = True
except ImportError:
    _SLACK_AVAILABLE = False

# ── bootstrap ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
sys.path.insert(0, str(SCRIPT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "logs" / "monitor.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("duendes-aios.monitor")

# ── config ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OSCAR_TELEGRAM_ID: str = os.getenv("OSCAR_TELEGRAM_ID", "")

LEAD_STALE_DAYS   = 3    # Leads in Estado=Nuevo without contact
DEAL_STALE_DAYS   = 7    # Deals in active states not updated
CHECKIN_STALE_DAYS = 14  # CS clients without check-in

# ── Telegram ───────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    """Send a message to Oscar via Telegram Bot API (sync, no bot process needed)."""
    if not TELEGRAM_BOT_TOKEN or not OSCAR_TELEGRAM_ID:
        logger.error("Telegram credentials not configured — cannot send alert")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                url,
                json={
                    "chat_id": OSCAR_TELEGRAM_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            resp.raise_for_status()
        logger.info("Telegram alert sent: %s chars", len(text))
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)


# ── helpers ────────────────────────────────────────────────────────────────

def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return str(v[0]).strip() if v else default
    return str(v).strip()


# ── CFO check ─────────────────────────────────────────────────────────────

def check_cfo() -> list[str]:
    """
    Mark Pendiente invoices past due as Vencida.
    Returns list of alert lines if any were marked.
    """
    from airtable_client import get_client, TABLE_INVOICES
    at = get_client()
    today = _today_iso()
    alerts: list[str] = []
    try:
        records = at.list_records_sync(
            TABLE_INVOICES,
            filter_formula="{Estado}='Pendiente'",
        )
    except Exception as exc:
        logger.error("CFO check failed (list): %s", exc)
        return []

    for r in records:
        f = r.get("fields", {})
        vencimiento = _f(f, "Fecha vencimiento")
        if vencimiento and vencimiento < today:
            cliente_raw = f.get("Cliente", "?")
            if isinstance(cliente_raw, list):
                cliente = cliente_raw[0] if cliente_raw else "?"
            else:
                cliente = str(cliente_raw)
            importe_raw = _f(f, "Importe") or "0"
            try:
                importe = float(importe_raw.replace("€", "").replace(",", ".").strip())
            except ValueError:
                importe = 0.0
            numero = _f(f, "Número factura") or r["id"][:8]
            try:
                at.update_record_sync(TABLE_INVOICES, r["id"], {"Estado": "Vencida"})
                alerts.append(f"  • {numero} {importe:.0f}€ — vencida el {vencimiento}")
                logger.info("Marked invoice %s as Vencida", numero)
            except Exception as exc:
                logger.error("CFO check: failed to update invoice %s: %s", r["id"], exc)

    return alerts


# ── CS check ──────────────────────────────────────────────────────────────

def check_cs() -> list[str]:
    """
    Alert on active clients with churn_risk=Alto AND last check-in > 14 days ago.
    Returns list of alert lines.
    """
    from airtable_client import get_client, TABLE_CLIENTS
    at = get_client()
    cutoff = _days_ago(CHECKIN_STALE_DAYS)
    alerts: list[str] = []
    try:
        records = at.list_records_sync(
            TABLE_CLIENTS,
            filter_formula="AND({Estado}='Activo', {Churn risk}='Alto')",
        )
    except Exception as exc:
        logger.error("CS check failed: %s", exc)
        return []

    for r in records:
        f = r.get("fields", {})
        nombre = _f(f, "Empresa") or "?"
        checkin = _f(f, "Último check-in") or None
        if checkin is None or checkin < cutoff:
            last = checkin or "nunca"
            alerts.append(f"  • {nombre} — último check-in: {last}")
            logger.info("CS alert: %s stale check-in (last: %s)", nombre, last)

    return alerts


# ── SDR check ─────────────────────────────────────────────────────────────

def check_sdr() -> list[str]:
    """
    Alert on leads in Estado=Nuevo that haven't been updated in > 3 days.
    Uses Airtable createdTime as proxy (no explicit 'last updated' field).
    Returns list of alert lines.
    """
    from airtable_client import get_client, TABLE_LEADS
    at = get_client()
    cutoff = _days_ago(LEAD_STALE_DAYS)
    alerts: list[str] = []
    try:
        records = at.list_records_sync(
            TABLE_LEADS,
            filter_formula="{Estado}='Nuevo'",
        )
    except Exception as exc:
        logger.error("SDR check failed: %s", exc)
        return []

    for r in records:
        created = r.get("createdTime", "")[:10]
        if created and created <= cutoff:
            f = r.get("fields", {})
            empresa = _f(f, "Empresa") or "?"
            telefono = _f(f, "Teléfono") or "—"
            alerts.append(f"  • {empresa} ({telefono}) — sin contacto desde {created}")
            logger.info("SDR alert: lead %s stale since %s", empresa, created)

    return alerts[:10]  # cap at 10 to avoid flooding


# ── AE check ──────────────────────────────────────────────────────────────

def check_ae() -> list[str]:
    """
    Alert on active deals (demo/propuesta/negociacion) not updated in > 7 days.
    Uses createdTime as proxy (AE module doesn't track 'last updated' separately).
    Returns list of alert lines.
    """
    from airtable_client import get_client, TABLE_DEALS
    at = get_client()
    cutoff = _days_ago(DEAL_STALE_DAYS)
    active_estados = {"Demo", "Propuesta", "Negociacion"}
    alerts: list[str] = []
    try:
        records = at.list_records_sync(TABLE_DEALS)
    except Exception as exc:
        logger.error("AE check failed: %s", exc)
        return []

    for r in records:
        f = r.get("fields", {})
        estado = _f(f, "Estado")
        if estado not in active_estados:
            continue
        created = r.get("createdTime", "")[:10]
        if created and created <= cutoff:
            empresa = _f(f, "Empresa") or "?"
            alerts.append(f"  • {empresa} [{estado}] — en pipeline desde {created}")
            logger.info("AE alert: deal %s in %s since %s", empresa, estado, created)

    return alerts


# ── main ───────────────────────────────────────────────────────────────────

def run_monitor() -> None:
    logger.info("Monitor run started")
    now_str = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")
    alert_sections: list[str] = []

    # 1. CFO — overdue invoices
    cfo_alerts = check_cfo()
    if cfo_alerts:
        section = "🔴 *Facturas marcadas como vencidas*\n" + "\n".join(cfo_alerts)
        alert_sections.append(section)
        if _SLACK_AVAILABLE:
            send_monitor_alert("cfo", section)

    # 2. CS — high churn + stale check-in
    cs_alerts = check_cs()
    if cs_alerts:
        section = "⚠️ *Clientes en riesgo sin check-in reciente*\n" + "\n".join(cs_alerts)
        alert_sections.append(section)
        if _SLACK_AVAILABLE:
            send_monitor_alert("cs", section)

    # 3. SDR — stale Nuevo leads
    sdr_alerts = check_sdr()
    if sdr_alerts:
        section = f"📋 *Leads sin contactar (>{LEAD_STALE_DAYS} días)*\n" + "\n".join(sdr_alerts)
        alert_sections.append(section)
        if _SLACK_AVAILABLE:
            send_monitor_alert("sdr", section)

    # 4. AE — stale active deals
    ae_alerts = check_ae()
    if ae_alerts:
        section = f"💼 *Deals activos sin actividad (>{DEAL_STALE_DAYS} días)*\n" + "\n".join(ae_alerts)
        alert_sections.append(section)
        if _SLACK_AVAILABLE:
            send_monitor_alert("ae", section)

    if alert_sections:
        header = f"🤖 *Monitor AIOS* — {now_str}\n"
        message = header + "\n\n".join(alert_sections)
        _send_telegram(message)
        logger.info("Sent alert with %d section(s)", len(alert_sections))
    else:
        logger.info("All clear — no alerts to send")


if __name__ == "__main__":
    (SCRIPT_DIR / "logs").mkdir(exist_ok=True)
    run_monitor()
