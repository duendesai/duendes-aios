"""
Duendes AIOS — CMO Content Management Module
Handles content draft CRUD + LinkedIn post generation via Engram HTTP REST API (port 7437).
All async operations for bot.py; sync variants for brief.py.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from coo_tasks import EngramConnectionError, EngramDataError

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

logger = logging.getLogger("duendes-bot.cmo_content")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENGRAM_URL: str = os.getenv("ENGRAM_URL", "http://127.0.0.1:7437")
ENGRAM_PROJECT: str = "gentleman-ai"
CONTENT_TOPIC_KEY: str = "cmo/content/drafts"
BOT_SESSION_ID: str = "duendes-bot-cmo"

VALID_SECTORS: set[str] = {"fisio", "quiro", "dental", "abogados", "general"}
VALID_TIPOS: set[str] = {"linkedin", "email", "general"}
VALID_ESTADOS: set[str] = {"borrador", "listo", "publicado"}

# ---------------------------------------------------------------------------
# Embedded voice/tone principles (from context/voz-tono.md)
# Embedded as constant to avoid runtime file-path dependencies.
# ---------------------------------------------------------------------------

_VOZ_TONO_PRINCIPLES: str = """VOZ Y TONO DE OSCAR / DUENDES:
- Ve al punto desde la primera frase. Sin introducciones vacías ni relleno.
- Usa ejemplos concretos con números ("Una clínica dental pierde de media 3 llamadas al día fuera de horario")
- NO empieces con "En el mundo actual...", "En el vertiginoso mundo digital...", "Estoy emocionado de compartir..."
- NO uses frases de LinkedIn corporativo. NO hype tecnológico ("revolucionario", "disruptivo", "game-changer")
- Español de España. Tuteo siempre. Frases cortas — punto y seguido antes que coma.
- Párrafos de 2-3 líneas máximo.
- Sin emojis en exceso — un emoji ocasional está bien, lluvia de emojis no.
- Sin signos de exclamación al final de cada frase.
- La IA es una herramienta, no la revolución del universo.
- Habla de problemas reales del sector. Concreto sobre abstracto.
- Ejemplo de buen tono: "Tu clínica pierde llamadas cada día. No porque no quieras cogerlas — sino porque estás con un paciente. Un agente de voz resuelve eso."
"""

# ICP pain points per sector (for generation context)
_SECTOR_CONTEXT: dict[str, str] = {
    "fisio": (
        "Clínica de fisioterapia o quiropráctica. 1-3 fisioterapeutas. "
        "Problema: está en consulta cuando llaman para pedir cita. "
        "No puede coger el teléfono con las manos ocupadas. "
        "Pierde llamadas de nuevos pacientes que no vuelven a llamar. "
        "Trabaja solo sin recepcionista. Budget: 150-300€/mes."
    ),
    "quiro": (
        "Clínica quiropráctica. 1-2 quiroprácticos. "
        "Problema: pierde llamadas mientras trata pacientes. "
        "Cada llamada perdida = una cita perdida = ~60-120€. "
        "No tiene recepcionista. Quiere algo que funcione sin complicaciones técnicas."
    ),
    "dental": (
        "Clínica dental privada. 1-3 sillones. "
        "Problema: llamadas perdidas fuera de horario (tardes, fines de semana). "
        "La asistente interrumpe al dentista para coger el teléfono. "
        "Pacientes que llaman, no contestan y se van a otra clínica. "
        "Ticket medio paciente nuevo: 500-1000€. ROI muy obvio."
    ),
    "abogados": (
        "Despacho de abogados pequeño. 1-5 abogados sin recepcionista. "
        "Problema: llamadas durante juicios o reuniones. "
        "Tiempo perdido en consultas que no se convierten en clientes. "
        "Necesita cualificar la consulta antes de que llegue al abogado."
    ),
    "general": (
        "Negocio pequeño español de 1-5 personas que recibe llamadas que no puede atender. "
        "El problema universal: estás trabajando cuando llaman, y si no contestas, "
        "el cliente llama al siguiente. Pierdes negocio por no poder estar al teléfono."
    ),
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ContentDraft:
    id: int
    titulo: str           # Short title/slug for display (auto-generated if empty)
    cuerpo: str           # Full post text
    sector: str           # fisio | quiro | dental | abogados | general | ""
    tipo: str             # linkedin | email | general
    estado: str           # borrador | listo | publicado
    created_at: str       # ISO 8601 UTC
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ContentDraft":
        return cls(
            id=data["id"],
            titulo=data.get("titulo", ""),
            cuerpo=data.get("cuerpo", ""),
            sector=data.get("sector", ""),
            tipo=data.get("tipo", "linkedin"),
            estado=data.get("estado", "borrador"),
            created_at=data.get("created_at", _now_iso()),
            tags=data.get("tags", []),
        )


@dataclass
class ContentStore:
    drafts: list[ContentDraft] = field(default_factory=list)
    next_id: int = 1
    last_updated: str = field(default_factory=lambda: _now_iso())

    def to_dict(self) -> dict:
        return {
            "drafts": [d.to_dict() for d in self.drafts],
            "next_id": self.next_id,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContentStore":
        return cls(
            drafts=[ContentDraft.from_dict(d) for d in data.get("drafts", [])],
            next_id=data.get("next_id", 1),
            last_updated=data.get("last_updated", _now_iso()),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _auto_titulo(cuerpo: str, max_len: int = 60) -> str:
    """Generate a title from the first line of cuerpo, truncated to max_len."""
    first_line = cuerpo.strip().split("\n")[0].strip()
    if len(first_line) <= max_len:
        return first_line
    return first_line[:max_len].rstrip() + "..."


# ---------------------------------------------------------------------------
# Engram HTTP Client (CMO-specific)
# ---------------------------------------------------------------------------


class CmoEngramClient:
    """Thin wrapper over Engram HTTP API for CMO content draft storage.
    Structurally identical to EngramClient in coo_tasks — own constants only.
    """

    def __init__(self, base_url: str = ENGRAM_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # ── Async methods ──────────────────────────────────────────────────────

    async def ensure_session(self) -> None:
        """Create bot session if it doesn't exist (idempotent)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.base_url}/sessions",
                    json={
                        "id": BOT_SESSION_ID,
                        "project": ENGRAM_PROJECT,
                        "directory": str(PROJECT_DIR),
                    },
                )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngramConnectionError(f"Cannot connect to Engram: {exc}") from exc
        except Exception:
            # Duplicate session or other non-critical errors — ignore
            pass

    async def load_drafts(self) -> ContentStore:
        """Search for cmo/content/drafts observation and parse JSON."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Use limit=20 — FTS5 ranks by relevance, not topic_key equality
                r = await client.get(
                    f"{self.base_url}/search",
                    params={
                        "q": CONTENT_TOPIC_KEY,
                        "project": ENGRAM_PROJECT,
                        "limit": 20,
                    },
                )
                r.raise_for_status()
                results = r.json()

                if not results:
                    logger.info("No active content store found — starting fresh")
                    return ContentStore()

                # Find exact topic_key match — skip SDD artifacts that mention this string
                matched = next(
                    (r for r in results if r.get("topic_key") == CONTENT_TOPIC_KEY),
                    None,
                )
                if matched is None:
                    logger.info(
                        "No observation with topic_key=%r found in search results "
                        "(top result topic_key=%r) — starting fresh",
                        CONTENT_TOPIC_KEY,
                        results[0].get("topic_key"),
                    )
                    return ContentStore()

                obs_id = matched["id"]

                # Get full observation content
                r2 = await client.get(f"{self.base_url}/observations/{obs_id}")
                r2.raise_for_status()
                obs = r2.json()
                raw = obs.get("content", "")

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngramConnectionError(f"Cannot connect to Engram: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise EngramConnectionError(f"Engram HTTP error: {exc}") from exc

        try:
            data = json.loads(raw)
            return ContentStore.from_dict(data)
        except json.JSONDecodeError:
            logger.warning(
                "Content store observation is not JSON — starting fresh. "
                "Content preview: %r",
                raw[:200],
            )
            return ContentStore()
        except (KeyError, TypeError) as exc:
            logger.error("Malformed content store: %r", raw[:500])
            raise EngramDataError(f"Cannot parse content store: {exc}") from exc

    async def save_drafts(self, store: ContentStore) -> None:
        """Save content store back to Engram via topic_key upsert."""
        store.last_updated = _now_iso()
        payload = {
            "session_id": BOT_SESSION_ID,
            "type": "architecture",
            "title": CONTENT_TOPIC_KEY,
            "content": json.dumps(store.to_dict(), ensure_ascii=False),
            "project": ENGRAM_PROJECT,
            "scope": "project",
            "topic_key": CONTENT_TOPIC_KEY,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(f"{self.base_url}/observations", json=payload)
                r.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngramConnectionError(f"Cannot connect to Engram: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise EngramConnectionError(f"Engram HTTP error: {exc}") from exc

    # ── Sync methods (for brief.py) ────────────────────────────────────────

    def load_drafts_sync(self) -> ContentStore:
        """Synchronous version for brief.py."""
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(
                    f"{self.base_url}/search",
                    params={
                        "q": CONTENT_TOPIC_KEY,
                        "project": ENGRAM_PROJECT,
                        "limit": 20,
                    },
                )
                r.raise_for_status()
                results = r.json()

                if not results:
                    return ContentStore()

                matched = next(
                    (r for r in results if r.get("topic_key") == CONTENT_TOPIC_KEY),
                    None,
                )
                if matched is None:
                    logger.info(
                        "No observation with topic_key=%r found in search results "
                        "(top result topic_key=%r) — starting fresh",
                        CONTENT_TOPIC_KEY,
                        results[0].get("topic_key"),
                    )
                    return ContentStore()

                obs_id = matched["id"]
                r2 = client.get(f"{self.base_url}/observations/{obs_id}")
                r2.raise_for_status()
                obs = r2.json()
                raw = obs.get("content", "")

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngramConnectionError(f"Cannot connect to Engram: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise EngramConnectionError(f"Engram HTTP error: {exc}") from exc

        try:
            data = json.loads(raw)
            return ContentStore.from_dict(data)
        except json.JSONDecodeError:
            logger.warning(
                "Content store observation is not JSON — starting fresh. "
                "Content preview: %r",
                raw[:200],
            )
            return ContentStore()
        except (KeyError, TypeError) as exc:
            logger.error("Malformed content store: %r", raw[:500])
            raise EngramDataError(f"Cannot parse content store: {exc}") from exc

    def save_drafts_sync(self, store: ContentStore) -> None:
        """Synchronous version for brief.py."""
        store.last_updated = _now_iso()
        payload = {
            "session_id": BOT_SESSION_ID,
            "type": "architecture",
            "title": CONTENT_TOPIC_KEY,
            "content": json.dumps(store.to_dict(), ensure_ascii=False),
            "project": ENGRAM_PROJECT,
            "scope": "project",
            "topic_key": CONTENT_TOPIC_KEY,
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{self.base_url}/observations", json=payload)
                r.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngramConnectionError(f"Cannot connect to Engram: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise EngramConnectionError(f"Engram HTTP error: {exc}") from exc


# ---------------------------------------------------------------------------
# Module-level client instance
# ---------------------------------------------------------------------------

_client = CmoEngramClient()


# ---------------------------------------------------------------------------
# Phase 2: CRUD Operations
# ---------------------------------------------------------------------------


async def add_draft(
    cuerpo: str,
    titulo: str = "",
    sector: str = "",
    tipo: str = "linkedin",
    tags: list[str] | None = None,
) -> ContentDraft:
    """Add a new content draft. Returns the created ContentDraft."""
    if tipo not in VALID_TIPOS:
        logger.warning("Invalid tipo %r — defaulting to 'linkedin'", tipo)
        tipo = "linkedin"
    if sector and sector not in VALID_SECTORS:
        logger.warning("Unknown sector %r — keeping as-is", sector)

    if not titulo.strip():
        titulo = _auto_titulo(cuerpo)

    await _client.ensure_session()
    store = await _client.load_drafts()

    draft = ContentDraft(
        id=store.next_id,
        titulo=titulo.strip(),
        cuerpo=cuerpo.strip(),
        sector=sector.strip().lower(),
        tipo=tipo,
        estado="borrador",
        created_at=_now_iso(),
        tags=tags or [],
    )
    store.drafts.append(draft)
    store.next_id += 1
    await _client.save_drafts(store)
    return draft


async def list_drafts(estado: str | None = None) -> list[ContentDraft]:
    """List drafts with optional estado filter. Returns sorted by created_at desc."""
    store = await _client.load_drafts()
    drafts = store.drafts

    if estado is not None:
        drafts = [d for d in drafts if d.estado == estado]

    return sorted(drafts, key=lambda d: d.created_at, reverse=True)


async def get_draft(draft_id: int) -> ContentDraft | None:
    """Get a single draft by ID. Returns None if not found."""
    store = await _client.load_drafts()
    return next((d for d in store.drafts if d.id == draft_id), None)


async def update_draft_estado(draft_id: int, nuevo_estado: str) -> ContentDraft | None:
    """Update draft estado. Returns updated ContentDraft or None if not found."""
    if nuevo_estado not in VALID_ESTADOS:
        raise ValueError(
            f"Invalid estado: {nuevo_estado!r}. Valid: {sorted(VALID_ESTADOS)}"
        )

    store = await _client.load_drafts()
    draft = next((d for d in store.drafts if d.id == draft_id), None)
    if draft is None:
        return None

    draft.estado = nuevo_estado
    await _client.save_drafts(store)
    return draft


async def delete_draft(draft_id: int) -> bool:
    """Delete a draft by ID. Returns True if deleted, False if not found."""
    store = await _client.load_drafts()
    original_count = len(store.drafts)
    store.drafts = [d for d in store.drafts if d.id != draft_id]
    if len(store.drafts) == original_count:
        return False
    await _client.save_drafts(store)
    return True


# ---------------------------------------------------------------------------
# Phase 2: Brief sync helper
# ---------------------------------------------------------------------------


def get_pending_drafts_for_brief_sync() -> str:
    """Sync variant for brief.py. Returns formatted string of posts ready to publish."""
    store = _client.load_drafts_sync()
    listo = [d for d in store.drafts if d.estado == "listo"]

    if not listo:
        return "No hay posts listos para publicar."

    count = len(listo)
    lines = [f"Tienes {count} post{'s' if count != 1 else ''} listo{'s' if count != 1 else ''} para publicar:"]
    for d in sorted(listo, key=lambda x: x.created_at, reverse=True):
        sector_label = f" [{d.sector}]" if d.sector else ""
        lines.append(f"  #{d.id} {d.titulo}{sector_label}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 3: Content Generation (Claude)
# ---------------------------------------------------------------------------


async def generate_post(
    sector: str,
    contexto_negocio: str,
    anthropic_client: Any,
    module_system: str = "",
) -> str:
    """
    Generate a LinkedIn post draft in Oscar's voice for the given sector.

    Args:
        sector: One of fisio | quiro | dental | abogados | general
        contexto_negocio: Full context OS string from bot.py _context_os
        anthropic_client: AsyncAnthropic instance from bot.py

    Returns:
        Generated LinkedIn post text (≤1300 chars)
    """
    sector = sector.strip().lower()
    if sector not in VALID_SECTORS:
        sector = "general"

    sector_ctx = _SECTOR_CONTEXT.get(sector, _SECTOR_CONTEXT["general"])

    system = module_system or (
        "Eres el CMO de Duendes, una agencia española de agentes de voz con IA. "
        "Tu trabajo es escribir posts de LinkedIn para Oscar Grana, el fundador. "
        "El contenido debe sonar EXACTAMENTE como Oscar — no como una IA corporativa. "
        "Oscar es directo, concreto, sin florituras. Habla de problemas reales con ejemplos reales."
    )

    user_prompt = f"""Genera un post de LinkedIn para Oscar Grana sobre el sector: {sector.upper()}

CONTEXTO DEL SECTOR (ICP):
{sector_ctx}

REGLAS DE VOZ Y TONO (OBLIGATORIAS):
{_VOZ_TONO_PRINCIPLES}

CONTEXTO DEL NEGOCIO:
{contexto_negocio[:2000] if contexto_negocio else "(sin contexto adicional)"}

ESTRUCTURA DEL POST:
1. Hook (1-2 líneas): captura la atención con el problema concreto del sector
2. Desarrollo (3-4 párrafos cortos de 2-3 líneas): explica el problema y la solución
3. CTA (1 línea): una acción concreta o pregunta al lector
4. Hashtags: 3-5 hashtags relevantes en la última línea

RESTRICCIONES:
- MÁXIMO 1300 caracteres (LinkedIn óptimo)
- Solo el post, sin comentarios ni explicaciones tuyas
- En español de España
- Tuteo
- Sin emojis en exceso (máximo 1-2 si encajan)"""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


async def generate_ideas(
    n: int = 3,
    contexto_negocio: str = "",
    anthropic_client: Any = None,
    module_system: str = "",
) -> str:
    """
    Generate N content ideas for LinkedIn posts.

    Args:
        n: Number of ideas to generate (default 3)
        contexto_negocio: Full context OS string from bot.py _context_os
        anthropic_client: AsyncAnthropic instance from bot.py

    Returns:
        Numbered list of ideas with title + 1-line description
    """
    system = module_system or (
        "Eres el CMO de Duendes, agencia española de agentes de voz con IA. "
        "Generas ideas de contenido concretas y accionables para LinkedIn. "
        "Las ideas deben ser relevantes para el ICP de Duendes: clínicas de fisio, dental, "
        "despachos de abogados y otros negocios pequeños españoles que pierden llamadas."
    )

    user_prompt = f"""Genera {n} ideas de posts de LinkedIn para Oscar Grana (Duendes).

CONTEXTO DEL NEGOCIO:
{contexto_negocio[:1500] if contexto_negocio else "(agencia de agentes de voz IA para España)"}

REGLAS:
- Cada idea = Título corto + descripción de 1 frase con el ángulo del post
- Mezcla: problema del ICP, proceso/historia de Oscar, concepto educativo sobre agentes de voz
- Concreto y específico. Sin ideas genéricas tipo "habla de tus valores"
- En español de España

FORMATO (exactamente así):
1. [Título de la idea]: [descripción del ángulo en 1 frase]
2. [Título de la idea]: [descripción del ángulo en 1 frase]
...

Solo las ideas, sin explicaciones adicionales."""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Phase 4: Formatters
# ---------------------------------------------------------------------------

_ESTADO_EMOJI: dict[str, str] = {
    "borrador": "📝",
    "listo": "✅",
    "publicado": "📢",
}


def format_draft_list(drafts: list[ContentDraft], title: str = "Posts") -> str:
    """Format drafts grouped by estado as Telegram-friendly text (Markdown)."""
    if not drafts:
        return "No hay posts guardados."

    # Group by estado in priority order
    estado_order = ["listo", "borrador", "publicado"]
    groups: dict[str, list[ContentDraft]] = {e: [] for e in estado_order}
    for d in drafts:
        groups.setdefault(d.estado, []).append(d)

    lines = [f"*{title}*\n"]
    for estado in estado_order:
        group = groups.get(estado, [])
        if not group:
            continue
        emoji = _ESTADO_EMOJI.get(estado, "")
        lines.append(f"{emoji} *{estado.capitalize()}*")
        for d in group:
            sector_label = f" [{d.sector}]" if d.sector else ""
            lines.append(f"  #{d.id} {d.titulo}{sector_label}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_draft_added(draft: ContentDraft) -> str:
    """Confirmation message for newly saved draft."""
    sector_label = f" [{draft.sector}]" if draft.sector else ""
    return f"Post #{draft.id} guardado como borrador: {draft.titulo}{sector_label}"


def format_draft_estado_updated(draft: ContentDraft, old_estado: str) -> str:
    """Confirmation for estado change."""
    emoji = _ESTADO_EMOJI.get(draft.estado, "")
    return f"Post #{draft.id} actualizado: {draft.titulo} — {old_estado} → {emoji} {draft.estado}"


# ---------------------------------------------------------------------------
# Phase 4: Natural Language Detection
# ---------------------------------------------------------------------------

_POST_GENERATE_PATTERNS = [
    re.compile(r"genera\s+(?:un\s+)?post(?:\s+(?:sobre|para|de|acerca\s+de))?\s+(.+)", re.IGNORECASE),
    re.compile(r"escribe\s+(?:un\s+)?post(?:\s+(?:sobre|para|de))?\s+(.+)", re.IGNORECASE),
    re.compile(r"crea\s+(?:un\s+)?post(?:\s+(?:sobre|para|de))?\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:un\s+)?post\s+(?:para|sobre|de)\s+(.+)", re.IGNORECASE),
    re.compile(r"redacta\s+(?:un\s+)?post\s+(.+)", re.IGNORECASE),
]

_POST_IDEAS_PATTERNS = [
    re.compile(r"ideas?\s+de\s+contenido", re.IGNORECASE),
    re.compile(r"qu[eé]\s+(?:puedo|podría|debería)\s+publicar", re.IGNORECASE),
    re.compile(r"ideas?\s+para\s+(?:un\s+)?post", re.IGNORECASE),
    re.compile(r"ideas?\s+para\s+linkedin", re.IGNORECASE),
    re.compile(r"qu[eé]\s+post(?:s)?\s+(?:puedo|hago|escribo)", re.IGNORECASE),
]

_POST_LIST_PATTERNS = [
    re.compile(r"\bmis\s+posts\b", re.IGNORECASE),
    re.compile(r"posts?\s+guardados?", re.IGNORECASE),
    re.compile(r"borradores?\s+(?:de\s+)?(?:post|contenido)", re.IGNORECASE),
    re.compile(r"ver\s+(?:mis\s+)?posts?", re.IGNORECASE),
    re.compile(r"contenido\s+guardado", re.IGNORECASE),
]

# Sector keyword mapping for NL generation
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "fisio": ["fisio", "fisioterapia", "fisioterapeuta", "fisioterapeutas"],
    "quiro": ["quiro", "quiropractica", "quiropráctica", "quiropráctico", "quiroprácticos"],
    "dental": ["dental", "dentista", "clínica dental", "clinica dental", "odontología"],
    "abogados": ["abogado", "abogados", "despacho", "legal", "abogacía"],
    "general": [],
}


def _extract_sector_from_text(text: str) -> str:
    """Extract sector keyword from NL text. Returns 'general' if no match."""
    text_lower = text.lower()
    for sector, keywords in _SECTOR_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return sector
    return "general"


def detect_content_intent(text: str) -> tuple[str, dict] | None:
    """
    Detect content-related intent in Spanish text.

    Returns:
        ("generate_post", {"sector": str}) — generate a LinkedIn post
        ("generate_ideas", {}) — generate content ideas
        ("list_drafts", {}) — list saved drafts
        None — no content intent detected
    """
    text = text.strip()

    # Check ideas first (before generate, to avoid "ideas de post para fisio" matching generate)
    for pattern in _POST_IDEAS_PATTERNS:
        if pattern.search(text):
            return ("generate_ideas", {})

    # Check list patterns
    for pattern in _POST_LIST_PATTERNS:
        if pattern.search(text):
            return ("list_drafts", {})

    # Check generate patterns — extract sector from matched group
    for pattern in _POST_GENERATE_PATTERNS:
        m = pattern.search(text)
        if m:
            matched_text = m.group(1).strip()
            sector = _extract_sector_from_text(matched_text)
            return ("generate_post", {"sector": sector})

    return None
