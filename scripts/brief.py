#!/usr/bin/env python3
"""
Duendes AIOS — Brief Diario
Genera y envía un brief de negocio cada mañana a las 8am via Telegram.
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import anthropic
import langfuse_init  # noqa: F401 — instrumenta Anthropic automáticamente
import httpx
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OSCAR_TELEGRAM_ID = os.getenv("OSCAR_TELEGRAM_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] brief — %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "scripts/logs/brief.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("brief")

# ── Días en español ──────────────────────────────────────────────────────────
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_hoy() -> str:
    hoy = datetime.now()
    dia_semana = DIAS[hoy.weekday()]
    return f"{dia_semana}, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


# ── Cargar contexto ──────────────────────────────────────────────────────────
def load_context() -> str:
    context_dir = BASE_DIR / "context"
    files = ["estrategia.md", "negocio.md", "ofertas.md", "clientes-ideales.md"]
    parts = []
    for fname in files:
        fpath = context_dir / fname
        if fpath.exists():
            parts.append(f"### {fname}\n{fpath.read_text()}")
    return "\n\n".join(parts)


try:
    from slack_notify import send_brief, send_weekly_report
    _SLACK_AVAILABLE = True
except ImportError:
    _SLACK_AVAILABLE = False

# ── Cargar tareas activas desde Engram ───────────────────────────────────────
try:
    from coo_tasks import EngramClient as _EngramClient, get_pending_for_brief_sync as _get_tasks_sync
    _COO_TASKS_AVAILABLE = True
except ImportError:
    _EngramClient = None  # type: ignore[assignment,misc]
    _COO_TASKS_AVAILABLE = False


def load_active_tasks() -> "str | None":
    """Load pending tasks from Engram for brief injection. Returns formatted string or None."""
    if not _COO_TASKS_AVAILABLE:
        log.warning("coo_tasks module not available — skipping task loading")
        return None
    try:
        return _get_tasks_sync()
    except Exception as exc:
        log.warning("Could not load tasks from Engram: %s", exc)
        return None


# ── Cargar follow-ups SDR desde Engram ───────────────────────────────────────
try:
    from sdr_leads import get_followups_for_brief_sync as _get_followups_sync
    _SDR_LEADS_AVAILABLE = True
except ImportError:
    _get_followups_sync = None  # type: ignore[assignment]
    _SDR_LEADS_AVAILABLE = False


def load_followup_leads() -> "str | None":
    """Load SDR follow-up leads from Engram for brief injection. Returns formatted string or None."""
    if not _SDR_LEADS_AVAILABLE:
        return None
    try:
        return _get_followups_sync()
    except Exception as exc:
        log.warning("Could not load follow-ups from Engram: %s", exc)
        return None


# ── Cargar posts CMO pendientes desde Engram ──────────────────────────────────
try:
    from cmo_content import get_pending_drafts_for_brief_sync as _get_posts_sync
    _CMO_CONTENT_AVAILABLE = True
except ImportError:
    _get_posts_sync = None  # type: ignore[assignment]
    _CMO_CONTENT_AVAILABLE = False


def load_pending_posts() -> "str | None":
    """Load CMO pending posts (estado=listo) from Engram for brief injection."""
    if not _CMO_CONTENT_AVAILABLE:
        return None
    try:
        result = _get_posts_sync()
        # Return None if no pending posts (avoids adding empty section to brief)
        if result == "No hay posts listos para publicar.":
            return None
        return result
    except Exception as exc:
        log.warning("Could not load pending posts from Engram: %s", exc)
        return None


# ── Cargar oportunidades AE calientes desde Engram ───────────────────────────
try:
    from ae_deals import get_hot_deals_for_brief_sync as _get_hot_deals_sync
    _AE_DEALS_AVAILABLE = True
except ImportError:
    _get_hot_deals_sync = None  # type: ignore[assignment]
    _AE_DEALS_AVAILABLE = False


def load_hot_deals() -> "str | None":
    """Load AE hot deals (demo/propuesta/negociacion) from Engram for brief injection."""
    if not _AE_DEALS_AVAILABLE:
        return None
    try:
        result = _get_hot_deals_sync()
        if result == "No hay oportunidades AE calientes.":
            return None
        return result
    except Exception as exc:
        log.warning("Could not load AE hot deals from Engram: %s", exc)
        return None


# ── Cargar facturas pendientes CFO desde Engram ───────────────────────────────
try:
    from cfo_invoices import get_pending_summary_for_brief_sync as _get_cfo_brief_sync
    _CFO_AVAILABLE = True
except ImportError:
    _get_cfo_brief_sync = None  # type: ignore[assignment]
    _CFO_AVAILABLE = False


def load_cfo_brief() -> "str | None":
    """Load CFO pending invoices from Engram for brief injection. Returns None if no pending invoices."""
    if not _CFO_AVAILABLE:
        return None
    try:
        result = _get_cfo_brief_sync()
        if result == "No hay facturas pendientes.":
            return None
        return result
    except Exception as exc:
        log.warning("Could not load CFO invoices from Engram: %s", exc)
        return None


# ── Reporte semanal (lunes) ───────────────────────────────────────────────────
def build_weekly_report() -> "str | None":
    """
    Genera un reporte semanal de negocio. Solo se llama los lunes.
    Agrega datos de CS (MRR), AE (pipeline), SDR (leads nuevos) y CFO (cobros).
    """
    from datetime import timedelta, timezone
    from airtable_client import get_client, TABLE_LEADS, TABLE_DEALS, TABLE_CLIENTS, TABLE_INVOICES

    today = datetime.now(timezone.utc).date()
    week_ago = (today - timedelta(days=7)).isoformat()
    at = get_client()
    lines = ["📊 *Reporte semanal Duendes*\n"]

    # MRR — clientes activos
    try:
        records = at.list_records_sync(TABLE_CLIENTS, filter_formula="{Estado}='Activo'")
        mrr_total = sum(
            float(str(r.get("fields", {}).get("Valor contrato") or 0)
                  .replace("€", "").replace(",", ".").strip() or 0)
            for r in records
        )
        n_clientes = len(records)
        lines.append(f"💶 *MRR:* {mrr_total:.0f}€/mes ({n_clientes} clientes activos)")
    except Exception as exc:
        log.warning("weekly: CS error: %s", exc)

    # Leads nuevos esta semana
    try:
        all_leads = at.list_records_sync(TABLE_LEADS)
        new_leads = [r for r in all_leads if r.get("createdTime", "")[:10] >= week_ago]
        lines.append(f"🎯 *Leads nuevos (7 días):* {len(new_leads)}")
    except Exception as exc:
        log.warning("weekly: SDR error: %s", exc)

    # Pipeline AE
    try:
        deals = at.list_records_sync(TABLE_DEALS)
        pipeline: dict[str, int] = {}
        for r in deals:
            estado = r.get("fields", {}).get("Estado", "")
            if estado in ("Demo", "Propuesta", "Negociacion"):
                pipeline[estado] = pipeline.get(estado, 0) + 1
        if pipeline:
            pipeline_str = " · ".join(f"{k}: {v}" for k, v in pipeline.items())
            lines.append(f"💼 *Pipeline activo:* {pipeline_str}")
        else:
            lines.append("💼 *Pipeline activo:* sin deals en curso")
    except Exception as exc:
        log.warning("weekly: AE error: %s", exc)

    # Facturas pendientes de cobro
    try:
        inv_records = at.list_records_sync(TABLE_INVOICES)
        pendientes = [
            r for r in inv_records
            if r.get("fields", {}).get("Estado", "").lower() in ("pendiente", "vencida")
        ]
        total_pendiente = sum(
            float(str(r.get("fields", {}).get("Importe") or 0)
                  .replace("€", "").replace(",", ".").strip() or 0)
            for r in pendientes
        )
        vencidas = sum(1 for r in pendientes if r.get("fields", {}).get("Estado", "").lower() == "vencida")
        cobro_str = f"{total_pendiente:.0f}€ pendiente"
        if vencidas:
            cobro_str += f" · ⚠️ {vencidas} vencida(s)"
        lines.append(f"💰 *Cobros:* {cobro_str}")
    except Exception as exc:
        log.warning("weekly: CFO error: %s", exc)

    lines.append(f"\n_Semana del {week_ago} al {today.isoformat()}_")
    return "\n".join(lines)


# ── Cargar check-ins CS pendientes desde Engram ───────────────────────────────
try:
    from cs_clients import get_checkins_for_brief_sync as _get_cs_brief_sync
    _CS_AVAILABLE = True
except ImportError:
    _get_cs_brief_sync = None  # type: ignore[assignment]
    _CS_AVAILABLE = False


def load_cs_brief() -> "str | None":
    """Load clients needing check-in from Engram for brief injection. Returns None if all ok."""
    if not _CS_AVAILABLE:
        return None
    try:
        return _get_cs_brief_sync()
    except Exception as exc:
        log.warning("Could not load CS check-ins from Engram: %s", exc)
        return None


# ── Generar brief con Claude ─────────────────────────────────────────────────
def generate_brief(
    context: str,
    fecha: str,
    tasks: "str | None" = None,
    followups: "str | None" = None,
    posts: "str | None" = None,
    deals: "str | None" = None,
    cfo: "str | None" = None,
    cs: "str | None" = None,
) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system = f"""Eres el AIOS de Duendes — el sistema de inteligencia operativa de Oscar Grana,
solo founder de Duendes (agencia de agentes de voz con IA para España).

Cada mañana generas un brief diario conciso y accionable que Oscar lee en Telegram.
El brief es directo, sin florituras, en español de España.

Contexto del negocio:
{context}"""

    if tasks is not None and tasks != "No hay tareas pendientes.":
        task_section = (
            f"📋 **Tareas prioritarias**\n"
            f"Oscar tiene estas tareas pendientes reales. Comenta sobre ellas, "
            f"prioriza, y sugiere cómo abordarlas hoy:\n{tasks}"
        )
    elif tasks == "No hay tareas pendientes.":
        task_section = (
            "📋 **Tareas prioritarias**\n"
            "No hay tareas pendientes registradas. Sugiere 3 acciones concretas "
            "orientadas a conseguir los primeros clientes según la estrategia."
        )
    else:
        task_section = (
            "📋 **Tareas prioritarias**\n"
            "[3 acciones concretas y accionables para hoy, orientadas a conseguir los primeros clientes]\n"
            "_(Nota: tareas desde IA — Engram no disponible)_"
        )

    # Build optional follow-up section for SDR
    if followups is not None and followups != "No hay follow-ups pendientes.":
        followup_section = f"\n\n🔔 **Follow-ups SDR**\n{followups}"
    else:
        followup_section = ""

    # Build optional CMO posts section
    if posts is not None:
        posts_section = f"\n\n✍️ **Posts pendientes de publicar**\n{posts}"
    else:
        posts_section = ""

    # Build optional AE deals section
    if deals is not None:
        deals_section = f"\n\n💼 **Pipeline de cierre (AE)**\n{deals}"
    else:
        deals_section = ""

    # Build optional CFO invoices section
    if cfo is not None:
        cfo_section = f"\n\n💰 **Facturas pendientes**\n{cfo}"
    else:
        cfo_section = ""

    # Build optional CS check-in section
    if cs is not None:
        cs_section = f"\n\n🤝 **Clientes — check-in pendiente**\n{cs}"
    else:
        cs_section = ""

    prompt = f"""Hoy es {fecha}.

Genera el brief diario de Duendes. Estructura exacta:

📅 **Brief Duendes — {fecha}**

🎯 **Foco del día**
[1-2 frases sobre en qué debe concentrarse Oscar hoy según la estrategia actual]

{task_section}{followup_section}{posts_section}{deals_section}{cfo_section}{cs_section}

💡 **Idea del día**
[1 idea de contenido para LinkedIn, prospección, o proceso interno — algo pequeño pero útil]

⚡ **Recordatorio estratégico**
[1 frase que recuerde a Oscar el objetivo principal: primeros 3-5 clientes de pago]

---
_Duendes AIOS · {datetime.now().strftime("%H:%M")}_"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


# ── Enviar a Telegram ────────────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": OSCAR_TELEGRAM_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        r = httpx.post(url, json=payload, timeout=15)
        r.raise_for_status()
        log.info("Brief enviado a Telegram correctamente")
        return True
    except Exception as e:
        log.error(f"Error enviando a Telegram: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    log.info("Generando brief diario...")

    fecha = fecha_hoy()
    context = load_context()

    if not context:
        log.error("No se pudo cargar el contexto")
        sys.exit(1)

    tasks = load_active_tasks()
    if tasks:
        log.info("Tareas cargadas desde Engram (%d chars)", len(tasks))
    else:
        log.info("Sin tareas de Engram — usando sección genérica")

    followups = load_followup_leads()
    if followups and followups != "No hay follow-ups pendientes.":
        log.info("Follow-ups SDR cargados desde Engram (%d chars)", len(followups))
    else:
        log.info("Sin follow-ups SDR pendientes")

    posts = load_pending_posts()
    if posts:
        log.info("Posts CMO pendientes cargados desde Engram (%d chars)", len(posts))
    else:
        log.info("Sin posts CMO listos para publicar")

    deals = load_hot_deals()
    if deals:
        log.info("Deals AE calientes cargados desde Engram (%d chars)", len(deals))
    else:
        log.info("Sin oportunidades AE calientes")

    cfo = load_cfo_brief()
    if cfo:
        log.info("Facturas CFO pendientes cargadas desde Engram (%d chars)", len(cfo))
    else:
        log.info("Sin facturas CFO pendientes")

    cs = load_cs_brief()
    if cs:
        log.info("Check-ins CS pendientes cargados desde Engram (%d chars)", len(cs))
    else:
        log.info("Sin check-ins CS pendientes")

    brief = generate_brief(
        context,
        fecha,
        tasks=tasks,
        followups=followups,
        posts=posts,
        deals=deals,
        cfo=cfo,
        cs=cs,
    )
    log.info(f"Brief generado ({len(brief)} chars)")

    success = send_telegram(brief)
    if not success:
        sys.exit(1)
    if _SLACK_AVAILABLE:
        send_brief(brief)

    # Reporte semanal — solo los lunes
    if datetime.now().weekday() == 0:
        log.info("Lunes — generando reporte semanal...")
        try:
            weekly = build_weekly_report()
            if weekly:
                send_telegram(weekly)
                log.info("Reporte semanal enviado")
                if _SLACK_AVAILABLE:
                    send_weekly_report(weekly)
        except Exception as exc:
            log.error("Error en reporte semanal: %s", exc)

    log.info("Brief diario completado")


if __name__ == "__main__":
    main()
