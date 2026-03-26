"""
Duendes AIOS — SDR Prospect Researcher
Uses Apify Google Maps Scraper to find and qualify leads by sector + city.
Saves qualified leads directly to Airtable Leads table (tblyTzWUXxpWeHJaB).

Trigger: /sdr buscar <sector> <ciudad>
Output:  Leads saved silently to Airtable + Telegram summary
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from airtable_client import AirtableClient, TABLE_LEADS, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

logger = logging.getLogger("duendes-bot.sdr_researcher")

APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "apify~google-maps-scraper"

MAX_PLACES = 25          # results per search
MAX_REVIEWS_ICP = 150    # above this → likely chain, skip
POLL_INTERVAL = 6        # seconds between status checks
MAX_WAIT = 360           # seconds before timeout (6 min)

# ---------------------------------------------------------------------------
# Sector mappings
# ---------------------------------------------------------------------------

# sector slug → Google Maps search term
SECTOR_QUERIES: dict[str, str] = {
    "fisio":        "fisioterapia",
    "quiro":        "quiropráctica",
    "dental":       "clínica dental",
    "estetica":     "centro estética",
    "abogados":     "abogado",
    "gestoria":     "gestoría",
    "fontanero":    "fontanero",
    "electricista": "electricista",
}

# sector slug → Airtable single-select option
SECTOR_TO_AT: dict[str, str] = {
    "fisio":        "Fisioterapia",
    "quiro":        "Fisioterapia",
    "dental":       "Clínica Dental",
    "estetica":     "Centro de Estética",
    "abogados":     "Bufete / Legal",
    "gestoria":     "Gestoría",
    "fontanero":    "Fontanería",
    "electricista": "Electricidad",
}

VALID_SECTORS = set(SECTOR_QUERIES.keys())

# ---------------------------------------------------------------------------
# Apify helpers
# ---------------------------------------------------------------------------

async def _run_apify(search_query: str) -> list[dict]:
    """Start Apify run, poll until complete, return dataset items."""
    if not APIFY_API_TOKEN:
        raise ValueError("APIFY_API_TOKEN not set in .env")

    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            headers=headers,
            json={
                "searchStringsArray": [search_query],
                "maxCrawledPlacesPerSearch": MAX_PLACES,
                "language": "es",
                "countryCode": "es",
                "includeHistogram": False,
                "includeOpeningHours": False,
                "includePeopleAlsoSearch": False,
            },
        )
        resp.raise_for_status()
        run_data = resp.json().get("data", {})
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

    logger.info("Apify run started: %s (query: %r)", run_id, search_query)

    # Poll until finished
    status = "RUNNING"
    elapsed = 0
    async with httpx.AsyncClient(timeout=15) as client:
        while elapsed < MAX_WAIT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            r = await client.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers=headers,
            )
            r.raise_for_status()
            status = r.json().get("data", {}).get("status", "")
            logger.info("Apify run %s: %s (%ds)", run_id, status, elapsed)
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run ended with status: {status}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            headers=headers,
            params={"format": "json", "clean": "true"},
        )
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Qualification
# ---------------------------------------------------------------------------

def _qualifies(place: dict) -> bool:
    """True if the place matches Duendes ICP criteria."""
    if place.get("permanentlyClosed") or place.get("temporarilyClosed"):
        return False
    if not (place.get("phone") or "").strip():
        return False  # no phone = can't be contacted
    reviews = place.get("reviewsCount") or 0
    if reviews > MAX_REVIEWS_ICP:
        return False  # likely a chain
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def research_leads(sector: str, ciudad: str) -> dict:
    """
    Search Google Maps via Apify, qualify results, deduplicate against
    existing Airtable leads, save new ones.

    Returns:
        {found, qualified, saved, skipped_dup, leads_saved: list[str]}
    """
    sector = sector.lower().strip()
    ciudad = ciudad.strip()

    query_term = SECTOR_QUERIES.get(sector, sector)
    search_query = f"{query_term} {ciudad}"
    at_sector = SECTOR_TO_AT.get(sector, "Otro")

    # 1. Run Apify
    places = await _run_apify(search_query)
    found = len(places)

    # 2. Qualify
    qualified = [p for p in places if _qualifies(p)]

    # 3. Deduplicate against existing Airtable phones
    at = get_client()
    try:
        existing_records = await at.list_records(TABLE_LEADS, max_records=2000)
        existing_phones = {
            r.get("fields", {}).get("Teléfono", "").strip()
            for r in existing_records
            if r.get("fields", {}).get("Teléfono")
        }
    except Exception as exc:
        logger.warning("Could not load existing leads for dedup: %s", exc)
        existing_phones = set()

    new_places = [
        p for p in qualified
        if (p.get("phone") or "").strip() not in existing_phones
    ]
    skipped_dup = len(qualified) - len(new_places)

    # 4. Save to Airtable
    saved: list[str] = []
    for place in new_places:
        phone = (place.get("phone") or "").strip()
        name = (place.get("title") or "").strip()
        address = (place.get("address") or "").strip()
        website = (place.get("website") or "").strip()
        rating = place.get("rating")
        reviews = place.get("reviewsCount") or 0

        nota_parts = [f"Google Maps · {ciudad}"]
        if rating:
            nota_parts.append(f"⭐ {rating} ({reviews} reseñas)")
        if address:
            nota_parts.append(address)
        if website:
            nota_parts.append(website)

        fields: dict[str, Any] = {
            "Empresa": name,
            "Teléfono": phone,
            "Sector": at_sector,
            "Fuente": "Outreach",
            "Estado": "Nuevo",
            "Notas": " · ".join(nota_parts),
        }

        try:
            await at.create_record(TABLE_LEADS, fields)
            saved.append(name)
            logger.info("Lead saved: %s (%s)", name, phone)
        except Exception as exc:
            logger.error("Error saving lead %r: %s", name, exc)

    return {
        "found": found,
        "qualified": len(qualified),
        "saved": len(saved),
        "skipped_dup": skipped_dup,
        "leads_saved": saved,
    }


def format_research_summary(result: dict, sector: str, ciudad: str) -> str:
    """Format research result as Telegram message."""
    saved = result["saved"]
    lines = [
        f"🔍 *Búsqueda completada: {sector} en {ciudad}*\n",
        f"Encontrados en Google Maps: {result['found']}",
        f"Cualificados (ICP): {result['qualified']}",
        f"Duplicados omitidos: {result['skipped_dup']}",
        f"Guardados en Airtable: *{saved}*",
    ]
    if result["leads_saved"]:
        lines.append("\n*Leads añadidos:*")
        for name in result["leads_saved"][:15]:
            lines.append(f"  • {name}")
        if saved > 15:
            lines.append(f"  … y {saved - 15} más")
    else:
        lines.append("\nNo se encontraron leads nuevos.")
    return "\n".join(lines)
