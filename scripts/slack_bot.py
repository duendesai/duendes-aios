"""
Duendes AIOS — Slack Bot
Cada canal del workspace Duendes conecta con un departamento del AIOS.
Canal → agente siempre activo con su CLAUDE.md cargado como system prompt.
"""

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

try:
    from cmo_content_writer import (
        detect_content_intent,
        generate_post,
        generate_content_ideas,
        format_post_response,
        format_ideas_response,
    )
    _CMO_WRITER_AVAILABLE = True
except ImportError:
    _CMO_WRITER_AVAILABLE = False

try:
    from sdr_email_sequencer import (
        detect_sequence_intent,
        generate_sequence,
        generate_quick_followup,
        format_sequence_response,
        format_followup_response,
    )
    _SDR_SEQUENCER_AVAILABLE = True
except ImportError:
    _SDR_SEQUENCER_AVAILABLE = False

try:
    from ae_proposal_writer import (
        detect_proposal_intent,
        generate_proposal,
        generate_demo_prep,
        format_proposal_response,
        format_demo_prep_response,
    )
    _AE_PROPOSAL_AVAILABLE = True
except ImportError:
    _AE_PROPOSAL_AVAILABLE = False

try:
    from slack_commands import detect_command, execute_command
    _SLACK_COMMANDS_AVAILABLE = True
except ImportError:
    _SLACK_COMMANDS_AVAILABLE = False

try:
    from slack_memory import search_dept_memory, save_dept_memory, should_save_memory
    _ENGRAM_AVAILABLE = True
except ImportError:
    _ENGRAM_AVAILABLE = False

try:
    from slack_logger import log_message, save_thread_message, load_thread_history, save_task_context, load_task_context
    _SLACK_LOGGER_AVAILABLE = True
except ImportError:
    _SLACK_LOGGER_AVAILABLE = False

try:
    from notion_writer import log_tarea, crear_proyecto_estructurado, agregar_nota_a_proyecto, ejecutar_proyecto
    _NOTION_AVAILABLE = True
except ImportError:
    _NOTION_AVAILABLE = False

# Caché thread_key → Notion page_id (en memoria, se pierde al reiniciar pero es suficiente)
_thread_notion_page: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

SLACK_BOT_TOKEN: str = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN: str = os.environ["SLACK_APP_TOKEN"]
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "slack_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("duendes-slack")

# ---------------------------------------------------------------------------
# Channel → Department mapping
# ---------------------------------------------------------------------------

CHANNEL_MAP: dict[str, str] = {
    "orquestador": "orchestrator",
    "general": "orchestrator",
    "marketing": "cmo",
    "captacion": "sdr",
    "captación": "sdr",
    "sdr": "sdr",
    "ventas": "ae",
    "ae": "ae",
    "operaciones": "coo",
    "coo": "coo",
    "finanzas": "cfo",
    "cfo": "cfo",
    "clientes": "cs",
    "cs": "cs",
}

# Department display names for multi-dept responses
DEPT_DISPLAY: dict[str, str] = {
    "orchestrator": "Orquestador",
    "cmo": "Marketing",
    "sdr": "SDR",
    "ae": "Ventas",
    "coo": "Operaciones",
    "cfo": "Finanzas",
    "cs": "Clientes",
}

# Department → channel name (resolved to IDs at startup)
DEPT_CHANNEL_NAME: dict[str, str] = {
    "cmo": "marketing",
    "sdr": "captacion",
    "ae": "ventas",
    "coo": "operaciones",
    "cfo": "finanzas",
    "cs": "clientes",
    "orchestrator": "orquestador",
}

# Populated at startup: dept → channel_id
DEPT_CHANNEL_IDS: dict[str, str] = {}

# Keywords that trigger execution mode in a thread
_EXECUTE_KEYWORDS = ("ejecuta", "ejecutar", "execute", "hazlo", "dale", "adelante", "listo")

# thread_ts → task description (for execution context)
_thread_task_map: dict[str, str] = {}

# DM channel ID de Oscar (se guarda en el primer DM)
_oscar_dm_channel: str = ""

# Keywords in @mentions that map to departments
MENTION_MAP: dict[str, str] = {
    "@marketing": "cmo",
    "@cmo": "cmo",
    "@sdr": "sdr",
    "@ventas": "ae",
    "@ae": "ae",
    "@operaciones": "coo",
    "@coo": "coo",
    "@finanzas": "cfo",
    "@cfo": "cfo",
    "@clientes": "cs",
    "@cs": "cs",
}

# ---------------------------------------------------------------------------
# Department help texts (shown when user sends "help" / "ayuda" / etc.)
# ---------------------------------------------------------------------------

DEPT_HELP: dict[str, str] = {
    "orchestrator": """*Secretario — Tu asistente ejecutivo* 🗂️

Coordina todos los departamentos, da resúmenes del negocio y delega tareas.

*Puedes pedirme:*
• Estado general del negocio: _"¿cómo va todo?"_
• Delegar a un depto: _"dile a marketing que prepare un post sobre fisios"_
• Resumen semanal: _"dame un resumen de esta semana"_
• Coordinar varios deptos: _"coordina con SDR y marketing una campaña dental"_
• Cualquier pregunta estratégica de alto nivel

*Reuniones multi-departamento:*
Menciona los agentes en cualquier canal:
`@marketing @sdr prepara campaña fisios Madrid`""",

    "cmo": """*CMO — Director de Marketing* 📣

Experto en contenido B2B, marca y posicionamiento. Genera posts de LinkedIn, estrategia de contenido y copywriting en el tono de Duendes.

*Puedes pedirme:*
• _"Escríbeme un post de LinkedIn sobre agentes de voz para fisios"_
• _"Dame 5 ideas de contenido para esta semana"_
• _"Mejora este copy: [texto]"_
• _"¿Qué ángulo usar para hablar con clínicas dentales?"_
• _"Crea un gancho para Instagram sobre [tema]"_

*Comandos:*
• `borradores` → ver drafts guardados
• `help` → esta ayuda""",

    "sdr": """*Captación — Desarrollo de Negocio* 🎯

Experto en prospección B2B, outreach en frío y cualificación de leads. Gestiona el pipeline de entrada.

*Puedes pedirme:*
• _"Busca fisios en Valencia"_ → lanza Apify Google Maps
• _"¿Cómo van mis leads?"_ → lista del pipeline
• _"Califica los leads nuevos"_ → scoring con IA
• _"Genera un email frío para [empresa]"_
• _"¿Qué leads hay que contactar hoy?"_

*Comandos:*
• `leads` → lista de leads activos
• `calificar` → scoring de leads nuevos
• `campañas` → campañas de Instantly activas
• `help` → esta ayuda""",

    "ae": """*AE — Account Executive* 🤝

Experto en cierre de ventas B2B. Gestiona deals, prepara propuestas y guía negociaciones hasta el cierre.

*Puedes pedirme:*
• _"¿Cómo está el pipeline de ventas?"_
• _"Prepara una propuesta para [empresa]"_
• _"¿Cómo respondo a esta objeción: [objeción]?"_
• _"El deal de [empresa] lleva 2 semanas parado, qué hago"_
• _"Prepárame para la demo de mañana con [sector]"_

*Comandos:*
• `deals` → pipeline actual
• `help` → esta ayuda""",

    "coo": """*COO — Operaciones* ⚙️

Experto en operaciones y gestión de proyectos. Gestiona tareas, SOPs y procesos internos de Duendes.

*Puedes pedirme:*
• _"¿Qué tengo pendiente hoy?"_
• _"Añade tarea: [descripción]"_
• _"Crea un SOP para [proceso]"_
• _"¿Qué tareas llevan más de una semana abiertas?"_
• _"Prioriza mis tareas de esta semana"_

*Comandos:*
• `tareas` → lista de tareas activas
• `help` → esta ayuda""",

    "cfo": """*CFO — Finanzas* 💰

Experto en finanzas para agencias. Gestiona facturas, MRR, cashflow y métricas financieras.

*Puedes pedirme:*
• _"¿Cuál es mi MRR actual?"_
• _"¿Qué facturas están pendientes de cobro?"_
• _"Añade factura: [cliente] | [concepto] | [importe]"_
• _"¿Cómo va el cashflow este mes?"_
• _"Genera el resumen financiero del mes"_

*Comandos:*
• `facturas` → facturas pendientes
• `mrr` → MRR actual
• `help` → esta ayuda""",

    "cs": """*CS — Customer Success* 🌟

Experto en retención y éxito de clientes. Gestiona check-ins, detecta riesgo de churn y maximiza el valor de cada cliente.

*Puedes pedirme:*
• _"¿Cómo están mis clientes activos?"_
• _"¿Algún cliente en riesgo de irse?"_
• _"Registra un check-in con [cliente]"_
• _"¿Cuándo fue el último contacto con [cliente]?"_
• _"Prepara un mensaje de seguimiento para [cliente]"_

*Comandos:*
• `clientes` → lista de clientes activos
• `churn` → alertas de riesgo
• `help` → esta ayuda""",
}

# ---------------------------------------------------------------------------
# Channel topics (set via API at first message received)
# ---------------------------------------------------------------------------

CHANNEL_TOPICS: dict[str, str] = {
    "orquestador": "Tu asistente ejecutivo. Escribe aquí para coordinar departamentos, pedir resúmenes o delegar tareas. Escribe 'help' para ver todo lo que puedo hacer.",
    "marketing": "CMO de Duendes. Genera posts de LinkedIn, estrategia de contenido y copywriting. Escribe 'help' para ver comandos.",
    "captacion": "Captación de Duendes. Prospección, leads y outreach en frío. Escribe 'help' para ver comandos.",
    "ventas": "AE de Duendes. Pipeline de deals, propuestas y negociaciones. Escribe 'help' para ver comandos.",
    "operaciones": "COO de Duendes. Tareas, procesos y operaciones. Escribe 'help' para ver comandos.",
    "finanzas": "CFO de Duendes. Facturas, MRR y finanzas. Escribe 'help' para ver comandos.",
    "clientes": "CS de Duendes. Retención, check-ins y churn. Escribe 'help' para ver comandos.",
}

_topics_set: bool = False


async def fetch_dept_channel_ids(client) -> None:
    """Resolve dept → channel_id mapping at startup."""
    try:
        result = await client.conversations_list(limit=200)
        channels = result.get("channels", [])
        for ch in channels:
            name = ch.get("name", "")
            ch_id = ch.get("id", "")
            for dept, dept_ch_name in DEPT_CHANNEL_NAME.items():
                if name == dept_ch_name:
                    DEPT_CHANNEL_IDS[dept] = ch_id
        logger.info("Dept channel IDs resolved: %s", DEPT_CHANNEL_IDS)
    except Exception as exc:
        logger.warning("fetch_dept_channel_ids failed: %s", exc)


async def post_task_to_dept_channel(client, dept: str, task: str, plan: str) -> Optional[str]:
    """
    Flow:
    1. Create a Slack Canvas with the full plan (requires canvases:write scope).
    2. Post a notice in the channel with the canvas link.
    3. Oscar edits the canvas → writes 'ejecuta' in the thread → Notion project is created.
    Falls back to posting the plan directly if canvas creation fails.
    """
    channel_id = DEPT_CHANNEL_IDS.get(dept)
    if not channel_id:
        logger.warning("No channel ID for dept=%s — cannot post task", dept)
        return None

    dept_display = DEPT_DISPLAY.get(dept, dept.upper())
    task_preview = task[:100] + ("…" if len(task) > 100 else "")
    canvas_id = None

    def _sanitize_for_canvas(md: str) -> str:
        """Remove markdown elements Slack Canvas doesn't support."""
        lines = []
        for line in md.split("\n"):
            # Strip blockquote prefix (> ) before checking content
            content = line.strip().lstrip(">").strip()
            # Remove thematic breaks (---, ***, ___) anywhere — unsupported inside blockquotes
            if re.fullmatch(r'[-*_]{3,}', content):
                continue
            lines.append(line)
        return "\n".join(lines)

    # Step 1: create canvas with the full plan
    if plan:
        try:
            canvas_result = await client.canvases_create(
                title=f"[{dept_display}] {task_preview}",
                document_content={"type": "markdown", "markdown": _sanitize_for_canvas(plan)},
            )
            canvas_id = canvas_result.get("canvas_id")
            if canvas_id:
                await client.canvases_access_set(
                    canvas_id=canvas_id,
                    access_level="write",
                    channel_ids=[channel_id],
                )
                logger.info("Canvas created for #%s: %s", DEPT_CHANNEL_NAME.get(dept), canvas_id)
        except Exception as exc:
            logger.warning("Canvas creation failed (add canvases:write scope): %s", exc)

    # Step 2: post notice in channel
    try:
        if canvas_id:
            notice = (
                f"*📋 [{dept_display}]* Propuesta lista en el canvas.\n"
                f"Revisá, editá lo que necesites y respondé *ejecuta* en este hilo."
            )
        else:
            # Fallback: post plan as text until canvases:write scope is added
            notice = f"*📋 [{dept_display}]*\n\n{plan[:3000]}"

        result = await client.chat_postMessage(
            channel=channel_id,
            text=notice,
            mrkdwn=True,
        )
        thread_ts = result.get("ts")
        logger.info("Task posted to #%s (thread_ts=%s)", DEPT_CHANNEL_NAME.get(dept), thread_ts)

        # Fallback overflow: rest of plan in thread replies
        if not canvas_id and plan and len(plan) > 3000:
            for i in range(3000, len(plan), 3000):
                await client.chat_postMessage(
                    channel=channel_id,
                    text=plan[i:i + 3000],
                    thread_ts=thread_ts,
                    mrkdwn=True,
                )

        return thread_ts
    except Exception as exc:
        logger.error("post_task_to_dept_channel failed for dept=%s: %s", dept, exc)
        return None


async def setup_channel_topics(client) -> None:
    """Set topics for each known channel. Best-effort — won't crash on failure."""
    try:
        result = await client.conversations_list(limit=200)
        channels = result.get("channels", [])
    except Exception as exc:
        logger.warning("setup_channel_topics: could not list channels: %s", exc)
        return

    for channel in channels:
        name: str = channel.get("name", "")
        channel_id: str = channel.get("id", "")
        topic_text = CHANNEL_TOPICS.get(name)
        if not topic_text:
            continue
        try:
            await client.conversations_setTopic(channel=channel_id, topic=topic_text)
            logger.info("Set topic for #%s (%s)", name, channel_id)
        except Exception as exc:
            logger.warning("Could not set topic for #%s: %s", name, exc)


# ---------------------------------------------------------------------------
# Department system prompts (loaded at startup)
# ---------------------------------------------------------------------------

DEPT_SYSTEMS: dict[str, str] = {}

_DEPT_KEYS = ("orchestrator", "cmo", "sdr", "ae", "coo", "cfo", "cs")

_GENERIC_SYSTEM = (
    "Eres un agente del AIOS de Duendes. Ayuda a Oscar con su negocio de agentes de voz con IA "
    "para clínicas y profesionales de la salud."
)


def load_dept_systems() -> None:
    """Load each department's CLAUDE.md at startup."""
    global DEPT_SYSTEMS
    for dept in _DEPT_KEYS:
        md_path = BASE_DIR / "modulos" / dept / "CLAUDE.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                DEPT_SYSTEMS[dept] = content
                logger.info("Loaded %s/CLAUDE.md — %d chars", dept, len(content))
            else:
                DEPT_SYSTEMS[dept] = _GENERIC_SYSTEM
                logger.warning("Empty CLAUDE.md for dept=%s, using fallback", dept)
        else:
            DEPT_SYSTEMS[dept] = _GENERIC_SYSTEM
            logger.warning("CLAUDE.md not found for dept=%s at %s, using fallback", dept, md_path)


# ---------------------------------------------------------------------------
# Context OS loader
# ---------------------------------------------------------------------------

_context_os: str = ""
_voz_tono: str = ""
_ofertas_context: str = ""


def load_voz_tono() -> None:
    """Load voz-tono.md from the context directory."""
    global _voz_tono
    voz_tono_path = BASE_DIR / "context" / "voz-tono.md"
    if voz_tono_path.exists():
        _voz_tono = voz_tono_path.read_text(encoding="utf-8")
        logger.info("Voz-tono loaded: %d chars", len(_voz_tono))
    else:
        logger.warning("voz-tono.md not found at %s", voz_tono_path)


def load_ofertas() -> None:
    """Load ofertas.md (pricing context) for the AE proposal writer."""
    global _ofertas_context
    p = BASE_DIR / "context" / "ofertas.md"
    if p.exists():
        _ofertas_context = p.read_text(encoding="utf-8")
        logger.info("Ofertas context loaded: %d chars", len(_ofertas_context))
    else:
        logger.warning("ofertas.md not found at %s — AE proposal writer will use fallback pricing", p)


def load_context_os() -> str:
    """Concatenate all context/*.md files from the project context directory."""
    global _context_os
    parts: list[str] = []
    context_dir = BASE_DIR / "context"
    if context_dir.exists():
        for md_file in sorted(context_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                parts.append(f"## [context] {md_file.name}\n\n{content}")
    _context_os = "\n\n---\n\n".join(parts)
    logger.info("Context OS loaded: %d chars from %d files", len(_context_os), len(parts))
    return _context_os


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# Thread history management
# ---------------------------------------------------------------------------

MAX_THREAD_MESSAGES = 20

thread_history: dict[str, list] = {}


def _get_thread_history(thread_key: str) -> list:
    if thread_key not in thread_history and _SLACK_LOGGER_AVAILABLE:
        # Recover thread from SQLite on restart
        rows = load_thread_history(thread_key, limit=MAX_THREAD_MESSAGES)
        if rows:
            thread_history[thread_key] = rows
            logger.info("Thread history recovered from SQLite: %s (%d msgs)", thread_key, len(rows))
    return thread_history.setdefault(thread_key, [])


def _append_message(thread_key: str, role: str, content: str) -> None:
    history = _get_thread_history(thread_key)
    history.append({"role": role, "content": content})
    # Trim to max — keep most recent messages
    if len(history) > MAX_THREAD_MESSAGES:
        thread_history[thread_key] = history[-MAX_THREAD_MESSAGES:]
    # Persist to SQLite for cross-restart recovery
    if _SLACK_LOGGER_AVAILABLE:
        save_thread_message(thread_key, role, content)


# ---------------------------------------------------------------------------
# Core Claude call
# ---------------------------------------------------------------------------

async def ask_department(dept: str, user_text: str, thread_key: str, skip_notion: bool = False) -> str:
    """Call the appropriate department agent and maintain thread history."""
    dept_system = DEPT_SYSTEMS.get(dept, _GENERIC_SYSTEM)
    system = dept_system
    if _context_os:
        system = f"{system}\n\n---\n\n{_context_os}"

    # Enrich system prompt with relevant Engram memory before calling Claude
    if _ENGRAM_AVAILABLE:
        memory_context = await search_dept_memory(dept, user_text)
        if memory_context:
            system = system + "\n\n---\n\n## Contexto de sesiones anteriores\n" + memory_context

    # Append user message to history
    _append_message(thread_key, "user", user_text)
    history = _get_thread_history(thread_key)

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=system,
            messages=history if history else [{"role": "user", "content": user_text}],
        )
        assistant_text = response.content[0].text
        _append_message(thread_key, "assistant", assistant_text)

        # Persist important interactions to Engram
        if _ENGRAM_AVAILABLE and should_save_memory(user_text, assistant_text):
            await save_dept_memory(
                dept,
                f"Conversación {dept}: {user_text[:60]}",
                f"Pregunta: {user_text}\n\nRespuesta: {assistant_text[:500]}",
            )

        # Respuestas largas → Notion. Si el hilo ya tiene proyecto, añadir nota; si no, crear proyecto nuevo.
        # skip_notion=True cuando el llamador va a manejar Notion por su cuenta (ej. DM routing al canal).
        DRAFT_THRESHOLD = 800
        if _NOTION_AVAILABLE and len(assistant_text) > DRAFT_THRESHOLD and not skip_notion:
            dept_display = DEPT_DISPLAY.get(dept, dept.title())
            existing_page_id = _thread_notion_page.get(thread_key)

            if existing_page_id:
                # Hilo con proyecto existente → añadir nota dentro del proyecto
                nota_titulo = f"Actualización — {user_text[:60].strip()}"
                nota_url = await agregar_nota_a_proyecto(existing_page_id, nota_titulo, assistant_text)
                if nota_url:
                    await log_tarea(tarea=user_text[:100], dept=dept, resultado=assistant_text[:500])
                    return (
                        f"*[{dept_display}]* He añadido los cambios como nota en el proyecto:\n"
                        f"→ {nota_url}\n\n"
                        f"Revisá en Notion y cuando estés listo mandame *ejecuta*."
                    )
            else:
                # Primer mensaje del hilo → crear proyecto estructurado nuevo
                titulo = user_text[:80].strip()
                proyecto = await crear_proyecto_estructurado(titulo, assistant_text, dept)
                if proyecto:
                    _thread_notion_page[thread_key] = proyecto["id"]
                    await log_tarea(tarea=user_text[:100], dept=dept, resultado=assistant_text[:500])
                    return (
                        f"*[{dept_display}]* Plan guardado en Notion con Status=Inbox:\n"
                        f"→ {proyecto['url']}\n\n"
                        f"Editá directamente ahí. Cualquier cambio que pidas en este hilo lo añado como nota dentro del mismo proyecto."
                    )

        # Respuesta corta → Log tarea a Notion como siempre
        if _NOTION_AVAILABLE and len(user_text) > 10:
            await log_tarea(
                tarea=user_text[:100],
                dept=dept,
                resultado=assistant_text[:500],
            )

        return assistant_text
    except Exception as exc:
        logger.error("Claude call failed for dept=%s thread=%s: %s", dept, thread_key, exc)
        # Remove the user message we just added since the call failed
        h = _get_thread_history(thread_key)
        if h and h[-1]["role"] == "user":
            h.pop()
        return "Error procesando tu mensaje. Inténtalo de nuevo."


# ---------------------------------------------------------------------------
# Orchestrator routing (Haiku call to detect delegation intent)
# ---------------------------------------------------------------------------

_ROUTING_SYSTEM = (
    "Eres un router de mensajes. Tu única tarea es detectar si el mensaje de Oscar delega "
    "trabajo a un departamento concreto de la empresa. Los departamentos son: "
    "cmo (marketing), sdr (prospección), ae (ventas), coo (operaciones), cfo (finanzas), cs (clientes). "
    "Responde SOLO con el nombre del departamento en minúsculas (cmo/sdr/ae/coo/cfo/cs) "
    "si detectas delegación clara. Si no hay delegación clara, responde exactamente: none"
)


async def _route_orchestrator(user_text: str) -> Optional[str]:
    """Lightweight Haiku call to detect if Oscar is delegating to a specific dept."""
    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            system=_ROUTING_SYSTEM,
            messages=[{"role": "user", "content": user_text}],
        )
        result = response.content[0].text.strip().lower()
        if result in ("cmo", "sdr", "ae", "coo", "cfo", "cs"):
            return result
        return None
    except Exception as exc:
        logger.warning("Routing call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Channel → dept resolution
# ---------------------------------------------------------------------------

def get_channel_dept(channel_name: str) -> str:
    """Normalize channel name and return the matching department key."""
    normalized = channel_name.lower().lstrip("#").strip()
    return CHANNEL_MAP.get(normalized, "orchestrator")


# ---------------------------------------------------------------------------
# Voice note transcription (Whisper)
# Requires Slack app scope: files:read
# ---------------------------------------------------------------------------

async def _transcribe_slack_audio(file_info: dict, client) -> str:
    """Download audio from Slack and transcribe with Whisper."""
    url = file_info.get("url_private_download") or file_info.get("url_private")
    if not url:
        return ""

    # Download with Slack auth token
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

    filetype = file_info.get("filetype", "mp4")
    suffix = f".{filetype}"

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(url, headers=headers)
            resp.raise_for_status()
            audio_data = resp.content

        # Write to temp file and transcribe
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        # Use OpenAI Whisper
        import openai
        openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        with open(tmp_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es"
            )

        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)

        return transcript.text

    except Exception as e:
        logger.warning("Voice transcription failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Slack app
# ---------------------------------------------------------------------------

app = AsyncApp(token=SLACK_BOT_TOKEN)


@app.event("message")
async def handle_message(event: dict, say, client) -> None:
    """Handle all messages in channels. Route to the appropriate department agent."""
    # Ignore bot messages
    if event.get("bot_id"):
        return

    # Ignore message edits and deletes
    subtype = event.get("subtype", "")
    if subtype in ("message_changed", "message_deleted"):
        return

    text: str = event.get("text", "").strip()

    # Handle voice notes / audio files
    if event.get("files"):
        audio_filetypes = ("mp4", "m4a", "webm", "ogg", "mp3", "wav")
        audio_file = None
        for f in event.get("files", []):
            if f.get("mimetype", "").startswith("audio/") or f.get("filetype") in audio_filetypes:
                audio_file = f
                break

        if audio_file:
            channel_id = event.get("channel", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts") or ts

            transcribed = await _transcribe_slack_audio(audio_file, client)
            if transcribed:
                await say(text=f"_🎤 Transcripción: {transcribed}_", thread_ts=thread_ts)
                text = transcribed  # process as if Oscar typed this
                # fall through to normal message handling below with the transcribed text
            else:
                return  # transcription failed, already logged
        else:
            return  # non-audio file, ignore

    if not text:
        return

    channel_id = event.get("channel", "")
    ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or ts

    # DMs have channel IDs starting with "D" — treat as direct conversation
    is_dm = channel_id.startswith("D")

    if is_dm:
        # DM: always orchestrator, one continuous conversation per user
        channel_name = "dm"
        dept = "orchestrator"
        thread_key = channel_id  # one conversation per DM, no thread splitting
        # Save Oscar's DM channel for later notifications
        global _oscar_dm_channel
        if not _oscar_dm_channel:
            _oscar_dm_channel = channel_id
    else:
        # Channel: resolve name → department
        try:
            channel_info = await client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"].get("name", "general")
        except Exception as exc:
            logger.warning("Could not fetch channel info for %s: %s", channel_id, exc)
            channel_name = "general"
        dept = get_channel_dept(channel_name)
        thread_key = f"{channel_id}:{thread_ts}"

    logger.info(
        "Message in %s → dept=%s | thread_key=%s | text_len=%d",
        f"DM:{channel_id}" if is_dm else f"#{channel_name}",
        dept,
        thread_key,
        len(text),
    )

    # Log Oscar's message to SQLite history
    if _SLACK_LOGGER_AVAILABLE:
        log_message(channel_name, dept, text, is_bot=False, ts=event.get("ts", ""))

    # Set channel topics on first message (best-effort, once per process)
    global _topics_set
    if not _topics_set:
        _topics_set = True
        asyncio.ensure_future(setup_channel_topics(client))

    # Help command — respond immediately without calling Claude
    if text.strip().lower() in ("help", "ayuda", "comandos", "/help"):
        help_text = DEPT_HELP.get(dept)
        if help_text:
            await say(text=help_text, thread_ts=thread_ts, mrkdwn=True)
            return

    # --- Airtable command dispatch ---
    if _SLACK_COMMANDS_AVAILABLE:
        cmd = detect_command(text, dept)
        if cmd:
            result = await execute_command(cmd, dept, anthropic_client)
            await say(text=result, thread_ts=thread_ts)
            return

    # CMO content writer intercept — detect content generation intent before generic Claude call
    if dept == "cmo" and _CMO_WRITER_AVAILABLE:
        intent = detect_content_intent(text)
        if intent:
            if intent["action"] == "post":
                post = await generate_post(
                    intent["topic"],
                    intent["sector"],
                    intent["formato"],
                    anthropic_client,
                    voz_tono=_voz_tono,
                    context_os=_context_os,
                )
                await say(text=format_post_response(post, intent["sector"], intent["formato"]), thread_ts=thread_ts)
                return
            elif intent["action"] == "ideas":
                ideas = await generate_content_ideas(intent["sector"], 5, anthropic_client, context_os=_context_os)
                await say(text=format_ideas_response(ideas, intent["sector"]), thread_ts=thread_ts)
                return

    # SDR email sequencer intercept — detect sequence/follow-up intent before generic Claude call
    if dept == "sdr" and _SDR_SEQUENCER_AVAILABLE:
        seq_intent = detect_sequence_intent(text)
        if seq_intent:
            if seq_intent["action"] == "sequence":
                seq = await generate_sequence(
                    seq_intent["empresa"],
                    seq_intent["sector"],
                    "",
                    "",
                    anthropic_client,
                    context_os=_context_os,
                )
                await say(text=format_sequence_response(seq), thread_ts=thread_ts)
                return
            elif seq_intent["action"] == "followup":
                fu = await generate_quick_followup(
                    seq_intent["empresa"],
                    seq_intent["sector"],
                    seq_intent["dias"],
                    anthropic_client,
                    context_os=_context_os,
                )
                await say(text=format_followup_response(fu, seq_intent["empresa"]), thread_ts=thread_ts)
                return

    # AE proposal writer intercept — detect proposal/demo-prep intent before generic Claude call
    if dept == "ae" and _AE_PROPOSAL_AVAILABLE:
        prop_intent = detect_proposal_intent(text)
        if prop_intent:
            if prop_intent["action"] == "proposal":
                proposal = await generate_proposal(
                    prop_intent["empresa"],
                    prop_intent["sector"],
                    prop_intent["notas"],
                    anthropic_client,
                    ofertas_context=_ofertas_context,
                    context_os=_context_os,
                )
                await say(text=format_proposal_response(proposal, prop_intent["empresa"], prop_intent["sector"]), thread_ts=thread_ts)
                return
            elif prop_intent["action"] == "demo_prep":
                prep = await generate_demo_prep(
                    prop_intent["empresa"],
                    prop_intent["sector"],
                    prop_intent["notas"],
                    anthropic_client,
                    context_os=_context_os,
                )
                await say(text=format_demo_prep_response(prep, prop_intent["empresa"]), thread_ts=thread_ts)
                return

    # Detect "ejecuta" in channel threads → execution mode
    is_execute = any(kw in text.lower().split() for kw in _EXECUTE_KEYWORDS)

    if not is_dm and is_execute:
        # Execution mode: generate deliverable + create Notion project + notify Oscar
        dept_display = DEPT_DISPLAY.get(dept, dept.upper())

        # Load context: memory first, then SQLite (survives restarts)
        task_context = _thread_task_map.get(thread_key, "")
        if not task_context and _SLACK_LOGGER_AVAILABLE:
            task_context = load_task_context(thread_key)
            if task_context:
                logger.info("Execution context loaded from SQLite for thread %s", thread_key)

        # Post "working" message in thread
        await say(text=f"_⚙️ [{dept_display}] Ejecutando..._", thread_ts=thread_ts)

        if task_context:
            execute_prompt = (
                f"MODO EJECUCIÓN. Oscar aprobó el siguiente plan y pidió ejecutarlo.\n\n"
                f"PLAN APROBADO (ejecuta ESTO, no inventes nada nuevo):\n{task_context}\n\n"
                f"Instrucción de Oscar: {text}\n\n"
                "REGLAS:\n"
                "- Ejecuta exactamente el plan aprobado, no lo reemplaces por otro\n"
                "- No preguntes nada, no des opciones, no hagas resúmenes del negocio\n"
                "- Entrega el trabajo concreto pedido en el plan\n\n"
                "Estructura:\n"
                "## TAREAS\n- [x] Lo que hiciste\n\n"
                "## NOTAS\nEntregable completo aquí\n\n"
                "## PENDIENTE OSCAR\n- Solo si Oscar necesita hacer algo específico"
            )
        else:
            execute_prompt = (
                f"Oscar dice: {text}\n\n"
                "No hay plan previo cargado. Pide a Oscar que comparta el plan que quiere ejecutar, "
                "o que empiece una nueva tarea desde el DM con el orquestador."
            )
        response = await ask_department(dept, execute_prompt, thread_key)

        # Create Notion project in execution mode
        notion_result = None
        if _NOTION_AVAILABLE:
            titulo = task_context[:80] or text[:80]
            notion_result = await ejecutar_proyecto(titulo, response, dept)

        if _SLACK_LOGGER_AVAILABLE:
            log_message(channel_name, dept, response, is_bot=True, ts="")

        # Post completion in channel thread
        if notion_result:
            pendientes = notion_result.get("pendiente_oscar", [])
            completion_msg = f"✅ *[{dept_display}]* Completado. Todo guardado en Notion:\n→ {notion_result['url']}"
            if pendientes:
                items = "\n".join(f"• {p}" for p in pendientes)
                completion_msg += f"\n\n*📋 Pendiente para vos:*\n{items}"
        else:
            completion_msg = f"✅ *[{dept_display}]* Completado:\n\n{response[:1500]}"

        await say(text=completion_msg, thread_ts=thread_ts)

        # DM Oscar with Notion link
        if notion_result and _oscar_dm_channel:
            channel_name_dept = DEPT_CHANNEL_NAME.get(dept, dept)
            dm_text = (
                f"✅ *[{dept_display}]* Tarea completada en *#{channel_name_dept}*.\n"
                f"→ {notion_result['url']}"
            )
            if notion_result.get("pendiente_oscar"):
                dm_text += f"\n\n*Hay {len(notion_result['pendiente_oscar'])} tarea(s) pendiente(s) para vos en Notion.*"
            try:
                await client.chat_postMessage(channel=_oscar_dm_channel, text=dm_text)
            except Exception as exc:
                logger.warning("Could not DM Oscar: %s", exc)
        return

    # Orchestrator special routing
    if dept == "orchestrator":
        routed_dept = await _route_orchestrator(text)
        if routed_dept and is_dm:
            # DM → detected dept → post plan to dept channel, confirm in DM
            logger.info("DM routing to dept=%s — posting to channel", routed_dept)
            plan_response = await ask_department(routed_dept, text, thread_key, skip_notion=True)
            thread_ts_posted = await post_task_to_dept_channel(client, routed_dept, text, plan_response)
            dept_display = DEPT_DISPLAY.get(routed_dept, routed_dept.upper())
            channel_name_dept = DEPT_CHANNEL_NAME.get(routed_dept, routed_dept)
            if thread_ts_posted:
                full_context = f"TAREA ORIGINAL:\n{text}\n\nPLAN DEL AGENTE:\n{plan_response}"
                tkey = f"{DEPT_CHANNEL_IDS.get(routed_dept)}:{thread_ts_posted}"
                _thread_task_map[tkey] = full_context
                if _SLACK_LOGGER_AVAILABLE:
                    save_task_context(tkey, full_context)
                dm_confirm = (
                    f"*[{dept_display}]* Plan enviado a *#{channel_name_dept}*.\n"
                    f"Revisá ahí, hacé los cambios que quieras y escribí *ejecuta* en ese hilo cuando estés listo."
                )
            else:
                dm_confirm = f"*[{dept_display}]* Plan listo (no pude postearlo al canal, revisá los logs):\n\n{plan_response}"
            if _SLACK_LOGGER_AVAILABLE:
                log_message("dm", routed_dept, dm_confirm, is_bot=True, ts="")
            await say(text=dm_confirm)
            return
        elif routed_dept:
            # Channel message routed to dept
            dept_display = DEPT_DISPLAY.get(routed_dept, routed_dept.upper())
            response = await ask_department(routed_dept, text, thread_key)
            response = f"_[Delegado a {dept_display}]_\n\n{response}"
        else:
            response = await ask_department("orchestrator", text, thread_key)
    else:
        response = await ask_department(dept, text, thread_key)

    # Log bot response to SQLite history
    if _SLACK_LOGGER_AVAILABLE:
        log_message(channel_name, dept, response, is_bot=True, ts="")

    # DMs: conversación lineal (sin thread_ts). Canales: responder en hilo.
    if is_dm:
        await say(text=response)
    else:
        await say(text=response, thread_ts=thread_ts)


@app.event("app_mention")
async def handle_mention(event: dict, say, client) -> None:
    """Handle @mentions — supports cross-department queries."""
    text: str = event.get("text", "").strip()
    channel_id: str = event.get("channel", "")
    ts: str = event.get("ts", "")
    thread_ts: str = event.get("thread_ts") or ts
    thread_key = f"{channel_id}:{thread_ts}"

    # Detect if the message mentions specific departments
    mentioned_depts: list[str] = []
    for keyword, dept_key in MENTION_MAP.items():
        if keyword.lower() in text.lower():
            if dept_key not in mentioned_depts:
                mentioned_depts.append(dept_key)

    if len(mentioned_depts) > 1:
        # Multi-department meeting — ask each dept and combine
        logger.info("Multi-dept @mention: %s", mentioned_depts)
        responses: list[str] = []
        tasks = [
            ask_department(dept, text, f"{thread_key}:{dept}")
            for dept in mentioned_depts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for dept, result in zip(mentioned_depts, results):
            display = DEPT_DISPLAY.get(dept, dept.upper())
            if isinstance(result, Exception):
                responses.append(f"*[{display}]:*\nError procesando tu mensaje. Inténtalo de nuevo.")
            else:
                responses.append(f"*[{display}]:*\n{result}")
        combined = "\n\n".join(responses)
        await say(text=combined, thread_ts=thread_ts)

    elif len(mentioned_depts) == 1:
        # Single specific department mentioned
        dept = mentioned_depts[0]
        logger.info("Single-dept @mention: dept=%s", dept)
        response = await ask_department(dept, text, thread_key)
        await say(text=response, thread_ts=thread_ts)

    else:
        # No specific dept — use orchestrator
        logger.info("@mention with no specific dept — using orchestrator")
        routed_dept = await _route_orchestrator(text)
        if routed_dept:
            dept_display = DEPT_DISPLAY.get(routed_dept, routed_dept.upper())
            response = await ask_department(routed_dept, text, thread_key)
            response = f"_[Delegado a {dept_display}]_\n\n{response}"
        else:
            response = await ask_department("orchestrator", text, thread_key)
        await say(text=response, thread_ts=thread_ts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    # Load everything at startup
    load_dept_systems()
    load_context_os()
    load_voz_tono()
    load_ofertas()

    # Log loaded departments
    logger.info("=== Duendes AIOS Slack Bot starting ===")
    for dept in _DEPT_KEYS:
        size = len(DEPT_SYSTEMS.get(dept, ""))
        logger.info("  dept=%-12s system_prompt=%d chars", dept, size)
    logger.info("  context_os=%d chars", len(_context_os))
    logger.info("Channel map: %d entries", len(CHANNEL_MAP))

    # Resolve dept → channel IDs using the app's web client
    await fetch_dept_channel_ids(app.client)

    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
