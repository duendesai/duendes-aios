#!/usr/bin/env python3
"""Backfill idempotente de los Leads de Airtable (base "Duendes CRM") a Twenty.

Lee vía `AirtableMultiClient` y reusa el mapeo registro→`Lead` del
`AirtableCRMAdapter` (sin duplicar lógica); escribe vía `TwentyCRMAdapter`, que
es idempotente por `find_lead` (email / calBookingId): re-ejecutar no duplica, y
puede solaparse con el dual-write sin crear duplicados.

Uso (con el venv del backend):
    AIRTABLE_API_KEY=... TWENTY_API_KEY=... TWENTY_BASE_URL=https://crm.duendes.net \\
        apps/api/.venv/bin/python infra/twenty/backfill_leads.py [--dry-run]
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
from services.airtable_multi import (  # noqa: E402
    BASE_CRM,
    TABLE_LEADS,
    AirtableMultiClient,
)
from services.crm.airtable_adapter import AirtableCRMAdapter  # noqa: E402
from services.crm.twenty_adapter import TwentyCRMAdapter  # noqa: E402


async def run(dry_run: bool) -> None:
    air = AirtableMultiClient(api_key=os.environ["AIRTABLE_API_KEY"])
    air_adapter = AirtableCRMAdapter(air)
    twenty = TwentyCRMAdapter(
        base_url=os.environ["TWENTY_BASE_URL"],
        api_key=os.environ["TWENTY_API_KEY"],
    )

    records = await air.list_records(BASE_CRM, TABLE_LEADS)
    print(f"Leads en Airtable (Duendes CRM): {len(records)}")

    created = existed = 0
    for rec in records:
        lead = air_adapter._record_to_lead(rec)
        if dry_run:
            print(f"  [dry] {lead.email!r} | {lead.nombre!r} | "
                  f"sector={lead.sector!r} estado={lead.estado!r} "
                  f"cal={lead.cal_booking_id!r}")
            continue
        existing = await twenty.find_lead(
            email=lead.email or None,
            cal_booking_id=lead.cal_booking_id or None,
        )
        if existing is not None:
            existed += 1
            print(f"  = ya en Twenty: {lead.email} -> {existing.id}")
            continue
        ref = await twenty.create_lead(lead)
        created += 1
        print(f"  + creado en Twenty: {lead.email} -> {ref.id}")

    if dry_run:
        print("\nDRY-RUN: no se escribió nada en Twenty.")
    else:
        print(f"\nResumen: {created} creados, {existed} ya existían.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Lee y mapea, pero no escribe en Twenty.")
    asyncio.run(run(parser.parse_args().dry_run))
