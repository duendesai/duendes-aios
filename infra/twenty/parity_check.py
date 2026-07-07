#!/usr/bin/env python3
"""Chequeo de paridad Airtable ↔ Twenty durante la ventana de dual-write (Fase 10).

Para cada Lead de Airtable (base "Duendes CRM") busca su gemelo en Twenty (por
email / calBookingId) y compara los campos mapeados. Reporta matched /
missing_in_twenty / field_mismatch y un % de paridad, criterio del cutover.

Comparaciones especiales:
- fecha_reunion: por INSTANTE (UTC), no por string (Twenty devuelve .000Z).
- telefono: por dígitos (Twenty separa el prefijo de país; +34600... vs 600...).

Uso:
    AIRTABLE_API_KEY=... TWENTY_API_KEY=... TWENTY_BASE_URL=https://crm.duendes.net \\
        apps/api/.venv/bin/python infra/twenty/parity_check.py
"""
import asyncio
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
from services.airtable_multi import (  # noqa: E402
    BASE_CRM,
    TABLE_LEADS,
    AirtableMultiClient,
)
from services.crm.airtable_adapter import AirtableCRMAdapter  # noqa: E402
from services.crm.models import Lead  # noqa: E402
from services.crm.twenty_adapter import TwentyCRMAdapter  # noqa: E402

_FIELDS = ["nombre", "email", "telefono", "empresa", "sector", "fuente",
           "estado", "fecha_reunion", "cal_booking_id", "notas"]


def _norm_phone(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")[-9:]  # últimos 9 dígitos (ignora prefijo país)


def _same_instant(a: str | None, b: str | None) -> bool:
    if not a and not b:
        return True
    if not a or not b:
        return False
    try:
        da = datetime.fromisoformat(a.replace("Z", "+00:00"))
        db = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return da == db
    except (ValueError, TypeError):
        return a == b


def _field_equal(name: str, a, b) -> bool:
    if name == "fecha_reunion":
        return _same_instant(a, b)
    if name == "telefono":
        return _norm_phone(a) == _norm_phone(b)
    return (a or "") == (b or "")


def _diffs(a: Lead, t: Lead) -> list[str]:
    out = []
    for f in _FIELDS:
        av, tv = getattr(a, f), getattr(t, f)
        if not _field_equal(f, av, tv):
            out.append(f"{f}: airtable={av!r} twenty={tv!r}")
    return out


async def run() -> None:
    air = AirtableMultiClient(api_key=os.environ["AIRTABLE_API_KEY"])
    airtable = AirtableCRMAdapter(air)
    twenty = TwentyCRMAdapter(base_url=os.environ["TWENTY_BASE_URL"],
                              api_key=os.environ["TWENTY_API_KEY"])

    records = await air.list_records(BASE_CRM, TABLE_LEADS)
    matched, missing, mismatched = [], [], []

    for rec in records:
        a_lead = airtable._record_to_lead(rec)
        ref = await twenty.find_lead(
            email=a_lead.email or None, cal_booking_id=a_lead.cal_booking_id or None,
        )
        if ref is None:
            missing.append(a_lead.email or a_lead.cal_booking_id)
            continue
        t_lead = await twenty.get_lead(ref)
        diffs = _diffs(a_lead, t_lead) if t_lead else ["no legible en Twenty"]
        if diffs:
            mismatched.append((a_lead.email, diffs))
        else:
            matched.append(a_lead.email)

    total = len(records)
    presencia = (total - len(missing)) / total * 100 if total else 100.0
    paridad = len(matched) / total * 100 if total else 100.0

    print(f"Leads Airtable: {total}")
    print(f"  matched (idénticos):     {len(matched)}")
    print(f"  missing_in_twenty:       {len(missing)}  {missing or ''}")
    print(f"  field_mismatch:          {len(mismatched)}")
    for email, diffs in mismatched:
        print(f"    - {email}:")
        for d in diffs:
            print(f"        {d}")
    print(f"\nPresencia en Twenty: {presencia:.1f}%  (criterio cutover: 100%)")
    print(f"Paridad de campos:   {paridad:.1f}%  (criterio cutover: ≥95%)")


if __name__ == "__main__":
    asyncio.run(run())
