"""
Duendes AIOS — Cross-Department Automations
Triggered when data changes in one department to notify/act in another.
All functions are fire-and-forget — never block or raise.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("duendes-bot.cross_dept")


async def on_deal_won(deal_empresa: str, deal_sector: str, deal_notas: str = "") -> None:
    """Deal ganado → crear cliente en CS + notificar."""
    try:
        from cs_clients import add_client
        from slack_notify import send_to_channel

        await add_client(
            nombre=deal_empresa,
            contacto="",
            sector=deal_sector,
            mrr=0.0,
        )
        send_to_channel(
            "clientes",
            f"🎉 Nuevo cliente: *{deal_empresa}* ({deal_sector}) — deal cerrado. Iniciar onboarding.",
        )
        send_to_channel(
            "orquestador",
            f"✅ Deal ganado: *{deal_empresa}* → creado en CS",
        )
    except Exception as exc:
        logger.warning("on_deal_won failed for %s: %s", deal_empresa, exc)


async def on_lead_responded(lead_empresa: str, lead_sector: str, lead_email: str = "") -> None:
    """Lead responde (contactado con interés) → notificar AE."""
    try:
        from slack_notify import send_to_channel

        send_to_channel(
            "ventas",
            f"🔥 Lead caliente: *{lead_empresa}* ({lead_sector}) ha respondido al outreach → considerar para demo",
        )
        send_to_channel(
            "captacion",
            f"✅ *{lead_empresa}* marcado como respondido",
        )
    except Exception as exc:
        logger.warning("on_lead_responded failed for %s: %s", lead_empresa, exc)


async def on_lead_qualified(lead_empresa: str, lead_sector: str, score: int) -> None:
    """Lead cualificado (score alto) → crear tarea en COO + notificar ventas."""
    if score < 7:
        return
    try:
        from coo_tasks import add_task
        from slack_notify import send_to_channel

        await add_task(
            title=f"Preparar demo para {lead_empresa} ({lead_sector}) — lead score {score}/10",
            priority="high",
            category="sales",
        )
        send_to_channel(
            "ventas",
            f"🎯 Lead cualificado: *{lead_empresa}* — score {score}/10. Tarea de demo creada en operaciones.",
        )
    except Exception as exc:
        logger.warning("on_lead_qualified failed for %s: %s", lead_empresa, exc)


async def on_deal_lost(deal_empresa: str, deal_sector: str) -> None:
    """Deal perdido → notificar SDR para prospección alternativa."""
    try:
        from slack_notify import send_to_channel

        send_to_channel(
            "captacion",
            f"ℹ️ Deal perdido: *{deal_empresa}* ({deal_sector}). ¿Hay leads alternativos en este sector?",
        )
    except Exception as exc:
        logger.warning("on_deal_lost failed for %s: %s", deal_empresa, exc)


async def on_invoice_overdue(empresa: str, importe: float, dias_vencida: int) -> None:
    """Factura vencida → notificar finanzas (real-time hook when manually marked overdue)."""
    try:
        from slack_notify import send_to_channel

        send_to_channel(
            "finanzas",
            f"⚠️ Factura vencida {dias_vencida} días: *{empresa}* — €{importe:.0f}",
        )
    except Exception as exc:
        logger.warning("on_invoice_overdue failed for %s: %s", empresa, exc)
