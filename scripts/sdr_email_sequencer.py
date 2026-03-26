"""
Duendes AIOS — SDR Email Sequencer Sub-Agent
Generates follow-up email sequences for leads that haven't responded.
3-email sequence: follow-up → value add → breakup.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailSequence:
    lead_empresa: str
    sector: str
    emails: list  # list of dicts: {n, asunto, cuerpo, dia}


SEQUENCE_TEMPLATES = [
    {
        "n": 1,
        "dia": 3,
        "tipo": "follow-up suave",
        "instruccion": "Recordatorio breve del email anterior. No seas insistente. Ofrece un ángulo diferente o una pregunta concreta. Máximo 4 líneas.",
    },
    {
        "n": 2,
        "dia": 7,
        "tipo": "valor añadido",
        "instruccion": "Comparte algo útil (dato, insight, caso de uso) relevante para su sector. Luego conecta con cómo Duendes lo resuelve. Máximo 5 líneas.",
    },
    {
        "n": 3,
        "dia": 14,
        "tipo": "breakup email",
        "instruccion": "Email de cierre. Deja la puerta abierta sin presionar. Tono humano y directo. Máximo 3 líneas. Clásico breakup: 'entiendo que no es el momento...'",
    },
]


async def generate_sequence(
    lead_empresa: str,
    sector: str,
    primer_email_asunto: str,
    primer_email_cuerpo: str,
    anthropic_client,
    context_os: str = "",
) -> EmailSequence:
    """
    Generates a 3-email follow-up sequence after an initial outreach.
    For each template in SEQUENCE_TEMPLATES, makes one Claude (Sonnet) call.
    Returns an EmailSequence with all 3 emails.
    """
    system_prompt = (
        "Eres un experto SDR B2B que escribe secuencias de follow-up en español de España. "
        "Escribes emails de prospección para Duendes AIOS, una agencia de automatización "
        "e inteligencia artificial para pequeños negocios y profesionales. "
        "El tono es humano, directo, sin florituras, sin palabras corporativas vacías. "
        "Nunca uses signos de exclamación en exceso. Nunca suenes como un vendedor agresivo. "
        "Tutea siempre. Frases cortas. Ve al punto desde la primera línea. "
        f"{context_os}"
    )

    emails = []
    for template in SEQUENCE_TEMPLATES:
        user_prompt = (
            f"Empresa objetivo: {lead_empresa}\n"
            f"Sector: {sector}\n"
            f"Email inicial enviado:\n"
            f"  Asunto: {primer_email_asunto}\n"
            f"  Cuerpo: {primer_email_cuerpo}\n\n"
            f"Tipo de email a generar: {template['tipo']}\n"
            f"Instrucciones: {template['instruccion']}\n\n"
            "Devuelve ÚNICAMENTE un JSON válido con esta estructura:\n"
            '{"asunto": "...", "cuerpo": "..."}\n'
            "Sin texto adicional, sin markdown, solo el JSON."
        )

        try:
            response = await anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            data = json.loads(raw)
            asunto = data.get("asunto", f"Re: {lead_empresa} — seguimiento #{template['n']}")
            cuerpo = data.get("cuerpo", "")
        except Exception:
            asunto = f"Re: {lead_empresa} — seguimiento #{template['n']}"
            cuerpo = "Quería retomar el contacto por si tienes un momento esta semana."

        emails.append(
            {
                "n": template["n"],
                "dia": template["dia"],
                "asunto": asunto,
                "cuerpo": cuerpo,
            }
        )

    return EmailSequence(lead_empresa=lead_empresa, sector=sector, emails=emails)


async def generate_quick_followup(
    lead_empresa: str,
    sector: str,
    dias_sin_respuesta: int,
    anthropic_client,
    context_os: str = "",
) -> dict:
    """
    Single follow-up email for when Oscar says 'no ha respondido [empresa]'.
    Adapts tone based on dias_sin_respuesta:
      <7  → follow-up suave
      7-14 → valor añadido
      >14  → breakup email
    Returns {"asunto": "...", "cuerpo": "..."}.
    """
    if dias_sin_respuesta < 7:
        tipo = "follow-up suave"
        instruccion = (
            "Recordatorio breve. No seas insistente. "
            "Ofrece un ángulo diferente o una pregunta concreta. Máximo 4 líneas."
        )
    elif dias_sin_respuesta <= 14:
        tipo = "valor añadido"
        instruccion = (
            "Comparte algo útil (dato, insight, caso de uso) relevante para su sector. "
            "Luego conecta con cómo Duendes lo resuelve. Máximo 5 líneas."
        )
    else:
        tipo = "breakup email"
        instruccion = (
            "Email de cierre. Deja la puerta abierta sin presionar. "
            "Tono humano y directo. Máximo 3 líneas. "
            "Clásico breakup: 'entiendo que no es el momento...'"
        )

    system_prompt = (
        "Eres un experto SDR B2B que escribe emails de follow-up en español de España. "
        "Escribes emails de prospección para Duendes AIOS, una agencia de automatización "
        "e inteligencia artificial para pequeños negocios y profesionales. "
        "El tono es humano, directo, sin florituras, sin palabras corporativas vacías. "
        "Tutea siempre. Frases cortas. Ve al punto desde la primera línea. "
        f"{context_os}"
    )

    user_prompt = (
        f"Empresa objetivo: {lead_empresa}\n"
        f"Sector: {sector}\n"
        f"Días sin respuesta: {dias_sin_respuesta}\n"
        f"Tipo de email: {tipo}\n"
        f"Instrucciones: {instruccion}\n\n"
        "Devuelve ÚNICAMENTE un JSON válido con esta estructura:\n"
        '{"asunto": "...", "cuerpo": "..."}\n'
        "Sin texto adicional, sin markdown, solo el JSON."
    )

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(raw)
        return {
            "asunto": data.get("asunto", f"Re: {lead_empresa}"),
            "cuerpo": data.get("cuerpo", ""),
        }
    except Exception:
        return {
            "asunto": f"Re: {lead_empresa}",
            "cuerpo": "Quería retomar el contacto por si tienes un momento esta semana.",
        }


def detect_sequence_intent(text: str) -> Optional[dict]:
    """
    Detect follow-up/sequence requests from Slack messages.

    Returns a dict with:
      - action: "sequence" | "followup"
      - empresa: extracted company name (or "")
      - dias: days without response (default 3)
      - sector: detected sector (default "general")

    Returns None if no sequence/follow-up intent is detected.
    """
    text_lower = text.lower()

    # Determine action
    sequence_keywords = ["secuencia", "follow-up", "followup", "seguimiento"]
    followup_keywords = ["no ha respondido", "no responde", "sin respuesta", "no contesta"]

    action = None
    for kw in sequence_keywords:
        if kw in text_lower:
            action = "sequence"
            break
    if action is None:
        for kw in followup_keywords:
            if kw in text_lower:
                action = "followup"
                break

    if action is None:
        return None

    # Extract days without response
    dias = 3
    match_dos_semanas = re.search(r"dos\s+semanas|2\s+semanas", text_lower)
    match_semana = re.search(r"\bsemana\b", text_lower)
    match_dias = re.search(r"hace\s+(\d+)\s+d[ií]as?", text_lower)
    match_lleva = re.search(r"lleva\s+(\d+)\s+d[ií]as?", text_lower)

    if match_dos_semanas:
        dias = 14
    elif match_dias:
        dias = int(match_dias.group(1))
    elif match_lleva:
        dias = int(match_lleva.group(1))
    elif match_semana:
        dias = 7

    # Extract company name — capitalised word(s) near trigger keywords
    empresa = ""
    empresa_patterns = [
        # "secuencia/seguimiento/follow-up para/de/con <Empresa>"
        r"(?:secuencia|seguimiento|follow-?up)\s+(?:para|de|con)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+)*)",
        # "secuencia/seguimiento/follow-up <Empresa>"
        r"(?:secuencia|seguimiento|follow-?up)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+)*)",
        # "<Empresa> no ha respondido / no responde / ..."
        r"([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+)*)\s+(?:no ha respondido|no responde|sin respuesta|no contesta)",
    ]
    for pattern in empresa_patterns:
        m = re.search(pattern, text)
        if m:
            empresa = m.group(1).strip()
            break

    # Detect sector from common keywords
    sector = "general"
    sector_map = [
        ("clínica dental", "dental"),
        ("dental", "dental"),
        ("fisio", "fisioterapia"),
        ("quiropráctic", "fisioterapia"),
        ("clínica", "salud"),
        ("médico", "salud"),
        ("salud", "salud"),
        ("farmacia", "salud"),
        ("estética", "estética"),
        ("belleza", "estética"),
        ("abogado", "legal"),
        ("bufete", "legal"),
        ("legal", "legal"),
        ("gestoría", "gestoría"),
        ("gestoria", "gestoría"),
        ("asesoría", "gestoría"),
        ("restaurante", "hostelería"),
        ("hotel", "hostelería"),
        ("hostelería", "hostelería"),
        ("retail", "retail"),
        ("tienda", "retail"),
        ("ecommerce", "ecommerce"),
        ("inmobiliaria", "inmobiliario"),
        ("inmobiliario", "inmobiliario"),
        ("marketing", "marketing"),
        ("agencia", "agencia"),
        ("logística", "logística"),
        ("transporte", "logística"),
        ("consultoría", "consultoría"),
        ("consultor", "consultoría"),
        ("tecnología", "tecnología"),
        ("software", "tecnología"),
        ("saas", "tecnología"),
        ("fontanero", "oficios"),
        ("electricista", "oficios"),
        ("reformas", "oficios"),
        ("oficios", "oficios"),
    ]
    for kw, sec in sector_map:
        if kw in text_lower:
            sector = sec
            break

    return {
        "action": action,
        "empresa": empresa,
        "dias": dias,
        "sector": sector,
    }


def format_sequence_response(seq: EmailSequence) -> str:
    """Slack-formatted output for a full 3-email sequence."""
    lines = [
        "*Secuencia de follow-up* 📧",
        f"*{seq.lead_empresa}* — {seq.sector}",
        "",
    ]
    for email in seq.emails:
        lines.append(f"*Email {email['n']} (día {email['dia']}):*")
        lines.append(f"Asunto: {email['asunto']}")
        lines.append(email["cuerpo"])
        lines.append("")

    lines.append("_¿La guardamos en las notas del lead?_")
    return "\n".join(lines)


def format_followup_response(email: dict, empresa: str) -> str:
    """Single follow-up Slack format."""
    return (
        f"*Follow-up generado* 📩\n"
        f"Para: *{empresa}*\n\n"
        f"Asunto: {email['asunto']}\n"
        f"{email['cuerpo']}\n\n"
        f"_¿Lo añadimos a Instantly?_"
    )
