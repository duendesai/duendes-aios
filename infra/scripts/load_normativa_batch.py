#!/usr/bin/env python3
"""
Carga los 50 emails del ángulo NORMATIVO en Smartlead campaña 3404016 (Despachos Madrid).

Fuente: cold-outreach/campaigns/despachos-madrid-2026-05/emails-normativa-50-final.csv
(formato: email, company_name, email_subject, email_body, ... con custom_fields).

Seguridad:
  - Excluye filas con email_body == ERROR.
  - Excluye filas cuyo validator_fails contenga "MIEDO" (no enviar alarmismo).
  - Excluye emails ya presentes en enviados-log.csv (idempotente).

Hace: POST leads (custom_fields email_subject/email_body) → START campaña → actualiza log.

Uso:
    uv run python infra/scripts/load_normativa_batch.py [--dry-run]
"""
from __future__ import annotations

import argparse, csv, json, sys
from datetime import date
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE  = REPO_ROOT / ".env"
CAMP_DIR  = REPO_ROOT / "cold-outreach/campaigns/despachos-madrid-2026-05"
SRC_CSV   = CAMP_DIR / "emails-normativa-50-final.csv"
LOG_CSV   = CAMP_DIR / "enviados-log.csv"

CAMPAIGN_ID = 3404016
BASE_URL    = "https://server.smartlead.ai/api/v1"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def load_already_sent() -> set[str]:
    sent: set[str] = set()
    if LOG_CSV.exists():
        with LOG_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sent.add(row["email"].strip().lower())
    return sent


def build_payload(row: dict) -> dict:
    return {
        "email": row["email"],
        "first_name": "",
        "last_name": "",
        "company_name": row.get("company_name", ""),
        "custom_fields": {
            "email_subject": row["email_subject"],
            "email_body": row["email_body"],
        },
    }


def append_log(new_rows: list[dict], tag: str) -> None:
    existing = []
    if LOG_CSV.exists():
        with LOG_CSV.open(encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    for r in new_rows:
        existing.append({"email": r["email"], "subject": r["email_subject"],
                         "sent_time": tag, "opened": "False", "replied": "False"})
    with LOG_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["email", "subject", "sent_time", "opened", "replied"])
        w.writeheader(); w.writerows(existing)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    api_key = env.get("SMARTLEAD_API_KEY", "")
    if not api_key:
        print("ERROR: SMARTLEAD_API_KEY ausente en .env", file=sys.stderr); return 1

    rows = list(csv.DictReader(SRC_CSV.open(encoding="utf-8")))
    already = load_already_sent()

    eligible, skipped = [], {"error": 0, "miedo": 0, "ya_enviado": 0}
    for r in rows:
        if r.get("email_body", "").strip() == "ERROR":
            skipped["error"] += 1; continue
        if "MIEDO" in (r.get("validator_fails", "") or ""):
            skipped["miedo"] += 1; continue
        if r["email"].strip().lower() in already:
            skipped["ya_enviado"] += 1; continue
        eligible.append(r)

    print(f"CSV: {len(rows)} filas | Elegibles: {len(eligible)} | Saltados: {skipped}")
    by_sub = {}
    for r in eligible:
        by_sub[r.get("subject_pattern", "?")] = by_sub.get(r.get("subject_pattern", "?"), 0) + 1
    print(f"Reparto subject A/B: {by_sub}")

    if args.dry_run:
        print("\n[DRY RUN] No se llama a Smartlead. Muestra de 3:")
        for r in eligible[:3]:
            print(f"  {r['email']:<40} → {r['email_subject']}")
        return 0

    # 1) POST leads
    payload = [build_payload(r) for r in eligible]
    resp = httpx.post(f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/leads",
                      params={"api_key": api_key}, json={"lead_list": payload}, timeout=60)
    if resp.status_code >= 400:
        print(f"ERROR add_leads {resp.status_code}: {resp.text[:400]}", file=sys.stderr); return 1
    print(f"✓ add_leads: {json.dumps(resp.json())[:300]}")

    # 2) START (la campaña pasa a COMPLETED cuando se queda sin cola)
    s = httpx.post(f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/status",
                   params={"api_key": api_key}, json={"status": "START"}, timeout=30)
    print(f"✓ start: {s.status_code} {s.text[:120]}")

    # 3) Log
    tag = f"EN_COLA_normativa_{date.today().isoformat()}"
    append_log(eligible, tag)
    print(f"✓ enviados-log.csv +{len(eligible)} filas (tag '{tag}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
