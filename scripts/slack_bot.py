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
    "cmo": "cmo",
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
    return thread_history.setdefault(thread_key, [])


def _append_message(thread_key: str, role: str, content: str) -> None:
    history = _get_thread_history(thread_key)
    history.append({"role": role, "content": content})
    # Trim to max — keep most recent messages
    if len(history) > MAX_THREAD_MESSAGES:
        thread_history[thread_key] = history[-MAX_THREAD_MESSAGES:]


# ---------------------------------------------------------------------------
# Core Claude call
# ---------------------------------------------------------------------------

async def ask_department(dept: str, user_text: str, thread_key: str) -> str:
    """Call the appropriate department agent and maintain thread history."""
    dept_system = DEPT_SYSTEMS.get(dept, _GENERIC_SYSTEM)
    system = dept_system
    if _context_os:
        system = f"{system}\n\n---\n\n{_context_os}"

    # Append user message to history
    _append_message(thread_key, "user", user_text)
    history = _get_thread_history(thread_key)

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system,
            messages=history[:-0] if history else [{"role": "user", "content": user_text}],
        )
        assistant_text = response.content[0].text
        _append_message(thread_key, "assistant", assistant_text)
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

    # Resolve channel name → department
    try:
        channel_info = await client.conversations_info(channel=channel_id)
        channel_name: str = channel_info["channel"].get("name", "general")
    except Exception as exc:
        logger.warning("Could not fetch channel info for %s: %s", channel_id, exc)
        channel_name = "general"

    dept = get_channel_dept(channel_name)
    thread_key = f"{channel_id}:{thread_ts}"

    logger.info(
        "Message in #%s → dept=%s | thread_key=%s | text_len=%d",
        channel_name,
        dept,
        thread_key,
        len(text),
    )

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

    # Orchestrator special routing
    if dept == "orchestrator":
        routed_dept = await _route_orchestrator(text)
        if routed_dept:
            logger.info("Orchestrator routing detected: delegating to dept=%s", routed_dept)
            dept_display = DEPT_DISPLAY.get(routed_dept, routed_dept.upper())
            response = await ask_department(routed_dept, text, thread_key)
            response = f"_[Delegado a {dept_display}]_\n\n{response}"
        else:
            response = await ask_department("orchestrator", text, thread_key)
    else:
        response = await ask_department(dept, text, thread_key)

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

    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
