"""
Router /admin — endpoints internos para crons y tareas administrativas.

Protegido con header `X-Admin-Token` que debe coincidir con `ADMIN_TOKEN` env.
Usado por el cron n8n para, por cada campaña:
  1. POST /admin/import-campaign-leads  → trae al dialer los leads que ya
     recibieron email (solo campañas con import_source).
  2. POST /admin/sync-smartlead         → sincroniza Smartlead → Airtable Emails
     y marca No llamar en los unsubscribed / not-interested.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from config import get_settings
from deps import get_airtable
from services.airtable_multi import CAMPAIGNS, AirtableMultiClient
from services.despachos_import import DespachosImportError, import_sent_leads
from services.smartlead_sync import SmartleadSyncError, sync_campaign

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_token(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.admin_token
    if not expected:
        # Sin token configurado en env → endpoint abierto (modo dev)
        return
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token")


@router.post("/import-campaign-leads", dependencies=[Depends(_require_token)])
async def post_import_campaign_leads(
    campaign: Optional[str] = Query(
        default=None, description="slug de campaña; vacío = todas las que tengan import_source"
    ),
    air: AirtableMultiClient = Depends(get_airtable),
) -> dict[str, Any]:
    """Importa al dialer los leads que YA recibieron email. Idempotente."""
    settings = get_settings()
    slugs = (
        [campaign]
        if campaign
        else [s for s, c in CAMPAIGNS.items() if c.get("import_source")]
    )
    results: list[dict[str, Any]] = []
    for slug in slugs:
        if slug not in CAMPAIGNS:
            raise HTTPException(status_code=404, detail=f"Campaña desconocida: {slug}")
        try:
            res = await import_sent_leads(air, settings.smartlead_api_key, slug)
        except DespachosImportError as exc:
            raise HTTPException(status_code=502, detail=f"{slug}: {exc}")
        results.append(res)
    return {"ok": True, "imported": results}


@router.post("/sync-smartlead", dependencies=[Depends(_require_token)])
async def post_sync_smartlead(
    campaign: Optional[str] = Query(
        default=None, description="slug de campaña; vacío = todas"
    ),
) -> dict[str, Any]:
    """Sincroniza Smartlead → Airtable. Sin `campaign`, sincroniza todas. Idempotente."""
    settings = get_settings()
    slugs = [campaign] if campaign else list(CAMPAIGNS.keys())
    results: list[dict[str, Any]] = []
    for slug in slugs:
        cfg = CAMPAIGNS.get(slug)
        if not cfg:
            raise HTTPException(status_code=404, detail=f"Campaña desconocida: {slug}")
        try:
            res = await sync_campaign(
                smartlead_api_key=settings.smartlead_api_key,
                airtable_api_key=settings.airtable_api_key,
                campaign_id=cfg["smartlead_id"],
                campaign_name=cfg["label"],
            )
        except SmartleadSyncError as exc:
            raise HTTPException(status_code=502, detail=f"{slug}: {exc}")
        results.append({"campaign": slug, **res})
    return {"ok": True, "synced": results}
