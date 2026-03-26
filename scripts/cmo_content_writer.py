"""
Duendes AIOS — CMO Content Writer Sub-Agent
Generates LinkedIn posts in Oscar's voice for target sectors.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("duendes-bot.cmo_content_writer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POST_FORMATS = {
    "historia": "Abre con anécdota real o situación reconocible. Desarrolla el problema. Cierra con insight accionable. Sin moraleja forzada.",
    "lista": "Título con número. 3-5 puntos concretos y accionables. Cada punto en 1-2 líneas. Cierre con pregunta o CTA.",
    "pregunta": "Abre con pregunta provocadora. Desarrolla el por qué importa. Cierra con tu perspectiva y pregunta al lector.",
    "dato": "Abre con estadística o dato sorprendente. Explica qué significa para el lector. Cierra con acción práctica.",
    "opinion": "Toma una posición clara. Argumenta en 2-3 puntos. Reconoce el contraargumento. Reafirma tu posición.",
}

SECTOR_ANGLES = {
    "fisio": "fisioterapeutas y quiroprácticos que pierden pacientes por no coger el teléfono durante las consultas",
    "dental": "clínicas dentales que pierden citas por no poder atender llamadas mientras tratan pacientes",
    "estetica": "centros de estética que pierden reservas fuera del horario de atención",
    "abogados": "despachos de abogados que necesitan filtrar consultas sin contratar recepcionista",
    "gestoria": "gestorías que reciben llamadas repetitivas de FAQs que podrían resolverse automáticamente",
    "general": "pequeños negocios de servicios que pierden clientes por no poder atender todas las llamadas",
}

# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------


async def generate_post(
    topic: str,
    sector: str,
    formato: str,
    anthropic_client: Any,
    voz_tono: str = "",
    context_os: str = "",
) -> str:
    """
    Generate a LinkedIn post in Oscar's voice.

    Args:
        topic: Subject/angle for the post
        sector: ICP sector key (fisio | dental | estetica | abogados | gestoria | general)
        formato: Post format key (historia | lista | pregunta | dato | opinion)
        anthropic_client: AsyncAnthropic instance
        voz_tono: Content of voz-tono.md (optional)
        context_os: Full context OS string (optional)

    Returns:
        Generated LinkedIn post text only, no preamble.
    """
    sector = sector.strip().lower() if sector else "general"
    if sector not in SECTOR_ANGLES:
        sector = "general"

    formato = formato.strip().lower() if formato else "historia"
    if formato not in POST_FORMATS:
        formato = "historia"

    sector_angle = SECTOR_ANGLES[sector]
    format_instructions = POST_FORMATS[formato]

    # Build system prompt
    system_parts = []

    if voz_tono:
        system_parts.append(voz_tono.strip())
    else:
        system_parts.append(
            "VOZ Y TONO DE OSCAR / DUENDES:\n"
            "- Ve al punto desde la primera frase. Sin introducciones vacías ni relleno.\n"
            "- Usa ejemplos concretos con números.\n"
            "- NO empieces con 'En el mundo actual...', 'Estoy emocionado de compartir...' ni similares.\n"
            "- NO uses hype tecnológico ('revolucionario', 'disruptivo', 'game-changer').\n"
            "- Español de España. Tuteo siempre. Frases cortas — punto y seguido antes que coma.\n"
            "- Sin signos de exclamación al final de cada frase.\n"
            "- La IA es una herramienta, no la revolución del universo.\n"
        )

    if context_os:
        system_parts.append(f"CONTEXTO DEL NEGOCIO:\n{context_os[:2000]}")

    system_parts.append(
        "Tu tarea es escribir posts de LinkedIn para Oscar Grana, fundador de Duendes. "
        "El contenido debe sonar EXACTAMENTE como Oscar — directo, concreto, sin florituras. "
        "Devuelve SOLO el texto del post. Sin preámbulos, sin 'aquí tienes tu post', sin comillas externas."
    )

    system = "\n\n---\n\n".join(system_parts)

    user_prompt = (
        f"Escribe un post de LinkedIn en primera persona como Oscar Grana.\n\n"
        f"TEMA: {topic if topic else 'agentes de voz para ' + sector_angle}\n\n"
        f"AUDIENCIA OBJETIVO: {sector_angle}\n\n"
        f"FORMATO A USAR ({formato.upper()}):\n{format_instructions}\n\n"
        f"RESTRICCIONES:\n"
        f"- Máximo 1300 caracteres\n"
        f"- Primera persona (yo, mi, nosotros)\n"
        f"- Español de España, tuteo\n"
        f"- Sin emojis o máximo 1 si encaja de forma natural\n"
        f"- Sin hashtags o máximo 2 al final si son muy relevantes\n"
        f"- Sin signos de exclamación en exceso\n"
        f"- Párrafos de 2-3 líneas como máximo\n\n"
        f"Devuelve SOLO el texto del post, sin ningún comentario adicional."
    )

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


async def generate_content_ideas(
    sector: str,
    n: int,
    anthropic_client: Any,
    context_os: str = "",
) -> str:
    """
    Generate n content ideas for a given sector.

    Args:
        sector: ICP sector key
        n: Number of ideas to generate
        anthropic_client: AsyncAnthropic instance
        context_os: Full context OS string (optional)

    Returns:
        Numbered list: "1. [title] — [one line description]"
    """
    sector = sector.strip().lower() if sector else "general"
    if sector not in SECTOR_ANGLES:
        sector = "general"

    sector_angle = SECTOR_ANGLES[sector]

    system = (
        "Eres el CMO de Duendes, agencia española de agentes de voz con IA. "
        "Generas ideas de contenido concretas y accionables para LinkedIn. "
        "Las ideas deben resonar con el ICP de Duendes: pequeños negocios españoles que pierden llamadas."
    )

    context_snippet = f"\n\nCONTEXTO DEL NEGOCIO:\n{context_os[:1500]}" if context_os else ""

    user_prompt = (
        f"Genera {n} ideas de posts de LinkedIn para Oscar Grana (Duendes).{context_snippet}\n\n"
        f"SECTOR OBJETIVO: {sector_angle}\n\n"
        f"REGLAS:\n"
        f"- Cada idea = título corto + descripción de 1 frase con el ángulo del post\n"
        f"- Mezcla: problema del ICP, historia/proceso de Oscar, concepto educativo sobre agentes de voz\n"
        f"- Concreto y específico. Sin ideas genéricas tipo 'habla de tus valores'\n"
        f"- En español de España\n\n"
        f"FORMATO (exactamente así):\n"
        f"1. [Título] — [descripción del ángulo en 1 frase]\n"
        f"2. [Título] — [descripción del ángulo en 1 frase]\n"
        f"...\n\n"
        f"Solo las ideas, sin explicaciones adicionales."
    )

    response = await anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_POST_KEYWORDS = re.compile(
    r"post|linkedin|escríbeme|escribeme|escribe|redacta|genera\s+un\s+post",
    re.IGNORECASE,
)
_IDEAS_KEYWORDS = re.compile(
    r"ideas?|temas?|qué\s+escribir|que\s+escribir|sobre\s+qué|sobre\s+que",
    re.IGNORECASE,
)
_SECTOR_MAP: dict[str, str] = {
    "fisio": "fisio",
    "fisioterapia": "fisio",
    "fisioterapeuta": "fisio",
    "dental": "dental",
    "dentist": "dental",
    "clínica dental": "dental",
    "clinica dental": "dental",
    "estética": "estetica",
    "estetica": "estetica",
    "estetic": "estetica",
    "belleza": "estetica",
    "abogad": "abogados",
    "despacho": "abogados",
    "gestor": "gestoria",
    "gestoría": "gestoria",
    "asesor": "gestoria",
}
_FORMAT_MAP: dict[str, str] = {
    "lista": "lista",
    "historia": "historia",
    "pregunta": "pregunta",
    "dato": "dato",
    "estadística": "dato",
    "estadistica": "dato",
    "opinión": "opinion",
    "opinion": "opinion",
}


def detect_content_intent(text: str) -> Optional[dict]:
    """
    Detect if message is asking for content generation.

    Returns a dict with keys action, topic, sector, formato — or None if no intent detected.
    """
    text_stripped = text.strip()

    # Detect action
    action: Optional[str] = None
    if _IDEAS_KEYWORDS.search(text_stripped):
        action = "ideas"
    elif _POST_KEYWORDS.search(text_stripped):
        action = "post"

    if action is None:
        return None

    # Detect sector
    text_lower = text_stripped.lower()
    sector = "general"
    for keyword, sector_key in _SECTOR_MAP.items():
        if keyword in text_lower:
            sector = sector_key
            break

    # Detect format (only relevant for post action)
    formato = "historia"
    for keyword, format_key in _FORMAT_MAP.items():
        if keyword in text_lower:
            formato = format_key
            break

    # Extract topic: everything after common trigger words
    topic = ""
    topic_match = re.search(
        r"(?:post|linkedin|escríbeme|escribeme|escribe|redacta|genera\s+un\s+post)\s+(?:un\s+post\s+)?(?:sobre|de|para|acerca\s+de)?\s*(.+)",
        text_stripped,
        re.IGNORECASE,
    )
    if topic_match:
        topic = topic_match.group(1).strip()

    return {
        "action": action,
        "topic": topic,
        "sector": sector,
        "formato": formato,
    }


# ---------------------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------------------


def format_post_response(post: str, sector: str, formato: str) -> str:
    """Format a generated post for Slack display."""
    return (
        f"*Post generado* ✍️\n"
        f"_Sector: {sector} | Formato: {formato}_\n\n"
        f"---\n"
        f"{post}\n"
        f"---\n\n"
        f"_¿Lo guardamos como borrador? Escribe `guardar` o `descartar`._"
    )


def format_ideas_response(ideas: str, sector: str) -> str:
    """Format a list of content ideas for Slack display."""
    return (
        f"*Ideas de contenido* 💡\n"
        f"_Sector: {sector}_\n\n"
        f"{ideas}\n\n"
        f"_Escribe el número de idea para desarrollarla en post._"
    )
