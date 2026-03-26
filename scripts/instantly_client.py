"""
Duendes AIOS — Instantly Email Outreach Module
Pushes qualified leads from Airtable to Instantly campaigns.

Instantly API v2: https://api.instantly.ai/api/v2
Auth: Bearer token (INSTANTLY_API_KEY)

Workflow:
  Lead en Airtable (Estado=Cualificado)
    → /push <lead_id>
    → generate_cold_email (sdr_leads.py)
    → add_lead_to_campaign (instantly)
    → update lead Estado=Enviado en Airtable
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("duendes-aios.instantly")

INSTANTLY_API_KEY: str = os.getenv("INSTANTLY_API_KEY", "")
INSTANTLY_BASE = "https://api.instantly.ai/api/v2"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Campaign:
    id: str
    name: str
    status: int  # 1=active, 0=paused

    @property
    def is_active(self) -> bool:
        return self.status == 1

    def __str__(self) -> str:
        estado = "activa" if self.is_active else "pausada"
        return f"{self.name} ({estado})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    if not INSTANTLY_API_KEY:
        raise ValueError("INSTANTLY_API_KEY no configurada en .env")
    return {
        "Authorization": f"Bearer {INSTANTLY_API_KEY}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

async def list_campaigns() -> list[Campaign]:
    """Return all Instantly campaigns."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{INSTANTLY_BASE}/campaigns",
            headers=_headers(),
            params={"limit": 50},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [Campaign(id=c["id"], name=c["name"], status=c.get("status", 0)) for c in items]


def list_campaigns_sync() -> list[Campaign]:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{INSTANTLY_BASE}/campaigns",
            headers=_headers(),
            params={"limit": 50},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [Campaign(id=c["id"], name=c["name"], status=c.get("status", 0)) for c in items]


# ---------------------------------------------------------------------------
# Lead management
# ---------------------------------------------------------------------------

async def add_lead_to_campaign(
    campaign_id: str,
    email: str,
    empresa: str,
    asunto: str,
    cuerpo: str,
    first_name: str = "",
    phone: str = "",
) -> dict:
    """
    Add a lead to an Instantly campaign with personalized email variables.
    Variables {{asunto_mail}} and {{cuerpo_mail}} are injected into the sequence.
    """
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "email": email,
        "variables": {
            "asunto_mail": asunto,
            "cuerpo_mail": cuerpo,
        },
        "personalization": empresa,
    }
    if first_name:
        payload["first_name"] = first_name
    if phone:
        payload["phone"] = phone

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{INSTANTLY_BASE}/leads",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def get_campaign_analytics(campaign_id: str) -> dict:
    """Return analytics summary for a campaign."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{INSTANTLY_BASE}/campaigns/{campaign_id}/analytics/overview",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_campaigns(campaigns: list[Campaign]) -> str:
    if not campaigns:
        return "No hay campañas en Instantly."
    lines = ["*Campañas Instantly*\n"]
    for i, c in enumerate(campaigns, 1):
        emoji = "🟢" if c.is_active else "⏸️"
        lines.append(f"{emoji} #{i} {c.name}")
    return "\n".join(lines)


def format_lead_pushed(empresa: str, campaign_name: str) -> str:
    return f"Lead añadido a Instantly: *{empresa}* → campaña *{campaign_name}*"
