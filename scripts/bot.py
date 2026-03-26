"""
Duendes AIOS — Telegram Bot
Bot: @DuendesCRM_bot
Runs in long-polling mode locally on Mac. Only accepts messages from OSCAR_TELEGRAM_ID.
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path

import langfuse_init  # noqa: F401 — instrumenta Anthropic automáticamente

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    from instantly_client import (
        add_lead_to_campaign,
        format_campaigns,
        format_lead_pushed,
        get_campaign_analytics,
        list_campaigns,
    )
    _INSTANTLY_AVAILABLE = True
except ImportError as _inst_err:
    _INSTANTLY_AVAILABLE = False
    logging.getLogger("duendes-bot").warning("instantly_client not available: %s", _inst_err)

try:
    from coo_tasks import (
        EngramConnectionError,
        add_task,
        complete_task,
        detect_task_intent,
        format_task_added,
        format_task_completed,
        format_task_list,
        get_pending_tasks,
        get_pending_for_brief_sync as _coo_brief_sync,
        list_tasks,
        parse_priority_and_category,
    )
    _COO_TASKS_AVAILABLE = True
except ImportError as _coo_import_err:
    _COO_TASKS_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "coo_tasks module not available: %s", _coo_import_err
    )

try:
    from sdr_leads import (
        EngramConnectionError as SdrEngramConnectionError,
        add_lead,
        list_leads,
        get_lead,
        update_lead_estado,
        add_lead_nota,
        get_followup_leads,
        generate_cold_email,
        detect_lead_intent,
        format_lead_list,
        format_lead_detail,
        format_lead_added,
        format_lead_estado_updated,
        format_followup_list,
        get_followups_for_brief_sync as _sdr_brief_sync,
        VALID_ESTADOS as SDR_VALID_ESTADOS,
        VALID_SECTORS as SDR_VALID_SECTORS,
    )
    _SDR_LEADS_AVAILABLE = True
except ImportError as _sdr_import_err:
    _SDR_LEADS_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "sdr_leads module not available: %s", _sdr_import_err
    )

try:
    from sdr_researcher import research_leads, format_research_summary, VALID_SECTORS as RESEARCHER_VALID_SECTORS
    _SDR_RESEARCHER_AVAILABLE = True
except ImportError as _err:
    _SDR_RESEARCHER_AVAILABLE = False
    logging.getLogger("duendes-bot").warning("sdr_researcher not available: %s", _err)

try:
    from sdr_qualifier import (
        qualify_leads_batch,
        qualify_lead,
        format_qualification_report,
        format_single_qualification,
    )
    _SDR_QUALIFIER_AVAILABLE = True
except ImportError as _qualifier_err:
    _SDR_QUALIFIER_AVAILABLE = False
    logging.getLogger("duendes-bot").warning("sdr_qualifier not available: %s", _qualifier_err)

try:
    from cmo_content import (
        EngramConnectionError as CmoEngramConnectionError,
        add_draft,
        list_drafts,
        update_draft_estado,
        generate_post,
        generate_ideas,
        detect_content_intent,
        format_draft_list,
        format_draft_added,
        format_draft_estado_updated,
        get_pending_drafts_for_brief_sync as _cmo_brief_sync,
        VALID_ESTADOS as CMO_VALID_ESTADOS,
        VALID_SECTORS as CMO_VALID_SECTORS,
    )
    _CMO_CONTENT_AVAILABLE = True
except ImportError as _cmo_import_err:
    _CMO_CONTENT_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "cmo_content module not available: %s", _cmo_import_err
    )

try:
    from ae_deals import (
        EngramConnectionError as AeEngramConnectionError,
        EngramDataError as AeEngramDataError,
        add_deal,
        list_deals,
        get_deal,
        update_deal_estado,
        update_deal_nota,
        save_propuesta,
        add_objecion,
        generate_propuesta,
        detect_deal_intent,
        format_deal_list,
        format_deal_added,
        format_deal_estado_updated,
        format_deal_detail,
        get_hot_deals_for_brief_sync as _ae_brief_sync,
        VALID_ESTADOS as AE_VALID_ESTADOS,
    )
    _AE_DEALS_AVAILABLE = True
except ImportError as _ae_import_err:
    _AE_DEALS_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "ae_deals module not available: %s", _ae_import_err
    )

try:
    from cfo_invoices import (
        EngramConnectionError as CfoEngramConnectionError,
        EngramDataError as CfoEngramDataError,
        add_invoice as _add_invoice,
        get_invoices as _get_invoices,
        list_invoices as _list_invoices,
        mark_paid as _mark_paid,
        get_mrr as _get_mrr,
        check_overdue as _check_overdue,
        get_pending_summary_for_brief_sync as _cfo_brief_sync,
        _CFO_AVAILABLE,
    )
    _CFO_AVAILABLE = True
except ImportError as _cfo_import_err:
    _CFO_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "cfo_invoices module not available: %s", _cfo_import_err
    )

try:
    from cs_clients import (
        add_client as _add_client,
        get_clients as _get_clients,
        list_clients as _list_clients,
        log_checkin as _log_checkin,
        set_churn_risk as _set_churn_risk,
        get_churn_report as _get_churn_report,
        get_total_mrr as _get_total_mrr,
        get_checkins_for_brief_sync as _cs_brief_sync,
        detect_cs_intent,
        format_client_added,
        format_checkin_logged,
        format_churn_risk_updated,
        EngramConnectionError as CsEngramConnectionError,
        EngramDataError as CsEngramDataError,
        VALID_SECTORES as CS_VALID_SECTORES,
        VALID_CHURN_RISK as CS_VALID_CHURN_RISK,
    )
    _CS_AVAILABLE = True
except ImportError as _cs_import_err:
    _CS_AVAILABLE = False
    logging.getLogger("duendes-bot").warning(
        "cs_clients module not available: %s", _cs_import_err
    )

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Load .env from project root
load_dotenv(PROJECT_DIR / ".env")

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OSCAR_TELEGRAM_ID: int = int(os.environ["OSCAR_TELEGRAM_ID"])

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("duendes-bot")

# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# SDR lead cache — maps display number → Lead (refreshed on every /leads call)
# Airtable record IDs are opaque strings; bot uses sequential display numbers.
# ---------------------------------------------------------------------------

_sdr_lead_cache: "list[Any]" = []  # list[Lead] — typed as Any to avoid import cycle


def _get_lead_by_display_id(n: int) -> "Any | None":
    """Return the Lead at display position n (1-based). None if out of range."""
    if 1 <= n <= len(_sdr_lead_cache):
        return _sdr_lead_cache[n - 1]
    return None


def _update_sdr_cache(leads: list) -> None:
    global _sdr_lead_cache
    _sdr_lead_cache = leads


# CFO invoice cache
_cfo_invoice_cache: "list[Any]" = []


def _get_invoice_by_display_id(n: int) -> "Any | None":
    if 1 <= n <= len(_cfo_invoice_cache):
        return _cfo_invoice_cache[n - 1]
    return None


# CS client cache
_cs_client_cache: "list[Any]" = []


def _get_client_by_display_id(n: int) -> "Any | None":
    if 1 <= n <= len(_cs_client_cache):
        return _cs_client_cache[n - 1]
    return None


def _update_cs_cache(clients: list) -> None:
    global _cs_client_cache
    _cs_client_cache = clients


# COO task cache
_coo_task_cache: "list[Any]" = []


def _get_task_by_display_id(n: int) -> "Any | None":
    if 1 <= n <= len(_coo_task_cache):
        return _coo_task_cache[n - 1]
    return None


def _update_task_cache(tasks: list) -> None:
    global _coo_task_cache
    _coo_task_cache = tasks


# AE deal cache
_ae_deal_cache: "list[Any]" = []


def _get_deal_by_display_id(n: int) -> "Any | None":
    if 1 <= n <= len(_ae_deal_cache):
        return _ae_deal_cache[n - 1]
    return None


def _update_deal_cache(deals: list) -> None:
    global _ae_deal_cache
    _ae_deal_cache = deals

# ---------------------------------------------------------------------------
# Context OS loader
# ---------------------------------------------------------------------------

_context_os: str = ""
_context_summary: list[str] = []


def load_context() -> str:
    """Load all .md files from the Context OS and return them as a single string."""
    global _context_os, _context_summary
    parts: list[str] = []
    loaded: list[str] = []

    def read_md_files(directory: Path, label: str) -> None:
        if not directory.exists():
            return
        for md_file in sorted(directory.glob("*.md")):
            content = md_file.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                parts.append(f"## [{label}] {md_file.name}\n\n{content}")
                loaded.append(f"{label}/{md_file.name}")

    # CLAUDE.md at project root
    claude_md = PROJECT_DIR / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8", errors="replace").strip()
        if content:
            parts.append(f"## [root] CLAUDE.md\n\n{content}")
            loaded.append("root/CLAUDE.md")

    read_md_files(PROJECT_DIR / "context", "context")
    read_md_files(PROJECT_DIR / "equipo", "equipo")

    # Orchestrator CLAUDE.md (routing instructions for ask_claude)
    orch_md = PROJECT_DIR / "modulos" / "orchestrator" / "CLAUDE.md"
    if orch_md.exists():
        content = orch_md.read_text(encoding="utf-8", errors="replace").strip()
        if content:
            parts.append(f"## [orchestrator] CLAUDE.md\n\n{content}")
            loaded.append("orchestrator/CLAUDE.md")

    _context_summary = loaded
    _context_os = "\n\n---\n\n".join(parts)

    logger.info("Context OS loaded: %d files — %d chars", len(loaded), len(_context_os))
    return _context_os


# ---------------------------------------------------------------------------
# Module contexts (department CLAUDE.md files as expert system prompts)
# ---------------------------------------------------------------------------

_module_contexts: dict[str, str] = {}


def load_module_contexts() -> None:
    """Load each department's CLAUDE.md into _module_contexts for use as system prompts."""
    global _module_contexts
    for module in ("sdr", "cmo", "ae", "coo", "cfo", "cs"):
        md_file = PROJECT_DIR / "modulos" / module / "CLAUDE.md"
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                _module_contexts[module] = content
    logger.info("Module contexts loaded: %s", list(_module_contexts.keys()))


# Load at startup
load_context()
load_module_contexts()

# ---------------------------------------------------------------------------
# Conversation history (in-memory, per user)
# ---------------------------------------------------------------------------

MAX_HISTORY = 10          # messages kept (each message = one dict)
SESSION_TTL = 2 * 60 * 60  # 2 hours in seconds

_history: list[dict] = []
_last_activity: float = time.time()


def _maybe_expire_history() -> None:
    global _history, _last_activity
    if time.time() - _last_activity > SESSION_TTL:
        logger.info("Session expired — clearing history")
        _history = []
    _last_activity = time.time()


def _add_to_history(role: str, content: str) -> None:
    _maybe_expire_history()
    _history.append({"role": role, "content": content})
    # Keep only the last MAX_HISTORY messages (pairs)
    if len(_history) > MAX_HISTORY * 2:
        _history[:] = _history[-(MAX_HISTORY * 2):]


def _reset_history() -> None:
    global _history, _last_activity
    _history = []
    _last_activity = time.time()
    logger.info("Conversation history reset")


# ---------------------------------------------------------------------------
# Whitelist guard
# ---------------------------------------------------------------------------

def is_oscar(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == OSCAR_TELEGRAM_ID


async def reject_unauthorized(update: Update) -> None:
    user = update.effective_user
    logger.warning(
        "Unauthorized access attempt — user_id=%s username=%s",
        user.id if user else "unknown",
        user.username if user else "unknown",
    )
    if update.message:
        await update.message.reply_text("No autorizado.")


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

async def ask_claude(user_message: str, extra_system: str = "") -> str:
    _add_to_history("user", user_message)

    system = _context_os or "Eres el AIOS de Duendes, un asistente de negocio."
    if extra_system:
        system = f"{system}\n\n---\n\n{extra_system}"

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            messages=_history,
        )
        answer = response.content[0].text
        _add_to_history("assistant", answer)
        return answer
    except Exception as exc:
        if _history and _history[-1]["role"] == "user":
            _history.pop()
        logger.error("Claude API error: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Super Orchestrator — AI-powered routing
# ---------------------------------------------------------------------------

_ORCHESTRATOR_SYSTEM = """Eres el router del AIOS de Duendes. Clasifica el mensaje de Oscar en el departamento correcto.

Responde ÚNICAMENTE con JSON válido, sin texto adicional:
{"department": "X", "action": "Y"}

Departamentos disponibles:
- "coo"    → tareas, procesos, organización, agenda, recordatorios
- "sdr"    → leads, prospectos, búsqueda de clientes, outreach, contacto frío
- "cmo"    → posts, LinkedIn, contenido, copywriting, ideas de marketing
- "ae"     → deals, propuestas, demos, negociación, pipeline de ventas, cierre
- "cfo"    → facturas, cobros, MRR, finanzas, pagos, ingresos
- "cs"     → clientes activos, check-in, churn, onboarding, retención
- "direct" → estrategia, preguntas generales, contexto, conversación

"action": describe en máximo 6 palabras qué quiere Oscar."""


async def _route_message(user_text: str) -> tuple[str, str]:
    """
    Uses Claude Haiku to classify a message into a department.
    Returns (department, action). Fast and cheap — routing only.
    """
    import json as _json
    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system=_ORCHESTRATOR_SYSTEM,
            messages=[{"role": "user", "content": user_text}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        result = _json.loads(raw)
        dept = result.get("department", "direct")
        action = result.get("action", "")
        logger.info("Orchestrator → dept=%s action=%r", dept, action)
        return dept, action
    except Exception as exc:
        logger.warning("Orchestrator routing failed: %s — falling back to direct", exc)
        return "direct", ""


# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------

async def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as audio_file:
        transcript = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    return transcript.text.strip()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    _reset_history()

    files_loaded = len(_context_summary)
    await update.message.reply_text(
        f"Hola Oscar. Soy el AIOS de Duendes.\n\n"
        f"Context OS cargado: {files_loaded} archivos.\n"
        f"Historial de conversación reiniciado.\n\n"
        f"Puedes escribirme o mandarme un audio."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _context_summary:
        status_text = "Context OS: no cargado."
    else:
        files_list = "\n".join(f"  • {f}" for f in _context_summary)
        status_text = (
            f"Context OS cargado ({len(_context_summary)} archivos, "
            f"{len(_context_os):,} chars):\n{files_list}"
        )

    history_info = f"Historial activo: {len(_history) // 2} intercambios."
    await update.message.reply_text(f"{status_text}\n\n{history_info}")


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    await update.message.reply_text("Recargando Context OS...")
    load_context()
    await update.message.reply_text(
        f"Context OS recargado: {len(_context_summary)} archivos, {len(_context_os):,} chars."
    )


# ---------------------------------------------------------------------------
# Task command handlers (COO module)
# ---------------------------------------------------------------------------

async def _engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a las tareas ahora. Engram no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def handle_task_intent(intent: str, match_data: dict, update: Update) -> bool:
    """
    Dispatch to the right coo_tasks function based on detected intent.
    Returns True if handled (caller should return early), False otherwise.
    """
    if not _COO_TASKS_AVAILABLE:
        return False

    try:
        if intent == "list":
            tasks = await list_tasks(status="pending")
            _update_task_cache(tasks)
            for i, t in enumerate(tasks, 1):
                t._display_id = i
            await update.message.reply_text(
                format_task_list(tasks), parse_mode="Markdown"
            )
            return True

        if intent == "pending":
            tasks = await get_pending_tasks()
            _update_task_cache(tasks)
            for i, t in enumerate(tasks, 1):
                t._display_id = i
            await update.message.reply_text(
                format_task_list(tasks, title="Tareas pendientes"), parse_mode="Markdown"
            )
            return True

        if intent == "add":
            title = match_data.get("title", "").strip()
            if not title:
                return False
            clean_title, priority, category = parse_priority_and_category(title)
            task = await add_task(clean_title, priority=priority, category=category)
            await update.message.reply_text(format_task_added(task))
            return True

        if intent == "complete":
            task_n = match_data.get("task_display_n")
            if task_n is None:
                return False
            task_obj = _get_task_by_display_id(task_n)
            if task_obj is None:
                await update.message.reply_text(
                    f"Tarea #{task_n} no encontrada. Ejecuta /tareas primero."
                )
                return True
            task = await complete_task(task_obj.id)
            if task is None:
                await update.message.reply_text(f"No pude completar la tarea #{task_n}.")
            else:
                await update.message.reply_text(format_task_completed(task))
            return True

    except EngramConnectionError as exc:
        logger.error("EngramConnectionError in task intent handler: %s", exc)
        await _engram_error_reply(update)
        return True
    except Exception as exc:
        logger.error("Unexpected error in task intent handler: %s", exc)

    return False


async def cmd_tareas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _COO_TASKS_AVAILABLE:
        await update.message.reply_text("El módulo de tareas no está disponible.")
        return

    category_filter = context.args[0].lower() if context.args else None

    try:
        tasks = await list_tasks(status="pending", category=category_filter)
        _update_task_cache(tasks)
        for i, t in enumerate(tasks, 1):
            t._display_id = i
        await update.message.reply_text(
            format_task_list(tasks), parse_mode="Markdown"
        )
    except EngramConnectionError as exc:
        logger.error("Airtable unreachable in /tareas: %s", exc)
        await update.message.reply_text("Airtable no responde. Intenta de nuevo.")


async def cmd_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _COO_TASKS_AVAILABLE:
        await update.message.reply_text("El módulo de tareas no está disponible.")
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /nueva <descripcion>\n"
            "Ejemplo: /nueva alta:Llamar a Clinica Garcia #sales"
        )
        return

    raw_title = " ".join(context.args)
    clean_title, priority, category = parse_priority_and_category(raw_title)

    try:
        task = await add_task(clean_title, priority=priority, category=category)
        await update.message.reply_text(format_task_added(task))
    except EngramConnectionError as exc:
        logger.error("Engram unreachable in /nueva: %s", exc)
        await _engram_error_reply(update)


async def cmd_hecho(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _COO_TASKS_AVAILABLE:
        await update.message.reply_text("El módulo de tareas no está disponible.")
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /hecho <numero>\nEjemplo: /hecho 3"
        )
        return

    arg = context.args[0]
    try:
        task_n = int(arg)
    except ValueError:
        await update.message.reply_text(
            "El número de tarea debe ser un entero (de la lista /tareas). Ejemplo: /hecho 3"
        )
        return

    task_obj = _get_task_by_display_id(task_n)
    if task_obj is None:
        # Try refreshing cache
        try:
            fresh = await list_tasks(status="pending")
            _update_task_cache(fresh)
            for i, t in enumerate(fresh, 1):
                t._display_id = i
            task_obj = _get_task_by_display_id(task_n)
        except Exception:
            pass
    if task_obj is None:
        await update.message.reply_text(
            f"Tarea #{task_n} no encontrada. Ejecuta /tareas primero."
        )
        return

    try:
        task = await complete_task(task_obj.id)
        if task is None:
            await update.message.reply_text(f"No pude completar la tarea #{task_n}.")
        else:
            await update.message.reply_text(format_task_completed(task))
    except EngramConnectionError as exc:
        logger.error("Airtable unreachable in /hecho: %s", exc)
        await update.message.reply_text("Airtable no responde. Intenta de nuevo.")


async def cmd_pendiente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _COO_TASKS_AVAILABLE:
        await update.message.reply_text("El módulo de tareas no está disponible.")
        return

    try:
        tasks = await get_pending_tasks()
        if not tasks:
            await update.message.reply_text("No hay tareas pendientes.")
            return

        from datetime import datetime as _dt
        today = _dt.now().date().isoformat()

        overdue_today = [
            t for t in tasks if t.due_date and t.due_date <= today
        ]
        rest = [t for t in tasks if not (t.due_date and t.due_date <= today)]

        parts: list[str] = []
        if overdue_today:
            parts.append(
                "🚨 *Vence hoy / Atrasadas*\n"
                + "\n".join(
                    f"  #{t.id} {t.title} [{t.category}]"
                    + (f" _(vence: {t.due_date})_" if t.due_date else "")
                    for t in overdue_today
                )
            )
        if rest:
            parts.append(format_task_list(rest, title="Otras pendientes"))
        elif not overdue_today:
            parts.append("Ninguna tarea vence hoy.")

        await update.message.reply_text("\n\n".join(parts), parse_mode="Markdown")
    except EngramConnectionError as exc:
        logger.error("Engram unreachable in /pendiente: %s", exc)
        await _engram_error_reply(update)


# ---------------------------------------------------------------------------
# SDR Lead Management handlers
# ---------------------------------------------------------------------------


async def _sdr_unavailable_reply(update: Update) -> None:
    await update.message.reply_text("El módulo de leads no está disponible.")


async def _sdr_engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a los leads ahora. Airtable no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def handle_lead_intent(intent: str, data: dict, update: Update) -> bool:
    """
    Dispatch to the right sdr_leads function based on detected intent.
    Returns True if handled (caller should return early), False otherwise.
    """
    if not _SDR_LEADS_AVAILABLE:
        return False

    try:
        if intent == "list":
            leads = await list_leads()
            _update_sdr_cache(leads)
            await update.message.reply_text(
                format_lead_list(leads), parse_mode="Markdown"
            )
            return True

        if intent == "followup":
            leads = await get_followup_leads()
            await update.message.reply_text(
                format_followup_list(leads), parse_mode="Markdown"
            )
            return True

        if intent == "add":
            nombre = data.get("nombre", "").strip()
            sector = data.get("sector", "").strip()
            ciudad = data.get("ciudad", "").strip()
            if not nombre or not sector or not ciudad:
                return False
            lead = await add_lead(nombre, sector, ciudad)
            await update.message.reply_text(format_lead_added(lead))
            return True

    except SdrEngramConnectionError as exc:
        logger.error("SdrEngramConnectionError in lead intent handler: %s", exc)
        await _sdr_engram_error_reply(update)
        return True
    except Exception as exc:
        logger.error("Unexpected error in lead intent handler: %s", exc)

    return False


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    estado_filter = None
    sector_filter = None
    if context.args:
        arg = context.args[0].lower()
        if arg in SDR_VALID_ESTADOS:
            estado_filter = arg
        elif arg in SDR_VALID_SECTORS:
            sector_filter = arg

    try:
        leads = await list_leads(estado=estado_filter, sector=sector_filter)
        _update_sdr_cache(leads)
        await update.message.reply_text(
            format_lead_list(leads), parse_mode="Markdown"
        )
    except SdrEngramConnectionError as exc:
        logger.error("Airtable unreachable in /leads: %s", exc)
        await _sdr_engram_error_reply(update)


async def cmd_sdr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sdr buscar <sector> <ciudad>
    Runs Apify Google Maps Scraper, qualifies leads, saves to Airtable.
    """
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_RESEARCHER_AVAILABLE:
        await update.message.reply_text("El módulo de investigación SDR no está disponible.")
        return

    if not context.args or len(context.args) < 3 or context.args[0].lower() != "buscar":
        sectores = ", ".join(sorted(RESEARCHER_VALID_SECTORS))
        await update.message.reply_text(
            "Uso: /sdr buscar <sector> <ciudad>\n"
            f"Ejemplo: /sdr buscar fisio Madrid\n"
            f"Sectores: {sectores}"
        )
        return

    sector = context.args[1].lower()
    ciudad = " ".join(context.args[2:])

    if sector not in RESEARCHER_VALID_SECTORS:
        sectores = ", ".join(sorted(RESEARCHER_VALID_SECTORS))
        await update.message.reply_text(
            f"Sector '{sector}' no reconocido.\nOpciones: {sectores}"
        )
        return

    await update.message.reply_text(
        f"🔍 Buscando {sector} en {ciudad}... (puede tardar 2-3 minutos)"
    )

    try:
        result = await research_leads(sector, ciudad)
        summary = format_research_summary(result, sector, ciudad)
        await update.message.reply_text(summary, parse_mode="Markdown")
    except Exception as exc:
        logger.error("Error in /sdr buscar: %s", exc)
        await update.message.reply_text(f"Error en la búsqueda: {exc}")


async def cmd_lead(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso:\n"
            "  /lead <nombre>, <sector>, <ciudad>  — añadir lead\n"
            "  /lead <id>  — ver detalle\n"
            "Ejemplo: /lead Clínica Dental Sol, dental, Madrid"
        )
        return

    raw = " ".join(context.args)

    # If single integer arg → view detail by display number
    if raw.strip().isdigit():
        display_n = int(raw.strip())
        lead = _get_lead_by_display_id(display_n)
        if lead is None:
            await update.message.reply_text(
                f"Lead #{display_n} no encontrado en la lista actual. "
                "Ejecuta /leads primero para actualizar la lista."
            )
            return
        await update.message.reply_text(
            format_lead_detail(lead, display_id=display_n), parse_mode="Markdown"
        )
        return

    # Otherwise → parse as nombre, sector, ciudad
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 3:
        await update.message.reply_text(
            "Uso: /lead <nombre>, <sector>, <ciudad>\n"
            "Ejemplo: /lead Clínica Dental Sol, dental, Madrid"
        )
        return

    nombre = parts[0]
    sector = parts[1]
    ciudad = parts[2]
    email = parts[3] if len(parts) > 3 else ""

    try:
        lead = await add_lead(nombre, sector, ciudad, email=email)
        await update.message.reply_text(format_lead_added(lead))
    except SdrEngramConnectionError as exc:
        logger.error("Engram unreachable in /lead add: %s", exc)
        await _sdr_engram_error_reply(update)


async def cmd_leadstatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /leadstatus <id> <estado>\n"
            "Ejemplo: /leadstatus 3 contactado\n"
            f"Estados válidos: {', '.join(sorted(SDR_VALID_ESTADOS))}"
        )
        return

    try:
        display_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (el de la lista /leads).")
        return

    nuevo_estado = context.args[1].lower()
    if nuevo_estado not in SDR_VALID_ESTADOS:
        await update.message.reply_text(
            f"Estado inválido. Opciones: {', '.join(sorted(SDR_VALID_ESTADOS))}"
        )
        return

    lead = _get_lead_by_display_id(display_n)
    if lead is None:
        await update.message.reply_text(
            f"Lead #{display_n} no encontrado. Ejecuta /leads primero."
        )
        return

    try:
        updated = await update_lead_estado(lead.id, nuevo_estado)
        if updated is None:
            await update.message.reply_text(f"Lead #{display_n} no encontrado en Airtable.")
        else:
            _sdr_lead_cache[display_n - 1] = updated  # keep cache in sync
            await update.message.reply_text(format_lead_estado_updated(updated))
    except SdrEngramConnectionError as exc:
        logger.error("Airtable unreachable in /leadstatus: %s", exc)
        await _sdr_engram_error_reply(update)


async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text("Uso: /email <id>\nEjemplo: /email 3")
        return

    try:
        display_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (el de la lista /leads).")
        return

    lead = _get_lead_by_display_id(display_n)
    if lead is None:
        await update.message.reply_text(
            f"Lead #{display_n} no encontrado. Ejecuta /leads primero."
        )
        return

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        email_text = await generate_cold_email(lead, _context_os, anthropic_client, module_system=_module_contexts.get("sdr", ""))
        await update.message.reply_text(f"Email para {lead.nombre}:\n\n{email_text}")
    except SdrEngramConnectionError as exc:
        logger.error("Airtable unreachable in /email: %s", exc)
        await _sdr_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error generating email for lead #%d: %s", display_n, exc)
        await update.message.reply_text(f"Error generando email: {exc}")


async def cmd_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    try:
        leads = await get_followup_leads()
        await update.message.reply_text(
            format_followup_list(leads), parse_mode="Markdown"
        )
    except SdrEngramConnectionError as exc:
        logger.error("Engram unreachable in /followup: %s", exc)
        await _sdr_engram_error_reply(update)


async def cmd_leadnota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /leadnota <id> <texto>\n"
            "Ejemplo: /leadnota 3 Habló con recepción, interesado"
        )
        return

    try:
        display_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (el de la lista /leads).")
        return

    nota = " ".join(context.args[1:])

    lead = _get_lead_by_display_id(display_n)
    if lead is None:
        await update.message.reply_text(
            f"Lead #{display_n} no encontrado. Ejecuta /leads primero."
        )
        return

    try:
        updated = await add_lead_nota(lead.id, nota)
        if updated is None:
            await update.message.reply_text(f"Lead #{display_n} no encontrado en Airtable.")
        else:
            _sdr_lead_cache[display_n - 1] = updated  # keep cache in sync
            await update.message.reply_text(f"Nota añadida al lead #{display_n}.")
    except SdrEngramConnectionError as exc:
        logger.error("Airtable unreachable in /leadnota: %s", exc)
        await _sdr_engram_error_reply(update)


async def cmd_calificar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /calificar — qualifies all prospecto leads and ranks them by ICP score.
    /calificar <n> — qualifies single lead by display number.
    """
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _SDR_LEADS_AVAILABLE:
        await _sdr_unavailable_reply(update)
        return

    if not _SDR_QUALIFIER_AVAILABLE:
        await update.message.reply_text("El módulo de qualificación no está disponible.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    # Determine mode: single lead or batch
    single_mode = False
    single_n: int | None = None
    if context.args:
        try:
            single_n = int(context.args[0])
            single_mode = True
        except ValueError:
            await update.message.reply_text(
                "Uso:\n"
                "  /calificar       — qualifica todos los leads\n"
                "  /calificar <n>   — qualifica el lead #n de la lista /leads"
            )
            return

    try:
        if single_mode:
            lead = _get_lead_by_display_id(single_n)
            if lead is None:
                await update.message.reply_text(
                    f"Lead #{single_n} no encontrado. Ejecuta /leads primero."
                )
                return
            await update.message.reply_text(f"Analizando lead #{single_n}...")
            result = await qualify_lead(lead, anthropic_client, extra_system=_context_os)
            msg = format_single_qualification(result, display_id=single_n)
            await update.message.reply_text(msg, parse_mode="Markdown")

        else:
            # Batch mode: fetch all prospecto leads
            leads = await list_leads(estado="prospecto")
            if not leads:
                await update.message.reply_text(
                    "No hay leads en estado prospecto para qualificar.\n"
                    "Usa /leads para ver todos los leads."
                )
                return

            await update.message.reply_text(
                f"Qualificando {len(leads)} leads... (puede tardar unos segundos)"
            )
            results = await qualify_leads_batch(leads, anthropic_client, extra_system=_context_os)

            # Save qualifier note to each lead in Airtable (best-effort, non-blocking errors)
            for result in results:
                try:
                    nota = f"[Qualifier] Score {result.score}/10 — {result.accion} — {result.razon}"
                    await add_lead_nota(result.lead_id, nota)
                except Exception as exc:
                    logger.warning(
                        "Could not save qualifier note for lead %s: %s", result.empresa, exc
                    )

            report = format_qualification_report(results)
            await update.message.reply_text(report, parse_mode="Markdown")

    except SdrEngramConnectionError as exc:
        logger.error("Airtable unreachable in /calificar: %s", exc)
        await _sdr_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /calificar: %s", exc)
        await update.message.reply_text(f"Error en la qualificación: {exc}")


# ---------------------------------------------------------------------------
# CMO Content Management handlers
# ---------------------------------------------------------------------------


async def _cmo_unavailable_reply(update: Update) -> None:
    await update.message.reply_text("El módulo de contenido no está disponible.")


async def _cmo_engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a los posts ahora. Engram no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def handle_content_intent(intent: str, data: dict, update: Update) -> bool:
    """
    Dispatch to the right cmo_content function based on detected intent.
    Returns True if handled (caller should return early), False otherwise.
    """
    if not _CMO_CONTENT_AVAILABLE:
        return False

    try:
        if intent == "list_drafts":
            drafts = await list_drafts()
            await update.message.reply_text(
                format_draft_list(drafts), parse_mode="Markdown"
            )
            return True

        if intent == "generate_post":
            sector = data.get("sector", "general")
            await update.message.chat.send_action(ChatAction.TYPING)
            post_text = await generate_post(sector, _context_os, anthropic_client, module_system=_module_contexts.get("cmo", ""))
            await update.message.reply_text(post_text)
            return True

        if intent == "generate_ideas":
            await update.message.chat.send_action(ChatAction.TYPING)
            ideas_text = await generate_ideas(3, _context_os, anthropic_client, module_system=_module_contexts.get("cmo", ""))
            await update.message.reply_text(ideas_text)
            return True

    except CmoEngramConnectionError as exc:
        logger.error("CmoEngramConnectionError in content intent handler: %s", exc)
        await _cmo_engram_error_reply(update)
        return True
    except Exception as exc:
        logger.error("Unexpected error in content intent handler: %s", exc)

    return False


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CMO_CONTENT_AVAILABLE:
        await _cmo_unavailable_reply(update)
        return

    arg = context.args[0].lower() if context.args else "general"

    # /post idea → generate ideas
    if arg == "idea" or arg == "ideas":
        try:
            await update.message.chat.send_action(ChatAction.TYPING)
            ideas_text = await generate_ideas(3, _context_os, anthropic_client, module_system=_module_contexts.get("cmo", ""))
            await update.message.reply_text(ideas_text)
        except CmoEngramConnectionError as exc:
            logger.error("Engram unreachable in /post ideas: %s", exc)
            await _cmo_engram_error_reply(update)
        except Exception as exc:
            logger.error("Error generating ideas: %s", exc)
            await update.message.reply_text(f"Error generando ideas: {exc}")
        return

    # /post [sector] → generate LinkedIn post
    sector = arg if arg in CMO_VALID_SECTORS else "general"

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        post_text = await generate_post(sector, _context_os, anthropic_client, module_system=_module_contexts.get("cmo", ""))
        sector_label = f" [{sector}]" if sector != "general" else ""
        await update.message.reply_text(
            f"Post LinkedIn{sector_label}:\n\n{post_text}"
        )
    except CmoEngramConnectionError as exc:
        logger.error("Engram unreachable in /post: %s", exc)
        await _cmo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error generating post for sector %r: %s", sector, exc)
        await update.message.reply_text(f"Error generando post: {exc}")


async def cmd_postguardar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CMO_CONTENT_AVAILABLE:
        await _cmo_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /postguardar <texto del post>\n"
            "Ejemplo: /postguardar Tu clínica pierde llamadas cada día..."
        )
        return

    cuerpo = " ".join(context.args)

    try:
        draft = await add_draft(cuerpo=cuerpo, tipo="linkedin")
        await update.message.reply_text(format_draft_added(draft))
    except CmoEngramConnectionError as exc:
        logger.error("Engram unreachable in /postguardar: %s", exc)
        await _cmo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error saving draft: %s", exc)
        await update.message.reply_text(f"Error guardando el post: {exc}")


async def cmd_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CMO_CONTENT_AVAILABLE:
        await _cmo_unavailable_reply(update)
        return

    estado_filter = None
    if context.args:
        arg = context.args[0].lower()
        if arg in CMO_VALID_ESTADOS:
            estado_filter = arg

    try:
        drafts = await list_drafts(estado=estado_filter)
        title = f"Posts — {estado_filter}" if estado_filter else "Posts"
        await update.message.reply_text(
            format_draft_list(drafts, title=title), parse_mode="Markdown"
        )
    except CmoEngramConnectionError as exc:
        logger.error("Engram unreachable in /posts: %s", exc)
        await _cmo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error listing drafts: %s", exc)
        await update.message.reply_text(f"Error cargando posts: {exc}")


async def cmd_poststatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CMO_CONTENT_AVAILABLE:
        await _cmo_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /poststatus <id> <estado>\n"
            "Ejemplo: /poststatus 3 listo\n"
            f"Estados válidos: {', '.join(sorted(CMO_VALID_ESTADOS))}"
        )
        return

    try:
        draft_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero.")
        return

    nuevo_estado = context.args[1].lower()
    if nuevo_estado not in CMO_VALID_ESTADOS:
        await update.message.reply_text(
            f"Estado inválido. Opciones: {', '.join(sorted(CMO_VALID_ESTADOS))}"
        )
        return

    try:
        # Load draft to get old estado before update
        from cmo_content import get_draft as _get_draft
        draft_before = await _get_draft(draft_id)
        old_estado = draft_before.estado if draft_before else "borrador"

        draft = await update_draft_estado(draft_id, nuevo_estado)
        if draft is None:
            await update.message.reply_text(f"Post #{draft_id} no encontrado.")
        else:
            await update.message.reply_text(
                format_draft_estado_updated(draft, old_estado)
            )
    except CmoEngramConnectionError as exc:
        logger.error("Engram unreachable in /poststatus: %s", exc)
        await _cmo_engram_error_reply(update)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
    except Exception as exc:
        logger.error("Error updating draft estado: %s", exc)
        await update.message.reply_text(f"Error actualizando el post: {exc}")


# ---------------------------------------------------------------------------
# AE Deal Management handlers
# ---------------------------------------------------------------------------


async def _ae_unavailable_reply(update: Update) -> None:
    await update.message.reply_text("El módulo de cierre (AE) no está disponible.")


async def _ae_engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a los deals ahora. Engram no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def handle_deal_intent(intent: str, data: dict, update: Update) -> bool:
    """
    Dispatch to the right ae_deals function based on detected intent.
    Returns True if handled (caller should return early), False otherwise.
    """
    if not _AE_DEALS_AVAILABLE:
        return False

    try:
        if intent == "list":
            deals = await list_deals()
            await update.message.reply_text(
                format_deal_list(deals, title="Pipeline AE"), parse_mode="Markdown"
            )
            return True

        if intent == "add":
            empresa = data.get("empresa", "").strip()
            sector = data.get("sector", "").strip()
            ciudad = data.get("ciudad", "").strip()
            if not empresa or not sector:
                return False
            deal = await add_deal(empresa=empresa, sector=sector, ciudad=ciudad)
            await update.message.reply_text(format_deal_added(deal))
            return True

    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("AeEngramConnectionError in deal intent handler: %s", exc)
        await _ae_engram_error_reply(update)
        return True
    except Exception as exc:
        logger.error("Unexpected error in deal intent handler: %s", exc)

    return False


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    estado_filter = None
    if context.args:
        arg = context.args[0].lower()
        if arg in AE_VALID_ESTADOS:
            estado_filter = arg

    try:
        deals = await list_deals(estado=estado_filter)
        _update_deal_cache(deals)
        for i, d in enumerate(deals, 1):
            d._display_id = i
        title = f"Pipeline AE — {estado_filter}" if estado_filter else "Pipeline AE"
        await update.message.reply_text(
            format_deal_list(deals, title=title), parse_mode="Markdown"
        )
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Airtable unreachable in /deals: %s", exc)
        await _ae_engram_error_reply(update)


async def cmd_deal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso:\n"
            "  /deal <empresa>, <sector>, <ciudad>, <contacto> — añadir deal\n"
            "  /deal <id>  — ver detalle\n"
            "Ejemplo: /deal Clínica Fisio Norte, fisio, Madrid, Laura"
        )
        return

    raw = " ".join(context.args)

    # If single integer arg → view detail by display number
    if raw.strip().isdigit():
        deal_n = int(raw.strip())
        deal_obj = _get_deal_by_display_id(deal_n)
        if deal_obj is None:
            await update.message.reply_text(
                f"Deal #{deal_n} no encontrado. Ejecuta /deals primero."
            )
            return
        try:
            deal = await get_deal(deal_obj.id)
            if deal is None:
                await update.message.reply_text(f"Deal #{deal_n} no encontrado.")
            else:
                await update.message.reply_text(
                    format_deal_detail(deal), parse_mode="Markdown"
                )
        except (AeEngramConnectionError, AeEngramDataError) as exc:
            logger.error("Airtable unreachable in /deal detail: %s", exc)
            await _ae_engram_error_reply(update)
        return

    # Otherwise → parse as empresa, sector, ciudad?, contacto?
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 2:
        await update.message.reply_text(
            "Uso: /deal <empresa>, <sector>, <ciudad>, <contacto>\n"
            "Ejemplo: /deal Clínica Fisio Norte, fisio, Madrid, Laura"
        )
        return

    empresa = parts[0]
    sector = parts[1]
    ciudad = parts[2] if len(parts) > 2 else ""
    contacto = parts[3] if len(parts) > 3 else ""

    try:
        deal = await add_deal(
            empresa=empresa,
            sector=sector,
            ciudad=ciudad,
            contacto=contacto,
        )
        await update.message.reply_text(format_deal_added(deal))
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Engram unreachable in /deal add: %s", exc)
        await _ae_engram_error_reply(update)


async def cmd_dealstatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /dealstatus <id> <estado> [razon]\n"
            "Ejemplo: /dealstatus 2 negociacion\n"
            f"Estados válidos: {', '.join(sorted(AE_VALID_ESTADOS))}"
        )
        return

    try:
        deal_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (de /deals).")
        return

    deal_obj = _get_deal_by_display_id(deal_n)
    if deal_obj is None:
        await update.message.reply_text(f"Deal #{deal_n} no encontrado. Ejecuta /deals primero.")
        return

    nuevo_estado = context.args[1].lower()
    if nuevo_estado not in AE_VALID_ESTADOS:
        await update.message.reply_text(
            f"Estado inválido. Opciones: {', '.join(sorted(AE_VALID_ESTADOS))}"
        )
        return

    razon_perdido = " ".join(context.args[2:]) if len(context.args) > 2 else ""

    try:
        deal = await update_deal_estado(
            record_id=deal_obj.id,
            nuevo_estado=nuevo_estado,
            razon_perdido=razon_perdido,
        )
        if deal is None:
            await update.message.reply_text(f"Deal #{deal_n} no encontrado.")
        else:
            await update.message.reply_text(format_deal_estado_updated(deal))
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Airtable unreachable in /dealstatus: %s", exc)
        await _ae_engram_error_reply(update)
    except ValueError as exc:
        await update.message.reply_text(str(exc))


async def cmd_propuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text("Uso: /propuesta <num_deal>\nEjemplo: /propuesta 3")
        return

    try:
        deal_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (de /deals).")
        return

    deal_obj = _get_deal_by_display_id(deal_n)
    if deal_obj is None:
        await update.message.reply_text(f"Deal #{deal_n} no encontrado. Ejecuta /deals primero.")
        return

    try:
        deal = await get_deal(deal_obj.id)
        if deal is None:
            await update.message.reply_text(f"Deal #{deal_n} no encontrado.")
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        propuesta = await generate_propuesta(deal, _context_os, anthropic_client, module_system=_module_contexts.get("ae", ""))
        updated = await save_propuesta(deal_obj.id, propuesta)
        if updated is None:
            await update.message.reply_text(
                "No pude guardar la propuesta porque el deal ya no existe."
            )
            return

        await update.message.reply_text(
            f"Propuesta para {updated.empresa}:\n\n{propuesta}"
        )
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Airtable unreachable in /propuesta: %s", exc)
        await _ae_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error generating proposal for deal #%s: %s", deal_obj.id, exc)
        await update.message.reply_text(f"Error generando propuesta: {exc}")


async def cmd_objecion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /objecion <deal_id> <texto>\n"
            "Ejemplo: /objecion 3 Dice que 229€/mes es caro"
        )
        return

    try:
        deal_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (de /deals).")
        return

    deal_obj = _get_deal_by_display_id(deal_n)
    if deal_obj is None:
        await update.message.reply_text(f"Deal #{deal_n} no encontrado. Ejecuta /deals primero.")
        return

    texto = " ".join(context.args[1:])

    try:
        deal = await add_objecion(deal_obj.id, texto)
        if deal is None:
            await update.message.reply_text(f"Deal #{deal_n} no encontrado.")
        else:
            await update.message.reply_text(
                f"Objeción guardada en {deal.empresa}."
            )
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Airtable unreachable in /objecion: %s", exc)
        await _ae_engram_error_reply(update)


async def cmd_dealnota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _AE_DEALS_AVAILABLE:
        await _ae_unavailable_reply(update)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /dealnota <id> <texto>\n"
            "Ejemplo: /dealnota 1 llamada positiva, quiere demo la semana que viene"
        )
        return

    try:
        deal_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (de /deals).")
        return

    deal_obj = _get_deal_by_display_id(deal_n)
    if deal_obj is None:
        await update.message.reply_text(f"Deal #{deal_n} no encontrado. Ejecuta /deals primero.")
        return

    nota = " ".join(context.args[1:])

    try:
        deal = await update_deal_nota(deal_obj.id, nota)
        if deal is None:
            await update.message.reply_text(f"Deal #{deal_n} no encontrado.")
        else:
            await update.message.reply_text(f"Nota añadida a {deal.empresa}.")
    except (AeEngramConnectionError, AeEngramDataError) as exc:
        logger.error("Airtable unreachable in /dealnota: %s", exc)
        await _ae_engram_error_reply(update)


# ---------------------------------------------------------------------------
# CFO Invoice Management handlers
# ---------------------------------------------------------------------------


async def _cfo_unavailable_reply(update: Update) -> None:
    await update.message.reply_text("El módulo de facturación (CFO) no está disponible.")


async def _cfo_engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a las facturas ahora. Engram no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def cmd_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CFO_AVAILABLE:
        await _cfo_unavailable_reply(update)
        return

    try:
        await _check_overdue()
        # Ensure client cache is populated so invoice names can be resolved
        if not _cs_client_cache and _CS_AVAILABLE:
            clients = await _get_clients()
            _update_cs_cache(clients)
        client_names = {c.id: c.nombre for c in _cs_client_cache}
        invoices = await _get_invoices()
        _cfo_invoice_cache.clear()
        _cfo_invoice_cache.extend(invoices)
        result = await _list_invoices(client_names=client_names)
        await update.message.reply_text(result, parse_mode="Markdown")
    except (CfoEngramConnectionError, CfoEngramDataError) as exc:
        logger.error("Airtable unreachable in /ingresos: %s", exc)
        await _cfo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /ingresos: %s", exc)
        await update.message.reply_text(f"Error cargando facturas: {exc}")


async def cmd_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CFO_AVAILABLE:
        await _cfo_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /factura <núm_cliente> | <concepto> | <importe>\n"
            "Ejemplo: /factura 1 | Agente voz mensual | 229\n"
            "(Ejecuta /clientes primero para ver los números)"
        )
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "Faltan datos. Uso: /factura <núm_cliente> | <concepto> | <importe>\n"
            "Ejemplo: /factura 1 | Agente voz mensual | 229"
        )
        return

    try:
        client_n = int(parts[0])
    except ValueError:
        await update.message.reply_text(
            f"El primer parámetro debe ser el número del cliente (de /clientes), ej: 1"
        )
        return

    client = _get_client_by_display_id(client_n)
    if client is None:
        await update.message.reply_text(
            f"Cliente #{client_n} no encontrado. Ejecuta /clientes primero."
        )
        return

    concepto = parts[1]
    try:
        importe = float(parts[2].replace(",", ".").replace("€", "").strip())
    except ValueError:
        await update.message.reply_text(
            f"El importe {parts[2]!r} no es válido. Usa un número, ej: 229 o 229.50"
        )
        return

    try:
        invoice = await _add_invoice(client.id, client.nombre, concepto, importe)
        await update.message.reply_text(
            f"Factura creada:\n"
            f"Cliente: {invoice.cliente}\n"
            f"Concepto: {invoice.concepto}\n"
            f"Importe: {invoice.importe:.2f}€\n"
            f"Vencimiento: {invoice.fecha_vencimiento}"
        )
    except (CfoEngramConnectionError, CfoEngramDataError) as exc:
        logger.error("Engram unreachable in /factura: %s", exc)
        await _cfo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /factura: %s", exc)
        await update.message.reply_text(f"Error creando factura: {exc}")


async def cmd_pagada(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CFO_AVAILABLE:
        await _cfo_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /pagada <id>\nEjemplo: /pagada 3"
        )
        return

    try:
        display_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (el de la lista /ingresos).")
        return

    invoice = _get_invoice_by_display_id(display_n)
    if invoice is None:
        await update.message.reply_text(
            f"Factura #{display_n} no encontrada. Ejecuta /ingresos primero."
        )
        return

    try:
        updated = await _mark_paid(invoice.id)
        if updated is None:
            await update.message.reply_text(f"Factura #{display_n} no encontrada en Airtable.")
        else:
            _cfo_invoice_cache[display_n - 1] = updated
            await update.message.reply_text(
                f"Factura #{display_n} marcada como pagada.\n"
                f"Cliente: {updated.cliente} — {updated.importe:.2f}€"
            )
    except (CfoEngramConnectionError, CfoEngramDataError) as exc:
        logger.error("Airtable unreachable in /pagada: %s", exc)
        await _cfo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /pagada: %s", exc)
        await update.message.reply_text(f"Error actualizando factura: {exc}")


async def cmd_mrr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CFO_AVAILABLE:
        await _cfo_unavailable_reply(update)
        return

    try:
        result = await _get_mrr()
        await update.message.reply_text(result, parse_mode="Markdown")
    except (CfoEngramConnectionError, CfoEngramDataError) as exc:
        logger.error("Engram unreachable in /mrr: %s", exc)
        await _cfo_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /mrr: %s", exc)
        await update.message.reply_text(f"Error calculando MRR: {exc}")


# ---------------------------------------------------------------------------
# CS Client Management handlers
# ---------------------------------------------------------------------------


async def _cs_unavailable_reply(update: Update) -> None:
    await update.message.reply_text("El módulo de clientes (CS) no está disponible.")


async def _cs_engram_error_reply(update: Update) -> None:
    await update.message.reply_text(
        "No puedo acceder a los clientes ahora. Engram no responde. "
        "Intentá de nuevo en unos minutos."
    )


async def handle_cs_intent(intent: str, data: dict, update: Update) -> bool:
    """
    Dispatch to the right cs_clients function based on detected intent.
    Returns True if handled (caller should return early), False otherwise.
    """
    if not _CS_AVAILABLE:
        return False

    try:
        if intent == "list":
            text = await _list_clients()
            await update.message.reply_text(text, parse_mode="Markdown")
            return True

        if intent == "churn":
            text = await _get_churn_report()
            await update.message.reply_text(text, parse_mode="Markdown")
            return True

        if intent == "mrr":
            total = await _get_total_mrr()
            await update.message.reply_text(f"MRR total (clientes activos): {total:.0f}€/mes")
            return True

    except (CsEngramConnectionError, CsEngramDataError) as exc:
        logger.error("CsEngramConnectionError in CS intent handler: %s", exc)
        await _cs_engram_error_reply(update)
        return True
    except Exception as exc:
        logger.error("Unexpected error in CS intent handler: %s", exc)

    return False


async def cmd_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of active clients + total MRR."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CS_AVAILABLE:
        await _cs_unavailable_reply(update)
        return

    try:
        clients = await _get_clients()
        _update_cs_cache(clients)
        text = await _list_clients()
        await update.message.reply_text(text, parse_mode="Markdown")
    except (CsEngramConnectionError, CsEngramDataError) as exc:
        logger.error("Airtable unreachable in /clientes: %s", exc)
        await _cs_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /clientes: %s", exc)
        await update.message.reply_text(f"Error cargando clientes: {exc}")


async def cmd_cliente_nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new client: /cliente_nuevo <nombre> | <contacto> | <sector> | <mrr>"""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CS_AVAILABLE:
        await _cs_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /cliente_nuevo <nombre> | <contacto> | <sector> | <mrr>\n"
            "Ejemplo: /cliente_nuevo Fisio Norte | Ana García | fisio | 229\n"
            f"Sectores válidos: {', '.join(sorted(CS_VALID_SECTORES))}"
        )
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 4:
        await update.message.reply_text(
            "Uso: /cliente_nuevo <nombre> | <contacto> | <sector> | <mrr>\n"
            "Ejemplo: /cliente_nuevo Fisio Norte | Ana García | fisio | 229"
        )
        return

    nombre = parts[0]
    contacto = parts[1]
    sector = parts[2].lower()
    try:
        mrr = float(parts[3].replace(",", ".").replace("€", "").strip())
    except ValueError:
        await update.message.reply_text("El MRR debe ser un número (ej: 229 o 229.50).")
        return

    try:
        client = await _add_client(nombre=nombre, contacto=contacto, sector=sector, mrr=mrr)
        await update.message.reply_text(format_client_added(client))
    except (CsEngramConnectionError, CsEngramDataError) as exc:
        logger.error("Engram unreachable in /cliente_nuevo: %s", exc)
        await _cs_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /cliente_nuevo: %s", exc)
        await update.message.reply_text(f"Error añadiendo cliente: {exc}")


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log a check-in for a client: /checkin <id> [notas]"""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CS_AVAILABLE:
        await _cs_unavailable_reply(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Uso: /checkin <id> [notas]\n"
            "Ejemplo: /checkin 3 Llamada positiva, contento con el servicio"
        )
        return

    try:
        display_n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El ID debe ser un número entero (el de la lista /clientes).")
        return

    notas = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    client = _get_client_by_display_id(display_n)
    if client is None:
        await update.message.reply_text(
            f"Cliente #{display_n} no encontrado. Ejecuta /clientes primero."
        )
        return

    try:
        updated = await _log_checkin(client.id, notas=notas)
        if updated is None:
            await update.message.reply_text(f"Cliente #{display_n} no encontrado en Airtable.")
        else:
            _cs_client_cache[display_n - 1] = updated
            await update.message.reply_text(format_checkin_logged(updated))
    except (CsEngramConnectionError, CsEngramDataError) as exc:
        logger.error("Airtable unreachable in /checkin: %s", exc)
        await _cs_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /checkin: %s", exc)
        await update.message.reply_text(f"Error registrando check-in: {exc}")


async def cmd_churn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show churn risk report."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    if not _CS_AVAILABLE:
        await _cs_unavailable_reply(update)
        return

    try:
        text = await _get_churn_report()
        await update.message.reply_text(text, parse_mode="Markdown")
    except (CsEngramConnectionError, CsEngramDataError) as exc:
        logger.error("Engram unreachable in /churn: %s", exc)
        await _cs_engram_error_reply(update)
    except Exception as exc:
        logger.error("Error in /churn: %s", exc)
        await update.message.reply_text(f"Error cargando reporte de churn: {exc}")


# ---------------------------------------------------------------------------
# Airtable sync — /sync command
# ---------------------------------------------------------------------------

async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger Airtable → Engram sync on-demand."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    import sys as _sys
    import os as _os
    sync_script = SCRIPT_DIR / "airtable_sync.py"
    if not sync_script.exists():
        await update.message.reply_text("❌ airtable_sync.py no encontrado.")
        return

    if not _os.getenv("AIRTABLE_API_KEY") or not _os.getenv("AIRTABLE_BASE_ID"):
        await update.message.reply_text(
            "⚠️ *Airtable no configurado*\n\n"
            "Añade en `.env`:\n"
            "`AIRTABLE_API_KEY=pat_xxx`\n"
            "`AIRTABLE_BASE_ID=appXXX`\n\n"
            "• API key → airtable.com/account → API\n"
            "• Base ID → URL de tu base: airtable.com/*BASE\\_ID*/tbl...",
            parse_mode="Markdown",
        )
        return

    table_arg = context.args[0].lower() if context.args else "all"
    if table_arg not in ("leads", "clients", "all"):
        await update.message.reply_text("Uso: /sync [leads|clients|all]")
        return

    await update.message.reply_text(f"⏳ Sincronizando Airtable → Engram ({table_arg})...")
    try:
        proc = await asyncio.create_subprocess_exec(
            _sys.executable, str(sync_script), "--table", table_arg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            out = (stdout or b"").decode()[-300:]
            await update.message.reply_text(f"✅ Sync completado\n`{out}`", parse_mode="Markdown")
        else:
            err = (stderr or b"").decode()[-400:]
            await update.message.reply_text(f"❌ Error en sync:\n`{err}`", parse_mode="Markdown")
    except asyncio.TimeoutError:
        await update.message.reply_text("⏱️ Sync tardó demasiado.")
    except Exception as exc:
        logger.error("Error running airtable_sync.py: %s", exc)
        await update.message.reply_text(f"❌ Error: {exc}")


# ---------------------------------------------------------------------------
# Dashboard — snapshot of all modules (no Claude, instant)
# ---------------------------------------------------------------------------

async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a quick snapshot of all modules: tasks, leads, deals, MRR, CS."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    from datetime import datetime as _dt
    lines: list[str] = [f"📊 *Dashboard Duendes* — {_dt.now().strftime('%d/%m %H:%M')}\n"]

    # COO — tareas
    if _COO_TASKS_AVAILABLE:
        try:
            tasks_text = _coo_brief_sync()
            if tasks_text and tasks_text != "No hay tareas pendientes.":
                lines.append(f"📋 *Tareas*\n{tasks_text}")
            else:
                lines.append("📋 *Tareas* — sin pendientes")
        except Exception:
            lines.append("📋 *Tareas* — no disponible")
    else:
        lines.append("📋 *Tareas* — módulo no cargado")

    # SDR — follow-ups
    if _SDR_LEADS_AVAILABLE:
        try:
            sdr_text = _sdr_brief_sync()
            if sdr_text and sdr_text != "No hay follow-ups pendientes.":
                lines.append(f"\n🔔 *Follow-ups SDR*\n{sdr_text}")
            else:
                lines.append("\n🔔 *Follow-ups SDR* — sin pendientes")
        except Exception:
            lines.append("\n🔔 *Follow-ups SDR* — no disponible")

    # CMO — drafts pendientes
    if _CMO_CONTENT_AVAILABLE:
        try:
            cmo_text = _cmo_brief_sync()
            if cmo_text:
                lines.append(f"\n✍️ *Posts pendientes*\n{cmo_text}")
            else:
                lines.append("\n✍️ *Posts* — sin drafts")
        except Exception:
            lines.append("\n✍️ *Posts* — no disponible")

    # AE — deals calientes
    if _AE_DEALS_AVAILABLE:
        try:
            ae_text = _ae_brief_sync()
            if ae_text and ae_text != "No hay deals activos.":
                lines.append(f"\n💼 *Pipeline AE*\n{ae_text}")
            else:
                lines.append("\n💼 *Pipeline AE* — vacío")
        except Exception:
            lines.append("\n💼 *Pipeline AE* — no disponible")

    # CFO — facturas + MRR
    if _CFO_AVAILABLE:
        try:
            cfo_text = _cfo_brief_sync()
            if cfo_text and cfo_text != "No hay facturas pendientes.":
                lines.append(f"\n💰 *Facturas*\n{cfo_text}")
            else:
                lines.append("\n💰 *Facturas* — sin pendientes")
        except Exception:
            lines.append("\n💰 *Facturas* — no disponible")

    # CS — clientes en riesgo / check-in
    if _CS_AVAILABLE:
        try:
            cs_text = _cs_brief_sync()
            if cs_text:
                lines.append(f"\n🤝 *CS — check-in pendiente*\n{cs_text}")
            else:
                lines.append("\n🤝 *CS* — todos los clientes al día")
        except Exception:
            lines.append("\n🤝 *CS* — no disponible")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Brief on-demand — triggers brief.py as subprocess
# ---------------------------------------------------------------------------

async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send the daily brief on-demand."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    import sys as _sys
    brief_script = SCRIPT_DIR / "brief.py"
    if not brief_script.exists():
        await update.message.reply_text("❌ brief.py no encontrado.")
        return

    await update.message.reply_text("⏳ Generando brief...")
    try:
        proc = await asyncio.create_subprocess_exec(
            _sys.executable, str(brief_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            err = (stderr or b"").decode()[-300:]
            await update.message.reply_text(f"❌ Error en brief:\n{err}")
        # Brief sends to Telegram itself — no need to relay output
    except asyncio.TimeoutError:
        await update.message.reply_text("⏱️ Brief tardó demasiado — revisa los logs.")
    except Exception as exc:
        logger.error("Error running brief.py: %s", exc)
        await update.message.reply_text(f"❌ Error: {exc}")


# ---------------------------------------------------------------------------
# Text handler
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    user_text = update.message.text or ""
    if not user_text.strip():
        return

    logger.info("Text message from Oscar: %s", user_text[:120])

    await update.message.chat.send_action(ChatAction.TYPING)

    # Pre-processing: check for task intent BEFORE calling Claude
    if _COO_TASKS_AVAILABLE:
        try:
            result = detect_task_intent(user_text)
            if result is not None:
                intent, data = result
                handled = await handle_task_intent(intent, data, update)
                if handled:
                    return
        except Exception as exc:
            logger.error("Task pre-processing error: %s", exc)
            # Fall through to Claude on any exception

    # Pre-processing: check for SDR lead intent BEFORE calling Claude
    if _SDR_LEADS_AVAILABLE:
        try:
            lead_result = detect_lead_intent(user_text)
            if lead_result is not None:
                lead_intent, lead_data = lead_result
                handled = await handle_lead_intent(lead_intent, lead_data, update)
                if handled:
                    return
        except Exception as exc:
            logger.error("SDR pre-processing error: %s", exc)
            # Fall through to Claude on any exception

    # Pre-processing: check for CMO content intent BEFORE calling Claude
    if _CMO_CONTENT_AVAILABLE:
        try:
            content_result = detect_content_intent(user_text)
            if content_result is not None:
                content_intent, content_data = content_result
                handled = await handle_content_intent(content_intent, content_data, update)
                if handled:
                    return
        except Exception as exc:
            logger.error("CMO pre-processing error: %s", exc)
            # Fall through to Claude on any exception

    # Pre-processing: check for AE deal intent BEFORE calling Claude
    if _AE_DEALS_AVAILABLE:
        try:
            deal_result = detect_deal_intent(user_text)
            if deal_result is not None:
                deal_intent, deal_data = deal_result
                handled = await handle_deal_intent(deal_intent, deal_data, update)
                if handled:
                    return
        except Exception as exc:
            logger.error("AE pre-processing error: %s", exc)
            # Fall through to Claude on any exception

    # Pre-processing: check for CFO invoice keywords BEFORE calling Claude
    if _CFO_AVAILABLE:
        import re as _re
        _cfo_keywords = _re.compile(
            r"\b(factura|ingreso|ingresos|mrr|cobro|cobros|pago|pagos|vencida|vencidas)\b",
            _re.IGNORECASE,
        )
        if _cfo_keywords.search(user_text):
            try:
                await _check_overdue()
                result = await _list_invoices()
                await update.message.reply_text(result, parse_mode="Markdown")
                return
            except Exception as exc:
                logger.error("CFO pre-processing error: %s", exc)
                # Fall through to Claude on any exception

    # Pre-processing: check for CS client intent BEFORE calling Claude
    if _CS_AVAILABLE:
        try:
            cs_result = detect_cs_intent(user_text)
            if cs_result is not None:
                cs_intent, cs_data = cs_result
                handled = await handle_cs_intent(cs_intent, cs_data, update)
                if handled:
                    return
        except Exception as exc:
            logger.error("CS pre-processing error: %s", exc)
            # Fall through to Claude on any exception

    # Pre-processing: NL detection for dashboard and brief
    import re as _re_nl
    _dashboard_re = _re_nl.compile(
        r"\b(dashboard|resumen|estado del negocio|snapshot|vista general|cómo vamos|como vamos)\b",
        _re_nl.IGNORECASE,
    )
    _brief_re = _re_nl.compile(
        r"\b(brief|briefing|dame el brief|informe del día|informe de hoy|qué tengo hoy|que tengo hoy)\b",
        _re_nl.IGNORECASE,
    )
    if _dashboard_re.search(user_text):
        await cmd_dashboard(update, context)
        return
    if _brief_re.search(user_text):
        await cmd_brief(update, context)
        return

    # ── Super Orchestrator: AI-powered routing ──────────────────────────────
    # Regex didn't match → ask Haiku which department should handle this
    dept, _action = await _route_message(user_text)

    module_ctx = _module_contexts.get(dept, "")

    # Department-specific handlers (conversational — no structured data needed)
    if dept == "coo" and _COO_TASKS_AVAILABLE and module_ctx:
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass  # fall through to generic Claude

    if dept == "sdr" and _SDR_LEADS_AVAILABLE and module_ctx:
        # If the action mentions qualifying leads, delegate to cmd_calificar
        if _SDR_QUALIFIER_AVAILABLE and "califica" in _action.lower():
            await cmd_calificar(update, context)
            return
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass

    if dept == "cmo" and _CMO_CONTENT_AVAILABLE and module_ctx:
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass

    if dept == "ae" and _AE_DEALS_AVAILABLE and module_ctx:
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass

    if dept == "cfo" and _CFO_AVAILABLE and module_ctx:
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass

    if dept == "cs" and _CS_AVAILABLE and module_ctx:
        try:
            answer = await ask_claude(user_text, extra_system=module_ctx)
            await update.message.reply_text(answer)
            return
        except Exception:
            pass

    # ── Final fallback: generic Claude with full context ─────────────────────
    try:
        answer = await ask_claude(user_text)
        await update.message.reply_text(answer)
    except Exception as exc:
        await update.message.reply_text(f"Error al contactar con Claude: {exc}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_oscar(update):
        await reject_unauthorized(update)
        return

    logger.info("Voice note received from Oscar")
    await update.message.chat.send_action(ChatAction.TYPING)

    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await tg_file.download_to_drive(tmp_path)
        logger.info("Voice note downloaded to %s", tmp_path)

        try:
            transcription = await transcribe_voice(tmp_path)
            logger.info("Transcription: %s", transcription[:120])
        except Exception as exc:
            logger.error("Whisper error: %s", exc)
            await update.message.reply_text(
                "No pude transcribir el audio, escribe el mensaje."
            )
            return

        try:
            answer = await ask_claude(transcription)
        except Exception as exc:
            await update.message.reply_text(f"Error al contactar con Claude: {exc}")
            return

        reply = f"🎤 *{transcription}*\n\n{answer}"
        await update.message.reply_text(reply, parse_mode="Markdown")

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Instantly handlers
# ---------------------------------------------------------------------------

async def cmd_campanas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista las campañas de Instantly."""
    if not is_oscar(update):
        await reject_unauthorized(update)
        return
    if not _INSTANTLY_AVAILABLE:
        await update.message.reply_text("Módulo Instantly no disponible.")
        return
    try:
        campaigns = await list_campaigns()
        await update.message.reply_text(format_campaigns(campaigns), parse_mode="Markdown")
    except Exception as exc:
        logger.error("Error en /campanas: %s", exc)
        await update.message.reply_text(f"Error: {exc}")


async def cmd_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Empuja un lead cualificado a una campaña de Instantly.
    Uso: /push <num_lead> <num_campaña>
    Ejemplo: /push 3 1
    Genera el email con Claude y lo añade a Instantly.
    """
    if not is_oscar(update):
        await reject_unauthorized(update)
        return
    if not _INSTANTLY_AVAILABLE:
        await update.message.reply_text("Módulo Instantly no disponible.")
        return
    if not _SDR_LEADS_AVAILABLE:
        await update.message.reply_text("Módulo SDR no disponible.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /push <num_lead> <num_campaña>\n"
            "Ejemplo: /push 3 1\n\n"
            "Primero ejecuta /leads para ver los números y /campanas para las campañas."
        )
        return

    try:
        lead_n = int(context.args[0])
        camp_n = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Los IDs deben ser números enteros.")
        return

    # Resolve lead from cache
    lead_obj = _get_lead_by_display_id(lead_n)
    if lead_obj is None:
        await update.message.reply_text(f"Lead #{lead_n} no encontrado. Ejecuta /leads primero.")
        return

    # Resolve campaign
    try:
        campaigns = await list_campaigns()
    except Exception as exc:
        await update.message.reply_text(f"Error cargando campañas: {exc}")
        return

    if camp_n < 1 or camp_n > len(campaigns):
        await update.message.reply_text(
            f"Campaña #{camp_n} no encontrada. Ejecuta /campanas para ver las disponibles."
        )
        return
    campaign = campaigns[camp_n - 1]

    if not lead_obj.email:
        await update.message.reply_text(
            f"El lead *{lead_obj.empresa}* no tiene email registrado.\n"
            f"Añádelo primero con /leadnota {lead_n} email: ejemplo@clinica.com",
            parse_mode="Markdown",
        )
        return

    # Generate cold email with Claude
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        from sdr_leads import generate_cold_email
        email_content = await generate_cold_email(
            lead_obj, _context_os, anthropic_client,
            module_system=_module_contexts.get("sdr", "")
        )
        # email_content is "Asunto: ...\n\nCuerpo: ..." or just the body
        lines = email_content.strip().split("\n", 2)
        if lines[0].lower().startswith("asunto:"):
            asunto = lines[0].split(":", 1)[1].strip()
            cuerpo = "\n".join(lines[2:]).strip() if len(lines) > 2 else "\n".join(lines[1:]).strip()
        else:
            asunto = f"Tu clínica y los pacientes que no puedes atender — {lead_obj.empresa}"
            cuerpo = email_content.strip()
    except Exception as exc:
        logger.error("Error generando email para push: %s", exc)
        await update.message.reply_text(f"Error generando el email: {exc}")
        return

    # Push to Instantly
    try:
        await add_lead_to_campaign(
            campaign_id=campaign.id,
            email=lead_obj.email,
            empresa=lead_obj.empresa,
            asunto=asunto,
            cuerpo=cuerpo,
            phone=lead_obj.telefono or "",
        )
    except Exception as exc:
        logger.error("Error añadiendo lead a Instantly: %s", exc)
        await update.message.reply_text(f"Error en Instantly: {exc}")
        return

    # Update lead estado in Airtable
    try:
        from sdr_leads import update_lead_estado
        await update_lead_estado(lead_obj.id, "contactado")
    except Exception as exc:
        logger.warning("No se pudo actualizar estado del lead: %s", exc)

    await update.message.reply_text(
        f"{format_lead_pushed(lead_obj.empresa, campaign.name)}\n\n"
        f"*Asunto:* {asunto}\n\n"
        f"{cuerpo[:300]}{'…' if len(cuerpo) > 300 else ''}",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Starting Duendes AIOS bot (@DuendesCRM_bot) in polling mode…")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Task management commands (COO module) — registered BEFORE text/voice handlers
    app.add_handler(CommandHandler("tareas", cmd_tareas))
    app.add_handler(CommandHandler("nueva", cmd_nueva))
    app.add_handler(CommandHandler("hecho", cmd_hecho))
    app.add_handler(CommandHandler("pendiente", cmd_pendiente))

    # SDR Lead Management commands
    app.add_handler(CommandHandler("sdr", cmd_sdr))
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(CommandHandler("lead", cmd_lead))
    app.add_handler(CommandHandler("leadstatus", cmd_leadstatus))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("followup", cmd_followup))
    app.add_handler(CommandHandler("leadnota", cmd_leadnota))
    app.add_handler(CommandHandler("calificar", cmd_calificar))

    # CMO Content Management commands
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("postguardar", cmd_postguardar))
    app.add_handler(CommandHandler("posts", cmd_posts))
    app.add_handler(CommandHandler("poststatus", cmd_poststatus))

    # AE Deal Management commands
    app.add_handler(CommandHandler("deals", cmd_deals))
    app.add_handler(CommandHandler("deal", cmd_deal))
    app.add_handler(CommandHandler("dealstatus", cmd_dealstatus))
    app.add_handler(CommandHandler("propuesta", cmd_propuesta))
    app.add_handler(CommandHandler("objecion", cmd_objecion))
    app.add_handler(CommandHandler("dealnota", cmd_dealnota))

    # CFO Invoice Management commands
    app.add_handler(CommandHandler("ingresos", cmd_ingresos))
    app.add_handler(CommandHandler("factura", cmd_factura))
    app.add_handler(CommandHandler("pagada", cmd_pagada))
    app.add_handler(CommandHandler("mrr", cmd_mrr))

    # CS Client Management commands
    app.add_handler(CommandHandler("clientes", cmd_clientes))
    app.add_handler(CommandHandler("cliente_nuevo", cmd_cliente_nuevo))
    app.add_handler(CommandHandler("checkin", cmd_checkin))
    app.add_handler(CommandHandler("churn", cmd_churn))

    # Instantly — Email Outreach
    app.add_handler(CommandHandler("campanas", cmd_campanas))
    app.add_handler(CommandHandler("push", cmd_push))

    # Dashboard + Brief on-demand + Airtable sync
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_handler(CommandHandler("sync", cmd_sync))

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
