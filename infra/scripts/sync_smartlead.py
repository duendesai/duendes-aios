#!/usr/bin/env python3
"""
Sync Smartlead → Airtable Emails (+ marca No llamar en malaga).

Idempotente: corre cuantas veces quieras, hace upsert por Smartlead stats_id.

Para cada email enviado por Smartlead:
  - Crea/actualiza row en tabla Emails con asunto, cuerpo, fechas, status
  - Si lead_category in (Not Interested, Do Not Contact) o is_unsubscribed:
    → marca No llamar = true en malaga (sale de la cola del dialer)

Uso: python3 infra/scripts/sync_smartlead.py [campaign_id]
Default campaign_id: 3368353 (Fisios Malaga May 26)
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# ─── Config ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"

# Carga .env raíz manualmente
env: dict[str, str] = {}
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

SMARTLEAD_API_KEY = env.get("SMARTLEAD_API_KEY", "")
AIRTABLE_API_KEY = env.get("AIRTABLE_API_KEY", "")
BASE_LUCIA = "app5WbiXR0qXGTc3r"
TABLE_MALAGA = "tblCyn7fjgBJM8rkF"
TABLE_EMAILS = "tblsOIzcXlleNjAat"
DEFAULT_CAMPAIGN_ID = 3368353

# Categorías Smartlead que indican "no llamar más" — sacar de la cola
CATEGORIES_DO_NOT_CALL = {3, 4}  # 3=Not Interested, 4=Do Not Contact
CATEGORY_NAMES = {
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

# ─── Helpers ───────────────────────────────────────────────────────────────────


def strip_html(html: str) -> str:
    """Convierte HTML a texto plano legible para guardar en Airtable."""
    if not html:
        return ""
    # Reemplaza <br> y </p>/<div> con saltos de línea antes de quitar tags
    txt = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    txt = re.sub(r"</(p|div|li|tr)>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    # Decodifica entidades comunes
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&#39;", "'"), ("&quot;", '"')):
        txt = txt.replace(ent, ch)
    # Colapsa saltos múltiples
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:5000]  # cap por si acaso


def derive_status(stat: dict[str, Any]) -> str:
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


def fmt_dt(s: str | None) -> str | None:
    if not s:
        return None
    # Smartlead devuelve "2026-05-21T07:41:56.000Z"
    return s


# ─── Airtable ──────────────────────────────────────────────────────────────────


def airtable(method: str, path: str, **kwargs) -> dict[str, Any]:
    url = f"https://api.airtable.com/v0/{BASE_LUCIA}/{path}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    for attempt in range(3):
        r = httpx.request(method, url, headers=headers, timeout=30, **kwargs)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {}


def airtable_list(table: str, **params) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = None
    while True:
        p = dict(params)
        if offset:
            p["offset"] = offset
        data = airtable("GET", table, params=p)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


# ─── Smartlead ─────────────────────────────────────────────────────────────────


def smartlead_stats(campaign_id: int) -> list[dict[str, Any]]:
    """Trae todos los stats (mensajes enviados) de la campaña."""
    url = f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics"
    out: list[dict[str, Any]] = []
    offset = 0
    limit = 100
    while True:
        r = httpx.get(url, params={"api_key": SMARTLEAD_API_KEY, "offset": offset, "limit": limit}, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("data", [])
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


# ─── Main sync ─────────────────────────────────────────────────────────────────


def main(campaign_id: int) -> None:
    if not SMARTLEAD_API_KEY or not AIRTABLE_API_KEY:
        sys.exit("Falta SMARTLEAD_API_KEY o AIRTABLE_API_KEY en .env raíz")

    print(f"▶ Smartlead campaign {campaign_id}: trayendo stats...")
    stats = smartlead_stats(campaign_id)
    print(f"  {len(stats)} emails enviados\n")

    print("▶ Airtable: mapeando malaga.Email contacto → record_id...")
    malaga_rows = airtable_list(
        TABLE_MALAGA,
        **{"filterByFormula": "AND({Email contacto}!='')"},
        **{"fields[]": "Email contacto"},
    )
    email_to_prospect: dict[str, str] = {}
    for r in malaga_rows:
        em = (r.get("fields", {}).get("Email contacto") or "").lower().strip()
        if em:
            email_to_prospect[em] = r["id"]
    print(f"  {len(email_to_prospect)} prospects con email contacto\n")

    print("▶ Airtable: mapeando Emails existentes por Smartlead Message ID / Email destino...")
    existing_emails = airtable_list(
        TABLE_EMAILS,
        **{"fields[]": "Smartlead Message ID"},
    )
    # También trae los emails por destino (los del CSV original que no tienen Smartlead Message ID)
    existing_emails_with_dest = airtable_list(
        TABLE_EMAILS,
        **{"fields[]": "Email destino"},
    )
    by_smartlead_id: dict[str, str] = {}
    for r in existing_emails:
        sid = (r.get("fields", {}).get("Smartlead Message ID") or "").strip()
        if sid:
            by_smartlead_id[sid] = r["id"]

    by_email_destino: dict[str, list[str]] = {}
    for r in existing_emails_with_dest:
        ed = (r.get("fields", {}).get("Email destino") or "").lower().strip()
        if ed:
            by_email_destino.setdefault(ed, []).append(r["id"])

    print(f"  {len(by_smartlead_id)} con Smartlead Message ID, {len(by_email_destino)} por destino\n")

    # ─── Procesar cada email ──────────────────────────────────────────────────
    created = updated = orphan = 0
    do_not_call_prospects: list[tuple[str, str, str]] = []  # (prospect_id, email, motivo)

    for stat in stats:
        email = (stat.get("lead_email") or "").lower().strip()
        stats_id = stat.get("stats_id") or ""
        category = stat.get("lead_category")
        status = derive_status(stat)

        prospect_id = email_to_prospect.get(email)
        existing_id = by_smartlead_id.get(stats_id)
        # Si no tiene Smartlead Message ID pero hay un row de CSV con mismo email, lo "adoptamos"
        if not existing_id and not stats_id:
            pass
        if not existing_id:
            adopt_ids = by_email_destino.get(email, [])
            # Adoptamos solo si esa row NO tiene Smartlead Message ID ya
            for aid in adopt_ids:
                # Es del CSV → la actualizamos con stats_id
                if aid not in by_smartlead_id.values():
                    existing_id = aid
                    break

        fields: dict[str, Any] = {
            "Smartlead Message ID": stats_id,
            "Smartlead Campaign ID": campaign_id,
            "Email destino": stat.get("lead_email"),
            "Asunto": stat.get("email_subject") or "",
            "Cuerpo": strip_html(stat.get("email_message") or ""),
            "Fecha envío": fmt_dt(stat.get("sent_time")),
            "Status": status,
            "Campaign": "Fisios Malaga May 26",
        }
        if stat.get("open_time"):
            fields["Fecha apertura"] = fmt_dt(stat.get("open_time"))
        if stat.get("reply_time"):
            fields["Fecha respuesta"] = fmt_dt(stat.get("reply_time"))
        if prospect_id:
            fields["Prospect"] = [prospect_id]

        body = {"fields": {k: v for k, v in fields.items() if v is not None}, "typecast": True}

        if existing_id:
            airtable("PATCH", f"{TABLE_EMAILS}/{existing_id}", json=body)
            updated += 1
            by_smartlead_id[stats_id] = existing_id  # actualizar caché
        else:
            # Crear con Email ID derivado del stats_id
            body["fields"]["Email ID"] = f"SL-{stats_id[:12]}"
            airtable("POST", TABLE_EMAILS, json=body)
            created += 1

        if not prospect_id:
            orphan += 1

        # Detectar "no llamar"
        if prospect_id and (category in CATEGORIES_DO_NOT_CALL or stat.get("is_unsubscribed")):
            cat_name = CATEGORY_NAMES.get(category, "")
            motivo = "Unsubscribed" if stat.get("is_unsubscribed") else cat_name
            do_not_call_prospects.append((prospect_id, email, motivo))

    print(f"✓ Emails sincronizados: {created} creados, {updated} actualizados, {orphan} huérfanos (sin prospect en malaga)\n")

    # ─── Marcar No llamar ─────────────────────────────────────────────────────
    if do_not_call_prospects:
        print(f"▶ Marcando No llamar = true en {len(do_not_call_prospects)} prospects:")
        for pid, em, motivo in do_not_call_prospects:
            print(f"   · {em} → {motivo}")
            today = datetime.utcnow().strftime("%Y-%m-%d")
            airtable(
                "PATCH",
                f"{TABLE_MALAGA}/{pid}",
                json={
                    "fields": {
                        "No llamar": True,
                        "Estado": "No llamar",
                        "Motivo pérdida": "Otra" if motivo != "Unsubscribed" else "Robinson/DNC",
                        "Notas": f"Smartlead detectó '{motivo}' el {today}",
                    },
                    "typecast": True,
                },
            )
        print(f"✓ {len(do_not_call_prospects)} prospects fuera de la cola\n")
    else:
        print("▶ Sin prospects para marcar No llamar (ningún reply categorizado como negativo)\n")

    # ─── Breakdown final ──────────────────────────────────────────────────────
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for stat in stats:
        s = derive_status(stat)
        by_status[s] = by_status.get(s, 0) + 1
        if stat.get("lead_category"):
            cn = CATEGORY_NAMES.get(stat["lead_category"], str(stat["lead_category"]))
            by_category[cn] = by_category.get(cn, 0) + 1

    print("📊 Resumen de la campaña:")
    for s, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"   {s:14} {n}")
    if by_category:
        print("\n   Categorías detectadas por Smartlead AI:")
        for c, n in sorted(by_category.items(), key=lambda x: -x[1]):
            print(f"   · {c:30} {n}")


if __name__ == "__main__":
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAMPAIGN_ID
    main(cid)
