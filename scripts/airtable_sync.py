#!/usr/bin/env python3
"""
Duendes AIOS — Airtable → Engram Sync  [DEPRECATED]

DEPRECATED: This script is no longer needed.
The modules sdr_leads.py, cs_clients.py, cfo_invoices.py now read/write
Airtable directly via airtable_client.py. Engram is used for AI memory only.

The launchd job (com.duendes.aios.sync.plist) can be safely removed:
  rm ~/Library/LaunchAgents/com.duendes.aios.sync.plist

This file is kept for reference only.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appFIn3ntFb39vGXF")
ENGRAM_URL = os.getenv("ENGRAM_URL", "http://127.0.0.1:7437")

# Table IDs (stable — won't change if you rename the tables)
TABLE_LEADS     = "tblyTzWUXxpWeHJaB"
TABLE_CLIENTS   = "tbl4Z31UWesy9NmB2"
TABLE_PROJECTS  = "tblyFyNTijqJufPpc"
TABLE_INVOICES  = "tbl0ee0GLpZjQtrGe"

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] airtable-sync — %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "scripts/logs/airtable_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("airtable-sync")


# ── Sector normalizer ─────────────────────────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "fisioterapia":         "fisio",
    "clínica dental":       "dental",
    "clinica dental":       "dental",
    "bufete / legal":       "abogados",
    "bufete/legal":         "abogados",
    "gestoría":             "gestoria",
    "gestoria":             "gestoria",
    "consultoría":          "consultoria",
    "consultoria":          "consultoria",
    "centro de estética":   "estetica",
    "peluquería / barbería":"peluqueria",
    "fontanería":           "fontaneria",
    "electricidad":         "electricidad",
    "reformas":             "reformas",
    "comercio":             "comercio",
    "otro":                 "otro",
}

def _norm_sector(raw: str) -> str:
    return _SECTOR_MAP.get(raw.lower().strip(), raw.lower().strip() or "otro")


# ── Lead status normalizer ────────────────────────────────────────────────────
_LEAD_STATUS_MAP: dict[str, str] = {
    "nuevo":              "nuevo",
    "contactado":         "contactado",
    "reunión agendada":   "calificado",
    "reunion agendada":   "calificado",
    "propuesta enviada":  "calificado",
    "negociación":        "negociacion",
    "negociacion":        "negociacion",
    "ganado":             "convertido",
    "perdido":            "descartado",
    "incorrecto":         "descartado",
}

def _norm_lead_status(raw: str) -> str:
    return _LEAD_STATUS_MAP.get(raw.lower().strip(), "nuevo")


# ── Client status normalizer ─────────────────────────────────────────────────
_CLIENT_STATUS_MAP: dict[str, str] = {
    "activo":     "activo",
    "pausado":    "pausado",
    "completado": "completado",
    "churn":      "cancelado",
}

def _norm_client_status(raw: str) -> str:
    return _CLIENT_STATUS_MAP.get(raw.lower().strip(), "activo")


# ── Project status normalizer ─────────────────────────────────────────────────
_PROJECT_STATUS_MAP: dict[str, str] = {
    "planificación": "pendiente",
    "planificacion": "pendiente",
    "en progreso":   "en_progreso",
    "revisión":      "revision",
    "revision":      "revision",
    "entregado":     "entregado",
    "cerrado":       "cerrado",
}

def _norm_project_status(raw: str) -> str:
    return _PROJECT_STATUS_MAP.get(raw.lower().strip(), raw.lower().strip() or "pendiente")


# ── Airtable client ───────────────────────────────────────────────────────────

class AirtableClient:
    BASE_URL = "https://api.airtable.com/v0"

    def __init__(self, api_key: str, base_id: str):
        self.api_key = api_key
        self.base_id = base_id
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def list_records(self, table_id: str, max_records: int = 1000) -> list[dict]:
        url = f"{self.BASE_URL}/{self.base_id}/{table_id}"
        records: list[dict] = []
        params: dict[str, Any] = {"maxRecords": max_records}

        with httpx.Client(timeout=30) as client:
            while True:
                resp = client.get(url, headers=self.headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
                params["offset"] = offset

        return records


# ── Engram upsert helper ─────────────────────────────────────────────────────

SYNC_SESSION_ID = "duendes-airtable-sync"
ENGRAM_PROJECT = "duendes-aios"


class EngramSyncClient:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._ensure_session()

    def _ensure_session(self) -> None:
        try:
            with httpx.Client(timeout=5) as client:
                client.post(
                    f"{self.url}/sessions",
                    json={"id": SYNC_SESSION_ID, "project": ENGRAM_PROJECT,
                          "directory": str(BASE_DIR)},
                )
        except Exception:
            pass  # session already exists or Engram unreachable — handled later

    def _search(self, query: str, limit: int = 20) -> list[dict]:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{self.url}/search",
                params={"q": query, "project": ENGRAM_PROJECT, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json() if isinstance(resp.json(), list) else []

    def _get(self, obs_id: int) -> dict:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{self.url}/observations/{obs_id}")
            resp.raise_for_status()
            return resp.json()

    def _create(self, title: str, content: str, topic_key: str) -> dict:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{self.url}/observations",
                json={
                    "session_id": SYNC_SESSION_ID,
                    "type": "architecture",
                    "title": title,
                    "content": content,
                    "project": ENGRAM_PROJECT,
                    "scope": "project",
                    "topic_key": topic_key,
                },
            )
            resp.raise_for_status()
            return resp.json()

    def _update(self, obs_id: int, title: str, content: str) -> dict:
        with httpx.Client(timeout=15) as client:
            resp = client.put(
                f"{self.url}/observations/{obs_id}",
                json={"title": title, "content": content, "type": "architecture"},
            )
            resp.raise_for_status()
            return resp.json()

    def upsert(self, title: str, content: str, project: str, topic_key: str) -> None:
        """Create or overwrite the observation at topic_key (FTS5 exact-match pattern)."""
        results = self._search(topic_key, limit=20)
        for r in results:
            obs_id = r.get("id")
            if obs_id:
                try:
                    full = self._get(obs_id)
                    if full.get("topic_key") == topic_key:
                        self._update(obs_id, title, content)
                        return
                except Exception:
                    continue
        self._create(title, content, topic_key)


# ── Field helpers ─────────────────────────────────────────────────────────────

def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, bool):
        return "sí" if v else "no"
    return str(v).strip()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Sync: Leads ───────────────────────────────────────────────────────────────

def sync_leads(at: AirtableClient, engram: EngramSyncClient) -> int:
    log.info("Syncing Leads...")
    records = at.list_records(TABLE_LEADS)
    log.info("  %d records found in Airtable", len(records))

    leads: list[dict] = []
    for rec in records:
        f = rec["fields"]
        lead = {
            "id":           rec["id"],
            "nombre":       _f(f, "Nombre"),
            "empresa":      _f(f, "Empresa"),
            "email":        _f(f, "Email"),
            "telefono":     _f(f, "Teléfono"),
            "sector":       _norm_sector(_f(f, "Sector")),
            "fuente":       _f(f, "Fuente").lower(),
            "estado":       _norm_lead_status(_f(f, "Estado")),
            "notas":        _f(f, "Notas"),
            "fecha_reunion":_f(f, "Fecha reunión"),
            "cal_id":       _f(f, "Cal Booking ID"),
            "convertido":   _f(f, "Convertido"),
            "synced_at":    _now(),
        }
        if lead["nombre"]:
            leads.append(lead)

    engram.upsert(
        title=f"Airtable leads — {len(leads)} registros",
        content=json.dumps(leads, ensure_ascii=False, indent=2),
        project="duendes-aios",
        topic_key="sdr/leads/active",
    )
    log.info("  ✅ %d leads → Engram (sdr/leads/active)", len(leads))
    return len(leads)


# ── Sync: Clients ─────────────────────────────────────────────────────────────

def sync_clients(at: AirtableClient, engram: EngramSyncClient) -> int:
    log.info("Syncing Clients...")
    records = at.list_records(TABLE_CLIENTS)
    log.info("  %d records found in Airtable", len(records))

    clients: list[dict] = []
    for rec in records:
        f = rec["fields"]
        client = {
            "id":             rec["id"],
            "nombre":         _f(f, "Nombre"),
            "empresa":        _f(f, "Empresa"),
            "email":          _f(f, "Email"),
            "telefono":       _f(f, "Teléfono"),
            "sector":         _norm_sector(_f(f, "Sector")),
            "servicio":       _f(f, "Servicio"),
            "estado":         _norm_client_status(_f(f, "Estado")),
            "valor_contrato": _f(f, "Valor contrato"),
            "stripe_id":      _f(f, "Stripe Customer ID"),
            "drive_url":      _f(f, "Drive Folder URL"),
            "notion_url":     _f(f, "Notion Page URL"),
            "setup_completo": _f(f, "Setup completo"),
            "fecha_inicio":   _f(f, "Fecha inicio"),
            "synced_at":      _now(),
        }
        if client["nombre"]:
            clients.append(client)

    engram.upsert(
        title=f"Airtable clients — {len(clients)} registros",
        content=json.dumps(clients, ensure_ascii=False, indent=2),
        project="duendes-aios",
        topic_key="cs/clients/active",
    )
    log.info("  ✅ %d clients → Engram (cs/clients/active)", len(clients))
    return len(clients)


# ── Sync: Projects ────────────────────────────────────────────────────────────

def sync_projects(at: AirtableClient, engram: EngramSyncClient) -> int:
    log.info("Syncing Projects...")
    records = at.list_records(TABLE_PROJECTS)
    log.info("  %d records found in Airtable", len(records))

    projects: list[dict] = []
    for rec in records:
        f = rec["fields"]
        project = {
            "id":           rec["id"],
            "nombre":       _f(f, "Nombre"),
            "estado":       _norm_project_status(_f(f, "Estado")),
            "entregables":  _f(f, "Entregables"),
            "fecha_limite": _f(f, "Fecha límite"),
            "drive_url":    _f(f, "Drive URL"),
            "notion_url":   _f(f, "Notion URL"),
            "horas":        _f(f, "Horas trabajadas"),
            "synced_at":    _now(),
        }
        if project["nombre"]:
            projects.append(project)

    engram.upsert(
        title=f"Airtable projects — {len(projects)} registros",
        content=json.dumps(projects, ensure_ascii=False, indent=2),
        project="duendes-aios",
        topic_key="coo/projects/active",
    )
    log.info("  ✅ %d projects → Engram (coo/projects/active)", len(projects))
    return len(projects)


# ── Sync: Invoices ────────────────────────────────────────────────────────────

def sync_invoices(at: AirtableClient, engram: EngramSyncClient) -> int:
    log.info("Syncing Invoices...")
    records = at.list_records(TABLE_INVOICES)
    log.info("  %d records found in Airtable", len(records))

    invoices: list[dict] = []
    for rec in records:
        f = rec["fields"]
        invoice = {
            "id":         rec["id"],
            "numero":     _f(f, "Número factura"),
            "importe":    _f(f, "Importe"),
            "fecha":      _f(f, "Fecha"),
            "estado":     _f(f, "Estado").lower(),   # pendiente | pagada | vencida
            "stripe_id":  _f(f, "Stripe Payment ID"),
            "gmail_link": _f(f, "Gmail Link"),
            "synced_at":  _now(),
        }
        if invoice["numero"]:
            invoices.append(invoice)

    engram.upsert(
        title=f"Airtable invoices — {len(invoices)} registros",
        content=json.dumps(invoices, ensure_ascii=False, indent=2),
        project="duendes-aios",
        topic_key="cfo/invoices/active",
    )
    log.info("  ✅ %d invoices → Engram (cfo/invoices/active)", len(invoices))
    return len(invoices)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_sync(tables: list[str]) -> dict[str, int]:
    if not AIRTABLE_API_KEY:
        raise RuntimeError("AIRTABLE_API_KEY not set in .env")
    if not AIRTABLE_BASE_ID:
        raise RuntimeError("AIRTABLE_BASE_ID not set in .env")

    at = AirtableClient(AIRTABLE_API_KEY, AIRTABLE_BASE_ID)
    engram = EngramSyncClient(ENGRAM_URL)
    results: dict[str, int] = {}

    if "leads" in tables:
        results["leads"] = sync_leads(at, engram)
    if "clients" in tables:
        results["clients"] = sync_clients(at, engram)
    if "projects" in tables:
        results["projects"] = sync_projects(at, engram)
    if "invoices" in tables:
        results["invoices"] = sync_invoices(at, engram)

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Duendes CRM (Airtable) → Engram")
    parser.add_argument(
        "--table",
        choices=["leads", "clients", "projects", "invoices", "all"],
        default="all",
    )
    args = parser.parse_args()
    tables = ["leads", "clients", "projects", "invoices"] if args.table == "all" else [args.table]

    log.info("=== Airtable sync starting: %s ===", tables)
    try:
        results = run_sync(tables)
        for t, n in results.items():
            log.info("  %s: %d records synced", t, n)
        total = sum(results.values())
        print(f"Sync OK — {total} records total: {results}")
    except RuntimeError as e:
        log.error("Config error: %s", e)
        print(f"❌ {e}")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        log.error("Airtable API error %s: %s", e.response.status_code, e.response.text[:300])
        sys.exit(1)
    except Exception as e:
        log.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
