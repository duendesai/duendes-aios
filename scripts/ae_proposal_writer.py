"""
Duendes AIOS — AE Proposal Writer Sub-Agent
Generates commercial proposals tailored to each prospect's sector and situation.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROPOSAL_SECTIONS = [
    "situacion_actual",       # Their problem, framed in their words
    "solucion",               # How Duendes solves it specifically
    "como_funciona",          # Simple explanation of voice agent setup
    "resultados_esperados",   # ROI / outcomes for their sector
    "inversion",              # Pricing relevant to their profile
    "proximos_pasos",         # Clear 1-2-3 next steps
]

_FALLBACK_PRICING = (
    "**Inversión:**\n"
    "• Plan Esencial: 79€/mes + 199€ setup\n"
    "• Plan Profesional: 129€/mes + 299€ setup *(el más elegido)*\n"
    "• Plan Elite: 229€/mes + 499€ setup\n"
    "Sin permanencia. Pagas mes a mes."
)

# Sector keywords for detection
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "dental": ["dental", "dentista", "clínica dental", "clinica dental", "odontolog"],
    "fisioterapia": ["fisio", "fisioterapia", "fisioterapeuta", "quiropractic"],
    "estetica": ["estética", "estetica", "belleza", "spa", "centro de belleza", "peluquería", "peluqueria"],
    "abogados": ["abogado", "abogados", "despacho", "legal", "jurídico", "juridico"],
    "gestoria": ["gestoría", "gestoria", "asesoría", "asesoria", "contable", "fiscal"],
    "inmobiliaria": ["inmobiliaria", "inmobiliario", "agencia inmobiliaria", "pisos", "alquiler"],
    "restaurante": ["restaurante", "bar", "cafetería", "cafeteria", "hostelería", "hosteleria", "comida"],
    "taller": ["taller", "mecánico", "mecanico", "garage"],
    "fontanero": ["fontanero", "fontanería", "fontaneria", "electricista", "cerrajero", "electricidad", "pintor"],
    "clinica": ["clínica", "clinica", "médico", "medico", "salud", "consultorio"],
}


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

async def generate_proposal(
    empresa: str,
    sector: str,
    notas: str,
    anthropic_client: Any,
    ofertas_context: str = "",
    context_os: str = "",
) -> str:
    """Generate a tailored commercial proposal for a prospect."""
    pricing_block = ofertas_context.strip() if ofertas_context.strip() else _FALLBACK_PRICING

    system = (
        "Eres el AE (Account Executive) de Duendes, una agencia especializada en agentes de voz con IA "
        "para pequeños negocios en España. Vendes resultados de negocio, no tecnología.\n\n"
        "Tu misión: redactar propuestas comerciales claras, concretas y orientadas a conversión. "
        "Español de España. Sin florituras corporativas. Sin jerga técnica innecesaria.\n\n"
        "Usa el contexto de precios proporcionado para recomendar el plan más adecuado. "
        "Formatea la propuesta para Slack: usa **negrita** para los títulos de sección, "
        "sin headers markdown (#). Máximo 600 palabras."
    )

    user_prompt = f"""Redacta una propuesta comercial completa para este prospecto.

DATOS DEL PROSPECTO:
- Empresa: {empresa or 'Empresa del prospecto'}
- Sector: {sector or 'general'}
- Notas / contexto: {notas or 'Sin notas adicionales'}

PRECIOS Y PLANES DE DUENDES:
{pricing_block[:2000]}

ESTRUCTURA OBLIGATORIA (usa estas secciones en este orden, con el nombre en negrita):
1. **Situación actual** — Su problema real, en sus palabras, sin tecnicismos
2. **Lo que hace Duendes** — Solución concreta para su sector
3. **Cómo funciona** — Explicación simple del setup (máx. 3 líneas)
4. **Qué pueden esperar** — ROI y resultados concretos para su sector
5. **Inversión** — Plan recomendado con precios exactos
6. **Próximos pasos** — 1-2-3 acciones claras y simples

REGLAS:
- Personaliza para el sector "{sector or 'general'}" y la empresa "{empresa or 'el prospecto'}"
- Incluye el precio exacto del plan recomendado (setup + mensual)
- Sin permanencia → menciónalo en inversión
- Cierra con una CTA directa para agendar demo o llamada
- Máximo 600 palabras en total
- Todo en español de España"""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


async def generate_demo_prep(
    empresa: str,
    sector: str,
    notas: str,
    anthropic_client: Any,
    context_os: str = "",
) -> str:
    """Generate a demo preparation briefing for Oscar before a call."""
    system = (
        "Eres el coach de ventas de Oscar, fundador de Duendes (agentes de voz IA para pequeños negocios en España). "
        "Preparas briefings de demo concisos, prácticos y orientados al cierre. "
        "Español de España. Sin relleno. Formato Slack con **negrita** para secciones."
    )

    user_prompt = f"""Prepárame para la demo / llamada con este prospecto.

DATOS:
- Empresa: {empresa or 'Prospecto'}
- Sector: {sector or 'general'}
- Notas: {notas or 'Sin información adicional'}

CONTEXTO DE DUENDES:
{context_os[:1500] if context_os else '(sin contexto adicional)'}

ESTRUCTURA:
**Quiénes son y su pain probable**
(2-3 líneas: qué hacen, cuál es su dolor más probable)

**3 preguntas para arrancar**
(preguntas abiertas que revelan el pain real)

**Objeciones que van a poner**
(las 2-3 más probables para su sector + cómo responderlas en 1 línea)

**En qué enfocarte del producto**
(qué feature o beneficio tiene más impacto para su sector)

**Movimiento de cierre recomendado**
(qué proponer al final de la llamada para avanzar)

Todo en español de España. Directo y accionable."""

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_PROPOSAL_PATTERNS = [
    re.compile(r"\bpropuesta\b", re.IGNORECASE),
    re.compile(r"\bgenera\s+propuesta\b", re.IGNORECASE),
    re.compile(r"\bprepara\s+propuesta\b", re.IGNORECASE),
    re.compile(r"\bcrea\s+propuesta\b", re.IGNORECASE),
    re.compile(r"\bredacta\s+propuesta\b", re.IGNORECASE),
]

_DEMO_PREP_PATTERNS = [
    re.compile(r"\bprep[aá]rame\b", re.IGNORECASE),
    re.compile(r"\bpreparar\s+llamada\b", re.IGNORECASE),
    re.compile(r"\bprepara\s+para\b", re.IGNORECASE),
    re.compile(r"\bprep\s+demo\b", re.IGNORECASE),
    re.compile(r"\bpreparaci[oó]n\s+demo\b", re.IGNORECASE),
    re.compile(r"\bprepara\s+(?:la\s+)?demo\b", re.IGNORECASE),
    re.compile(r"\bprepara\s+(?:la\s+)?llamada\b", re.IGNORECASE),
]

# Patterns to extract company name after trigger words
_EMPRESA_PATTERNS = [
    re.compile(r"(?:propuesta|demo|llamada|prepara(?:me)?)\s+(?:para|de|con)\s+([A-ZÁÉÍÓÚÑ][^\s,\.]{1,40}(?:\s+[A-ZÁÉÍÓÚÑ][^\s,\.]{1,40}){0,3})", re.IGNORECASE),
    re.compile(r"para\s+([A-ZÁÉÍÓÚÑ][^\s,\.]{1,40}(?:\s+[A-ZÁÉÍÓÚÑ][^\s,\.]{1,40}){0,3})", re.IGNORECASE),
]


def _extract_empresa(text: str) -> str:
    """Extract a company name from the message text."""
    for pattern in _EMPRESA_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip()
            # Filter out common stop words that are not company names
            stop_words = {"el", "la", "los", "las", "un", "una", "una", "mi", "su", "su", "demo", "llamada", "propuesta"}
            if candidate.lower() not in stop_words and len(candidate) > 1:
                return candidate
    return ""


def _detect_sector(text: str) -> str:
    """Detect sector from text using keyword matching."""
    text_lower = text.lower()
    for sector, keywords in _SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return sector
    return "general"


def detect_proposal_intent(text: str) -> Optional[dict]:
    """
    Detect whether the message is asking for a proposal or demo prep.

    Returns a dict with keys: action, empresa, sector, notas
    or None if no intent detected.
    """
    text = text.strip()

    # Check for demo prep intent first (more specific)
    for pattern in _DEMO_PREP_PATTERNS:
        if pattern.search(text):
            return {
                "action": "demo_prep",
                "empresa": _extract_empresa(text),
                "sector": _detect_sector(text),
                "notas": text,
            }

    # Check for proposal intent
    for pattern in _PROPOSAL_PATTERNS:
        if pattern.search(text):
            return {
                "action": "proposal",
                "empresa": _extract_empresa(text),
                "sector": _detect_sector(text),
                "notas": text,
            }

    return None


# ---------------------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------------------

def format_proposal_response(proposal: str, empresa: str, sector: str) -> str:
    """Format a generated proposal for Slack."""
    cliente_label = empresa if empresa else "Prospecto"
    return (
        f"*Propuesta comercial* 📋\n"
        f"Cliente: *{cliente_label}* | Sector: {sector}\n\n"
        f"{proposal}\n\n"
        f"---\n"
        f"_¿La guardamos en el deal? Escribe `guardar` o ajusta lo que necesites._"
    )


def format_demo_prep_response(prep: str, empresa: str) -> str:
    """Format a demo prep briefing for Slack."""
    empresa_label = empresa if empresa else "Prospecto"
    return (
        f"*Preparación de demo* 🎯\n"
        f"*{empresa_label}*\n\n"
        f"{prep}"
    )
