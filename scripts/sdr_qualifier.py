"""
Duendes AIOS — SDR Lead Qualifier
Scores leads against ICP and BANT criteria. Ranks Nuevo leads for outreach priority.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("duendes-bot.sdr_qualifier")

# ---------------------------------------------------------------------------
# ICP context (hardcoded — extracted from context/clientes-ideales.md)
# ---------------------------------------------------------------------------

ICP_CONTEXT = (
    "ICP Duendes — Sectores prioritarios: Fisioterapia/Quiropráctica (#1), "
    "Clínica Dental (#2), Centro de Estética (#3), Bufete/Legal (#4), "
    "Gestoría (#5), Oficios/Servicios (#6).\n"
    "Perfil ideal: 1-5 empleados, sin recepcionista a tiempo completo, "
    "pierde llamadas/citas por no poder atender el teléfono.\n"
    "Presupuesto: €150-400/mes. Decisión: dueño solo, decide rápido.\n"
    "Anti-ICP: empresa grande con call center, contento con recepcionista, "
    "solo online, proceso muy complejo."
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class QualificationResult:
    lead_id: str
    empresa: str
    sector: str
    score: int           # 0-10
    icp_match: bool      # score >= 6
    razon: str           # 2-3 lines explaining score
    accion: str          # contactar_ya | contactar_pronto | investigar_mas | descartar
    prioridad: int       # 1=alta, 2=media, 3=baja


# ---------------------------------------------------------------------------
# Core qualification function
# ---------------------------------------------------------------------------

async def qualify_lead(
    lead: Any,
    anthropic_client: Any,
    extra_system: str = "",
) -> QualificationResult:
    """
    Score a single lead against ICP using Claude Haiku (fast + cheap).
    Returns a QualificationResult dataclass.
    """
    system = (
        "Eres un cualificador de leads B2B para Duendes, empresa española que vende "
        "agentes de voz con IA a pequeñas empresas.\n\n"
        f"{ICP_CONTEXT}\n\n"
    )
    if extra_system:
        system = f"{system}\n---\n{extra_system}\n\n---\n\n"

    system += (
        "Evalúa el lead y devuelve ÚNICAMENTE JSON válido, sin texto adicional:\n"
        '{"score": <0-10>, "icp_match": <true|false>, '
        '"razon": "<2-3 líneas>", "accion": "<contactar_ya|contactar_pronto|investigar_mas|descartar>", '
        '"prioridad": <1|2|3>}\n\n'
        "Criterios de score:\n"
        "8-10: Sector prioritario, tamaño ideal (1-5 empleados), señales de problema claro.\n"
        "6-7: Sector secundario o sector primario sin confirmar tamaño.\n"
        "4-5: Sector no en ICP pero podría encajar, o info insuficiente.\n"
        "0-3: Anti-ICP (empresa grande, call center, solo online, fuera de España, competidor).\n\n"
        "Mapeo de accion según score: 7-10→contactar_ya, 5-6→contactar_pronto, "
        "3-4→investigar_mas, 0-2→descartar.\n"
        "Mapeo de prioridad: score 7-10→1, score 4-6→2, score 0-3→3."
    )

    notas_snippet = (lead.notas[:300] if lead.notas else "Sin notas")
    user_message = (
        f"Lead a evaluar:\n"
        f"- Empresa: {lead.nombre}\n"
        f"- Sector: {lead.sector}\n"
        f"- Ciudad: {lead.ciudad or 'desconocida'}\n"
        f"- Notas: {notas_snippet}"
    )

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        score = int(data.get("score", 5))
        icp_match = bool(data.get("icp_match", score >= 6))
        razon = str(data.get("razon", "Sin análisis disponible."))
        accion = str(data.get("accion", "investigar_mas"))
        prioridad = int(data.get("prioridad", 2))

        # Validate accion
        valid_acciones = {"contactar_ya", "contactar_pronto", "investigar_mas", "descartar"}
        if accion not in valid_acciones:
            accion = "investigar_mas"

        return QualificationResult(
            lead_id=lead.id,
            empresa=lead.nombre,
            sector=lead.sector,
            score=max(0, min(10, score)),
            icp_match=icp_match,
            razon=razon,
            accion=accion,
            prioridad=max(1, min(3, prioridad)),
        )

    except Exception as exc:
        logger.warning("qualify_lead failed for %s: %s — using fallback", lead.nombre, exc)
        return QualificationResult(
            lead_id=lead.id,
            empresa=lead.nombre,
            sector=lead.sector,
            score=5,
            icp_match=True,
            razon="No se pudo analizar",
            accion="investigar_mas",
            prioridad=2,
        )


# ---------------------------------------------------------------------------
# Batch qualification
# ---------------------------------------------------------------------------

async def qualify_leads_batch(
    leads: list,
    anthropic_client: Any,
    extra_system: str = "",
) -> list[QualificationResult]:
    """
    Qualify all leads concurrently using asyncio.gather.
    Returns results sorted by score descending.
    """
    tasks = [qualify_lead(lead, anthropic_client, extra_system) for lead in leads]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    qualified: list[QualificationResult] = []
    for lead, result in zip(leads, results):
        if isinstance(result, Exception):
            logger.error("Error qualifying lead %s: %s", lead.nombre, result)
            qualified.append(QualificationResult(
                lead_id=lead.id,
                empresa=lead.nombre,
                sector=lead.sector,
                score=5,
                icp_match=True,
                razon="No se pudo analizar",
                accion="investigar_mas",
                prioridad=2,
            ))
        else:
            qualified.append(result)

    qualified_sorted = sorted(qualified, key=lambda r: r.score, reverse=True)

    # Cross-dept automations — notify for high-scoring leads
    try:
        from cross_dept import on_lead_qualified
        for result in qualified_sorted:
            if result.score >= 7:
                asyncio.create_task(on_lead_qualified(result.empresa, result.sector, result.score))
    except Exception:
        pass

    return qualified_sorted


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_qualification_report(results: list[QualificationResult]) -> str:
    """
    Returns a Telegram Markdown string with leads grouped by accion.
    Shows max 15 leads total.
    """
    if not results:
        return "No hay leads para calificar."

    groups: dict[str, list[QualificationResult]] = {
        "contactar_ya": [],
        "contactar_pronto": [],
        "investigar_mas": [],
        "descartar": [],
    }
    shown = 0
    for result in results:
        if shown >= 15:
            break
        groups[result.accion].append(result)
        shown += 1

    sections = [
        ("contactar_ya",    "🔴", "Contactar ya"),
        ("contactar_pronto","🟡", "Contactar pronto"),
        ("investigar_mas",  "⚪", "Investigar más"),
        ("descartar",       "❌", "Descartar"),
    ]

    lines = ["*Qualificación de Leads* 🎯\n"]

    # Build a display index across all groups
    display_index = {r.lead_id: i for i, r in enumerate(results[:15], 1)}

    for accion_key, emoji, label in sections:
        group = groups[accion_key]
        if not group:
            continue
        lines.append(f"{emoji} *{label}*")
        for result in group:
            display_id = display_index.get(result.lead_id, "?")
            sector_display = result.sector.capitalize() if result.sector else "Otro"
            lines.append(
                f"#{display_id} {result.empresa} — {sector_display} — {result.score}/10"
            )
            # Show first line of razon as italic hint
            razon_short = result.razon.split("\n")[0][:80]
            lines.append(f"_{razon_short}_")
        lines.append("")

    total = len(results)
    shown_count = min(total, 15)
    if total > 15:
        lines.append(f"_Mostrando {shown_count} de {total} leads._")

    return "\n".join(lines).rstrip()


def format_single_qualification(result: QualificationResult, display_id: int) -> str:
    """
    Detailed view for one qualified lead.
    """
    accion_label = {
        "contactar_ya":    "🔴 Contactar ya",
        "contactar_pronto":"🟡 Contactar pronto",
        "investigar_mas":  "⚪ Investigar más",
        "descartar":       "❌ Descartar",
    }.get(result.accion, result.accion)

    sector_display = result.sector.capitalize() if result.sector else "Otro"
    icp_label = "Sí" if result.icp_match else "No"

    lines = [
        f"*Lead #{display_id} — {result.empresa}*",
        f"Sector: {sector_display}",
        f"Score: {result.score}/10 | ICP match: {icp_label}",
        f"\nAnálisis:\n{result.razon}",
        f"\nAcción recomendada: {accion_label}",
    ]
    return "\n".join(lines)
