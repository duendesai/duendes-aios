#!/usr/bin/env python3
"""
Carga la tanda diaria de leads en Smartlead para campaña Despachos Madrid (mayo 2026).

Hace, en orden:
  1. Carga pool de emails reescritos + log de enviados.
  2. Excluye los ya enviados/encolados + los marcados REVISAR + word_count > 160.
  3. Selecciona N leads con diversidad de register (tu/usted) y de subject.
  4. PATCH max_leads_per_day si el valor pedido difiere del actual.
  5. POST leads a Smartlead campaign.
  6. POST status START (la campaña queda COMPLETED cuando se queda sin leads).
  7. Actualiza enviados-log.csv local con tag EN_COLA_<dia>.

Uso:
    uv run python infra/scripts/load_smartlead_batch.py [N] [--dry-run]

Default N: 25.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"
CAMPAIGN_DIR = REPO_ROOT / "cold-outreach/campaigns/despachos-madrid-2026-05"
POOL_JSON = CAMPAIGN_DIR / "emails-reescritos.json"
LOG_CSV = CAMPAIGN_DIR / "enviados-log.csv"

CAMPAIGN_ID = 3404016
BASE_URL = "https://server.smartlead.ai/api/v1"
WORD_COUNT_MAX = 160

REVISAR_COMPANIES = {"abogado supralaboris", "ollé sesé abogados", "olle sese abogados"}

DAY_TAG_MAP = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes"}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def load_pool() -> list[dict]:
    return json.loads(POOL_JSON.read_text())


def load_log() -> tuple[list[dict], set[str]]:
    rows: list[dict] = []
    sent_emails: set[str] = set()
    with LOG_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            sent_emails.add(row["email"].strip().lower())
    return rows, sent_emails


def select_batch(candidates: list[dict], n: int) -> list[dict]:
    """Selecciona n leads maximizando diversidad de subject y respetando proporción register."""
    if len(candidates) <= n:
        return candidates

    by_subject_pattern: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        key = (c.get("email_subject", "")[:25]).lower().strip()
        by_subject_pattern[key].append(c)

    for k in by_subject_pattern:
        by_subject_pattern[k].sort(
            key=lambda x: (0 if x.get("register") == "tu" else 1, x["email"])
        )

    chosen: list[dict] = []
    chosen_emails: set[str] = set()
    patterns = sorted(by_subject_pattern.keys(), key=lambda k: -len(by_subject_pattern[k]))

    while len(chosen) < n:
        added_in_round = 0
        for p in patterns:
            bucket = by_subject_pattern[p]
            for c in bucket:
                if c["email"] not in chosen_emails:
                    chosen.append(c)
                    chosen_emails.add(c["email"])
                    added_in_round += 1
                    bucket.remove(c)
                    break
            if len(chosen) >= n:
                break
        if added_in_round == 0:
            break
    return chosen[:n]


def smartlead_get_campaign(api_key: str) -> dict:
    r = httpx.get(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}", params={"api_key": api_key}, timeout=30
    )
    r.raise_for_status()
    return r.json()


def smartlead_patch_settings(api_key: str, max_per_day: int) -> tuple[bool, str]:
    """Intenta varios endpoints/payloads. Devuelve (ok, detalle). NO lanza."""
    attempts = [
        ("/schedule", {"max_new_leads_per_day": max_per_day}),
        ("/settings", {"max_new_leads_per_day": max_per_day}),
        ("/settings", {"max_leads_per_day": max_per_day}),
        ("", {"max_leads_per_day": max_per_day}),
    ]
    last = ""
    for path, body in attempts:
        try:
            r = httpx.post(
                f"{BASE_URL}/campaigns/{CAMPAIGN_ID}{path}",
                params={"api_key": api_key},
                json=body,
                timeout=30,
            )
            if r.status_code < 400:
                return True, f"OK via POST {path} body={body}"
            last = f"POST {path} body={body} → {r.status_code} {r.text[:200]}"
        except Exception as e:
            last = f"POST {path} → {e}"
    return False, last


def smartlead_add_leads(api_key: str, leads: list[dict]) -> dict:
    r = httpx.post(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/leads",
        params={"api_key": api_key},
        json={"lead_list": leads},
        timeout=60,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"add_leads failed {r.status_code}: {r.text[:400]}")
    return r.json()


def smartlead_start(api_key: str) -> dict:
    r = httpx.post(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/status",
        params={"api_key": api_key},
        json={"status": "START"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"start failed {r.status_code}: {r.text[:400]}")
    return r.json()


def append_log(rows: list[dict], new_batch: list[dict], tag: str) -> None:
    existing = list(rows)
    fieldnames = ["email", "subject", "sent_time", "opened", "replied"]
    for lead in new_batch:
        existing.append({
            "email": lead["email"],
            "subject": lead["email_subject"],
            "sent_time": tag,
            "opened": "False",
            "replied": "False",
        })
    with LOG_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing)


def build_lead_payload(lead: dict) -> dict:
    return {
        "email": lead["email"],
        "first_name": "",
        "last_name": "",
        "company_name": lead.get("company_name", ""),
        "custom_fields": {
            "email_subject": lead["email_subject"],
            "email_body": lead["email_body"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("n", nargs="?", type=int, default=25, help="Leads a cargar")
    parser.add_argument("--dry-run", action="store_true", help="No llama Smartlead, solo previsualiza")
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("SMARTLEAD_API_KEY", "")
    if not api_key:
        print("ERROR: SMARTLEAD_API_KEY no encontrada en .env", file=sys.stderr)
        return 1

    pool = load_pool()
    log_rows, sent_emails = load_log()

    candidates = [
        p for p in pool
        if p["email"].strip().lower() not in sent_emails
        and (p.get("company_name", "").strip().lower() not in REVISAR_COMPANIES)
        and (p.get("word_count") or 0) <= WORD_COUNT_MAX
    ]

    register_dist = Counter(p.get("register") for p in candidates)
    print(f"Pool total: {len(pool)} | Enviados/encolados: {len(sent_emails)} | Candidatos elegibles: {len(candidates)}")
    print(f"  Register en candidatos: {dict(register_dist)}")

    batch = select_batch(candidates, args.n)
    print(f"\nBatch seleccionado ({len(batch)}):")
    b_reg = Counter(b.get("register") for b in batch)
    b_subj = Counter(b.get("email_subject", "")[:25].lower() for b in batch)
    print(f"  Register: {dict(b_reg)}")
    print(f"  Subjects únicos: {len(b_subj)}")
    for i, b in enumerate(batch, 1):
        print(f"  {i:2d}. [{b.get('register'):<5}] [{b.get('word_count'):>3} w] {b['email']:<45} → {b['email_subject']}")

    if args.dry_run:
        print("\n[DRY RUN] No se ha llamado a Smartlead. Salgo.")
        return 0

    camp = smartlead_get_campaign(api_key)
    cur_max = camp.get("max_leads_per_day", 0)
    cur_status = camp.get("status")
    print(f"\nCampaña Smartlead: status={cur_status}, max_leads_per_day={cur_max}")

    if cur_max != args.n:
        print(f"Intentando actualizar max_leads_per_day {cur_max} → {args.n}...")
        ok, detail = smartlead_patch_settings(api_key, args.n)
        if ok:
            print(f"  ✓ {detail}")
        else:
            print(f"  ⚠ No se pudo actualizar (no bloquea): {detail}")
            print(f"  ⚠ Los {args.n} leads se cargan igual; Smartlead enviará {cur_max}/día y dejará el resto en cola.")

    print(f"POST {len(batch)} leads a campaña {CAMPAIGN_ID}...")
    payload = [build_lead_payload(b) for b in batch]
    add_resp = smartlead_add_leads(api_key, payload)
    print(f"  ✓ Respuesta: {json.dumps(add_resp)[:300]}")

    if cur_status != "ACTIVE":
        print("Reactivando campaña (START)...")
        start_resp = smartlead_start(api_key)
        print(f"  ✓ Respuesta: {json.dumps(start_resp)[:200]}")

    weekday = date.today().weekday()
    tag_day = DAY_TAG_MAP.get(weekday, f"dia{weekday}")
    tag = f"EN_COLA_{tag_day}{date.today().day}"
    append_log(log_rows, batch, tag)
    print(f"\n✓ enviados-log.csv actualizado con tag '{tag}' ({len(batch)} filas nuevas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
