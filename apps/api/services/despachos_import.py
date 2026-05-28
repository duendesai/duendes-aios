"""Import recurrente de prospectos a la cola del dialer.

Para una campaña con `import_source` (p.ej. despachos-madrid), trae a la tabla
del dialer (`malaga`) los leads que YA recibieron email en Smartlead, copiando
su ficha desde la base de origen (cold-outreach "duendes OUTREACH"). Idempotente
por `Email contacto` — reejecutable sin duplicar.

Flujo recurrente (cron n8n), por campaña con import_source:
  import_sent_leads()  → crea prospectos en el dialer para los emails enviados
  sync_campaign()      → vincula los rows de Emails a esos prospectos
El warm-mode de la cola prioriza la ventana D+2..D+5, así que un lead recién
importado no se llama hasta que pasan ~2 días desde el envío del email.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from services.airtable_multi import (
    AirtableMultiClient,
    BASE_LUCIA,
    CAMPAIGNS,
    TABLE_MALAGA,
)
from services.smartlead_sync import _smartlead_stats

logger = logging.getLogger(__name__)


class DespachosImportError(Exception):
    pass


def _norm_city(raw: str | None) -> str | None:
    """Normaliza la ciudad para no crear opciones duplicadas en el singleSelect."""
    if not raw:
        return None
    if "madrid" in raw.strip().lower():
        return "Madrid"
    return raw.strip()


def _lead_to_prospect_fields(lead_fields: dict[str, Any], label: str) -> dict[str, Any]:
    """Mapea un row de duendes OUTREACH.Leads → fields de un prospecto del dialer."""
    notas_parts: list[str] = []
    if lead_fields.get("contact_role"):
        notas_parts.append(f"Rol: {lead_fields['contact_role']}")
    if lead_fields.get("notes"):
        notas_parts.append(str(lead_fields["notes"]))
    if lead_fields.get("linkedin_url"):
        notas_parts.append(f"LinkedIn: {lead_fields['linkedin_url']}")
    return {
        "title": (
            lead_fields.get("company_name")
            or lead_fields.get("contact_name")
            or "(sin nombre)"
        ),
        "phone": lead_fields.get("phone"),
        "city": _norm_city(lead_fields.get("city")),
        "categoryName": lead_fields.get("sector"),
        "website": lead_fields.get("website"),
        "Email contacto": lead_fields.get("email"),
        "Contacto nombre": lead_fields.get("contact_name"),
        "Notas": "\n".join(notas_parts) or None,
        "Campaña": label,
        "Estado": "Pendiente",
        "Intentos": 0,
        "Fuente": "Cold email",
    }


async def import_sent_leads(
    air: AirtableMultiClient,
    smartlead_api_key: str,
    campaign_slug: str,
) -> dict[str, Any]:
    """Trae al dialer los leads de `campaign_slug` que ya recibieron email."""
    cfg = CAMPAIGNS.get(campaign_slug)
    if not cfg:
        raise DespachosImportError(f"Campaña desconocida: {campaign_slug}")
    src = cfg.get("import_source")
    if not src:
        return {
            "ok": True,
            "campaign": campaign_slug,
            "skipped": True,
            "reason": "campaña sin import_source (sus prospectos ya viven en el dialer)",
            "created": 0,
        }
    if not smartlead_api_key:
        raise DespachosImportError("SMARTLEAD_API_KEY vacía")

    label = cfg["label"]
    smartlead_id = cfg["smartlead_id"]

    # 1. Emails ya enviados en Smartlead (sent_time presente)
    async with httpx.AsyncClient() as client:
        stats = await _smartlead_stats(client, smartlead_api_key, smartlead_id)
    sent_emails = {
        (s.get("lead_email") or "").lower().strip()
        for s in stats
        if s.get("sent_time")
    }
    sent_emails.discard("")
    if not sent_emails:
        return {"ok": True, "campaign": campaign_slug, "created": 0, "sent_emails": 0}

    # 2. Fichas de la base de origen (indexadas por email)
    src_records = await air.list_records(src["base_id"], src["table"], max_records=2000)
    leads_by_email: dict[str, dict[str, Any]] = {}
    for r in src_records:
        em = (r.get("fields", {}).get("email") or "").lower().strip()
        if em:
            leads_by_email[em] = r.get("fields", {})

    # 3. Emails ya presentes en el dialer (idempotencia)
    existing = await air.list_records(
        BASE_LUCIA, TABLE_MALAGA, fields=["Email contacto"], max_records=2000
    )
    in_dialer = {
        (r.get("fields", {}).get("Email contacto") or "").lower().strip()
        for r in existing
    }
    in_dialer.discard("")

    # 4. Crear los enviados que existen en origen y aún no están en el dialer
    created = 0
    skipped_no_lead = 0
    for em in sent_emails:
        if em in in_dialer:
            continue
        lead = leads_by_email.get(em)
        if not lead:
            skipped_no_lead += 1
            continue
        try:
            await air.create_record(
                BASE_LUCIA,
                TABLE_MALAGA,
                _lead_to_prospect_fields(lead, label),
                typecast=True,
            )
            created += 1
            in_dialer.add(em)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Import lead %s falló: %s", em, exc)

    result = {
        "ok": True,
        "campaign": campaign_slug,
        "sent_emails": len(sent_emails),
        "created": created,
        "already_in_dialer": len(sent_emails) - created - skipped_no_lead,
        "no_lead_in_source": skipped_no_lead,
    }
    logger.info("Import %s result: %s", campaign_slug, result)
    return result
