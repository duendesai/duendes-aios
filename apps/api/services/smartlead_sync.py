"""
Sync Smartlead → Airtable Emails (+ marca No llamar en malaga).

Idempotente: corre cuantas veces quieras, hace upsert por Smartlead stats_id.
Complementa el webhook en tiempo real — el cron horario captura los eventos
que se pudieran perder.

Para cada email enviado por Smartlead:
  - Upsert row en tabla Emails (Asunto, Cuerpo, fechas, status)
  - Si lead_category ∈ (Not Interested, Do Not Contact) o is_unsubscribed:
    → marca No llamar = true en malaga
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from services.crm.models import option_value
from services.prospecto_twenty import TwentyProspectoClient

logger = logging.getLogger(__name__)

# Categorías Smartlead que indican "no llamar más"
CATEGORIES_DO_NOT_CALL = {3, 4}  # Not Interested, Do Not Contact
CATEGORY_NAMES: dict[int, str] = {
    1: "Interested",
    2: "Meeting Request",
    3: "Not Interested",
    4: "Do Not Contact",
    5: "Information Request",
    6: "Out Of Office",
    7: "Wrong Person",
    8: "Uncategorizable by Ai",
    9: "Sender Originated Bounce",
}

BASE_LUCIA = "app5WbiXR0qXGTc3r"
TABLE_MALAGA = "tblCyn7fjgBJM8rkF"
TABLE_EMAILS = "tblsOIzcXlleNjAat"

DEFAULT_CAMPAIGN_ID = 3368353  # Fisios Malaga May 26


class SmartleadSyncError(Exception):
    pass


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    txt = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    txt = re.sub(r"</(p|div|li|tr)>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    for ent, ch in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&#39;", "'"),
        ("&quot;", '"'),
    ):
        txt = txt.replace(ent, ch)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:5000]


def _derive_status(stat: dict[str, Any]) -> str:
    if stat.get("is_bounced"):
        return "bounced"
    if stat.get("is_unsubscribed"):
        return "unsubscribed"
    if stat.get("reply_time"):
        return "replied"
    if stat.get("click_time"):
        return "clicked"
    if stat.get("open_time"):
        return "opened"
    return "sent"


async def _airtable(
    client: httpx.AsyncClient,
    airtable_key: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
) -> dict[str, Any]:
    url = f"https://api.airtable.com/v0/{BASE_LUCIA}/{path}"
    headers = {"Authorization": f"Bearer {airtable_key}", "Content-Type": "application/json"}
    resp = await client.request(method, url, headers=headers, params=params, json=json, timeout=30)
    if resp.status_code >= 400:
        raise SmartleadSyncError(f"Airtable {method} {path} → {resp.status_code}: {resp.text[:300]}")
    return resp.json()


async def _airtable_list(
    client: httpx.AsyncClient, airtable_key: str, table: str, **params: Any
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        p = dict(params)
        if offset:
            p["offset"] = offset
        data = await _airtable(client, airtable_key, "GET", table, params=p)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


async def _smartlead_stats(
    client: httpx.AsyncClient, api_key: str, campaign_id: int
) -> list[dict[str, Any]]:
    url = f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics"
    out: list[dict[str, Any]] = []
    offset = 0
    limit = 100
    while True:
        r = await client.get(
            url,
            params={"api_key": api_key, "offset": offset, "limit": limit},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json().get("data", [])
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


async def sync_campaign(
    *,
    smartlead_api_key: str,
    airtable_api_key: str,
    campaign_id: int = DEFAULT_CAMPAIGN_ID,
    campaign_name: str = "Fisios Malaga May 26",
    dialer_backend: str = "airtable",
    prospecto_client: TwentyProspectoClient | None = None,
) -> dict[str, Any]:
    """Ejecuta el sync. Devuelve un dict con métricas para el log/respuesta.

    El upsert de la tabla `Emails` de Airtable NO cambia (queda pendiente decidir con
    Oscar si esa tabla sigue viva o se desactiva). Lo que sí sigue `dialer_backend` es
    el marcado de "No llamar" (opt-out de email), que es el paso con implicación de
    cumplimiento: en modo "twenty" el `noLlamar=true` va al `prospecto` de Twenty; en
    "airtable" (default) va a `malaga`, como hasta ahora.
    """
    if not smartlead_api_key:
        raise SmartleadSyncError("SMARTLEAD_API_KEY vacía")
    if not airtable_api_key:
        raise SmartleadSyncError("AIRTABLE_API_KEY vacía")
    if dialer_backend == "twenty" and prospecto_client is None:
        raise SmartleadSyncError(
            "dialer_backend='twenty' pero no se pasó prospecto_client"
        )

    started_at = datetime.now(timezone.utc)

    async with httpx.AsyncClient() as client:
        stats = await _smartlead_stats(client, smartlead_api_key, campaign_id)

        # Mapeo malaga.Email contacto → record_id
        malaga = await _airtable_list(
            client,
            airtable_api_key,
            TABLE_MALAGA,
            **{"filterByFormula": "{Email contacto}!=''", "fields[]": "Email contacto"},
        )
        email_to_prospect = {
            (r["fields"].get("Email contacto") or "").lower().strip(): r["id"]
            for r in malaga
            if r["fields"].get("Email contacto")
        }

        # Emails existentes
        existing = await _airtable_list(
            client,
            airtable_api_key,
            TABLE_EMAILS,
            **{"fields[]": ["Smartlead Message ID", "Email destino"]},
        )
        by_smartlead_id: dict[str, str] = {}
        by_email_destino: dict[str, list[str]] = {}
        for r in existing:
            sid = (r["fields"].get("Smartlead Message ID") or "").strip()
            if sid:
                by_smartlead_id[sid] = r["id"]
            ed = (r["fields"].get("Email destino") or "").lower().strip()
            if ed:
                by_email_destino.setdefault(ed, []).append(r["id"])

        created = updated = orphan = 0
        # (email, motivo): por EMAIL, no por record de Airtable, para que el marcado
        # funcione también en modo twenty (donde el id de malaga no aplica).
        do_not_call: list[tuple[str, str]] = []

        for stat in stats:
            email = (stat.get("lead_email") or "").lower().strip()
            stats_id = stat.get("stats_id") or ""
            category = stat.get("lead_category")
            status = _derive_status(stat)

            prospect_id = email_to_prospect.get(email)

            existing_id = by_smartlead_id.get(stats_id)
            if not existing_id:
                # Adoptar row del CSV original (sin Smartlead Message ID)
                for aid in by_email_destino.get(email, []):
                    if aid not in by_smartlead_id.values():
                        existing_id = aid
                        break

            fields: dict[str, Any] = {
                "Smartlead Message ID": stats_id,
                "Smartlead Campaign ID": campaign_id,
                "Email destino": stat.get("lead_email"),
                "Asunto": stat.get("email_subject") or "",
                "Cuerpo": _strip_html(stat.get("email_message")),
                "Fecha envío": stat.get("sent_time"),
                "Status": status,
                "Campaign": campaign_name,
            }
            if stat.get("open_time"):
                fields["Fecha apertura"] = stat["open_time"]
            if stat.get("reply_time"):
                fields["Fecha respuesta"] = stat["reply_time"]
            if prospect_id:
                fields["Prospect"] = [prospect_id]

            body = {
                "fields": {k: v for k, v in fields.items() if v is not None},
                "typecast": True,
            }

            if existing_id:
                await _airtable(
                    client, airtable_api_key, "PATCH", f"{TABLE_EMAILS}/{existing_id}", json=body
                )
                updated += 1
                if stats_id:
                    by_smartlead_id[stats_id] = existing_id
            else:
                body["fields"]["Email ID"] = f"SL-{stats_id[:12]}" if stats_id else f"SL-{int(datetime.now().timestamp())}"
                await _airtable(client, airtable_api_key, "POST", TABLE_EMAILS, json=body)
                created += 1

            if not prospect_id:
                orphan += 1

            if category in CATEGORIES_DO_NOT_CALL or stat.get("is_unsubscribed"):
                motivo = "Unsubscribed" if stat.get("is_unsubscribed") else CATEGORY_NAMES.get(category, "")
                do_not_call.append((email, motivo))

        # Marca No llamar en el backend activo del dialer
        marked = 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if dialer_backend == "twenty":
            # email → id del prospecto en Twenty
            tw_nodes = await prospecto_client.list_all()
            email_to_tw = {
                (n.get("email") or "").lower().strip(): n["id"]
                for n in tw_nodes
                if n.get("email")
            }
            for em, motivo in do_not_call:
                tw_id = email_to_tw.get(em)
                if not tw_id:
                    continue
                try:
                    await prospecto_client.update(
                        tw_id,
                        {
                            "noLlamar": True,
                            "estado": option_value("No llamar"),
                            "outcome": option_value("no_llamar"),
                            "motivoPerdida": "Robinson/DNC" if motivo == "Unsubscribed" else "Otra",
                            "notas": f"Smartlead detectó '{motivo}' el {today}",
                        },
                    )
                    marked += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Fallo marcando noLlamar en Twenty para %s: %s", em, exc)
        else:
            for em, motivo in do_not_call:
                pid = email_to_prospect.get(em)
                if not pid:
                    continue
                try:
                    await _airtable(
                        client,
                        airtable_api_key,
                        "PATCH",
                        f"{TABLE_MALAGA}/{pid}",
                        json={
                            "fields": {
                                "No llamar": True,
                                "Estado": "No llamar",
                                "Motivo pérdida": "Robinson/DNC" if motivo == "Unsubscribed" else "Otra",
                                "Notas": f"Smartlead detectó '{motivo}' el {today}",
                            },
                            "typecast": True,
                        },
                    )
                    marked += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Fallo marcando No llamar para %s: %s", em, exc)

        # Breakdown
        by_status: dict[str, int] = {}
        for s in stats:
            st = _derive_status(s)
            by_status[st] = by_status.get(st, 0) + 1

        result = {
            "ok": True,
            "campaign_id": campaign_id,
            "total_emails": len(stats),
            "created": created,
            "updated": updated,
            "orphans": orphan,
            "marked_no_llamar": marked,
            "by_status": by_status,
            "started_at": started_at.isoformat(),
            "duration_sec": (datetime.now(timezone.utc) - started_at).total_seconds(),
        }
        logger.info("Smartlead sync result: %s", result)
        return result
