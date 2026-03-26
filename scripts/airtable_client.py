"""
Duendes AIOS — Shared Airtable HTTP Client
All modules use this for direct read/write on Airtable tables.

Base: Duendes CRM (appFIn3ntFb39vGXF)
Tables:
  TABLE_LEADS    = "tblyTzWUXxpWeHJaB"
  TABLE_CLIENTS  = "tbl4Z31UWesy9NmB2"
  TABLE_PROJECTS = "tblyFyNTijqJufPpc"
  TABLE_INVOICES = "tbl0ee0GLpZjQtrGe"
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

AIRTABLE_API_KEY: str = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "appFIn3ntFb39vGXF")
_BASE_URL = "https://api.airtable.com/v0"

# Stable table IDs — won't change if you rename the table in Airtable
TABLE_LEADS    = "tblyTzWUXxpWeHJaB"
TABLE_CLIENTS  = "tbl4Z31UWesy9NmB2"
TABLE_PROJECTS = "tblyFyNTijqJufPpc"
TABLE_INVOICES = "tbl0ee0GLpZjQtrGe"
TABLE_TASKS    = "tblChzXpWi6hEpqfw"
TABLE_DEALS    = "tblWzOHSU16QusG9s"


class AirtableError(Exception):
    pass


class AirtableClient:
    """
    Async + sync Airtable REST API client.
    Async methods for bot.py; sync methods for brief.py and CLI scripts.
    """

    def __init__(
        self,
        api_key: str = AIRTABLE_API_KEY,
        base_id: str = AIRTABLE_BASE_ID,
    ) -> None:
        if not api_key:
            raise AirtableError("AIRTABLE_API_KEY not set in .env")
        self._base = f"{_BASE_URL}/{base_id}"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Async ──────────────────────────────────────────────────────────────

    async def list_records(
        self,
        table: str,
        filter_formula: str | None = None,
        sort: list[dict[str, str]] | None = None,
        max_records: int = 1000,
    ) -> list[dict]:
        """Return all records from a table, handling Airtable pagination."""
        url = f"{self._base}/{table}"
        params: dict[str, Any] = {"maxRecords": max_records}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if sort:
            for i, s in enumerate(sort):
                params[f"sort[{i}][field]"] = s["field"]
                params[f"sort[{i}][direction]"] = s.get("direction", "asc")

        records: list[dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(url, headers=self._headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
                params = {**params, "offset": offset}
        return records

    async def create_record(self, table: str, fields: dict) -> dict:
        """Create a record. Returns the full Airtable record dict (id + fields + createdTime)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self._base}/{table}",
                headers=self._headers,
                json={"fields": fields},
            )
            resp.raise_for_status()
            return resp.json()

    async def update_record(self, table: str, record_id: str, fields: dict) -> dict:
        """PATCH update — only the provided fields are modified, others stay intact."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{self._base}/{table}/{record_id}",
                headers=self._headers,
                json={"fields": fields},
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_record(self, table: str, record_id: str) -> bool:
        """Delete a record. Returns True if deleted."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{self._base}/{table}/{record_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return bool(resp.json().get("deleted", False))

    # ── Sync (brief.py + CLI) ─────────────────────────────────────────────

    def list_records_sync(
        self,
        table: str,
        filter_formula: str | None = None,
        sort: list[dict[str, str]] | None = None,
        max_records: int = 1000,
    ) -> list[dict]:
        url = f"{self._base}/{table}"
        params: dict[str, Any] = {"maxRecords": max_records}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if sort:
            for i, s in enumerate(sort):
                params[f"sort[{i}][field]"] = s["field"]
                params[f"sort[{i}][direction]"] = s.get("direction", "asc")

        records: list[dict] = []
        with httpx.Client(timeout=30) as client:
            while True:
                resp = client.get(url, headers=self._headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
                params = {**params, "offset": offset}
        return records

    def create_record_sync(self, table: str, fields: dict) -> dict:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{self._base}/{table}",
                headers=self._headers,
                json={"fields": fields},
            )
            resp.raise_for_status()
            return resp.json()

    def update_record_sync(self, table: str, record_id: str, fields: dict) -> dict:
        with httpx.Client(timeout=10) as client:
            resp = client.patch(
                f"{self._base}/{table}/{record_id}",
                headers=self._headers,
                json={"fields": fields},
            )
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: AirtableClient | None = None


def get_client() -> AirtableClient:
    """Return (and lazily create) the module-level AirtableClient singleton."""
    global _client
    if _client is None:
        _client = AirtableClient()
    return _client
