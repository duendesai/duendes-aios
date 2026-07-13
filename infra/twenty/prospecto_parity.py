#!/usr/bin/env python3
"""Chequeo de paridad Airtable `malaga` ↔ Twenty `prospecto` (C2).

Hermano de `parity_check.py` (que compara la tabla `Leads`), pero para la cola del
dialer: por cada registro de `malaga` en Airtable busca su gemelo en Twenty (por
`airtableId`) y compara los campos mapeados. Criterio de corte del dialer (E2):

- Presencia: 100%  (todo registro elegible tiene gemelo en Twenty).
- Paridad de campos: ≥95%.
- `noLlamar`: 100%, SIN excepción. Es el único campo con implicación de cumplimiento
  (RGPD/LOPDGDD, opt-out): un `No llamar=true` que no migre significa llamar a alguien
  que ya dijo que no. Por eso el comparador lo separa como `compliance_mismatch`, no
  como un mismatch de campo genérico más.

Comparaciones especiales (idénticas a parity_check.py):
- fechas (ultimoIntento / proximoIntento): por INSTANTE (UTC), no por string.
- teléfono: por dígitos finales (Twenty separa el prefijo de país).

La lógica de comparación (`compare_prospecto`) es PURA y testeable sin red
(ver apps/api/tests/test_prospecto_parity.py). El runner (`run`) sí toca APIs y lee
el entorno de forma perezosa dentro de la función, para que importar este módulo en
los tests no exija credenciales.

Uso (en Hetzner, que alcanza Twenty y tiene el .env):
    set -a; . /opt/n8n-recepcionista/.env; set +a
    apps/api/.venv/bin/python infra/twenty/prospecto_parity.py
    apps/api/.venv/bin/python infra/twenty/prospecto_parity.py --base <base> --table <tabla>
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ── option_value (COPIA EXACTA de apps/api/services/crm/models.py) ──────────────
def option_value(label: str) -> str:
    """Etiqueta → value UPPER_SNAKE de Twenty."""
    nfkd = unicodedata.normalize("NFKD", label)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() else " " for c in ascii_only)
    return "_".join(cleaned.upper().split())


# ── Sets limpios + alias (espejo de migrate_prospectos.py) ──────────────────────
ESTADO = ["Pendiente", "No contesta", "Contestador", "Comunica", "Gatekeeper",
          "Info solicitada", "Rellamar", "Interés cálido", "Demo agendada",
          "No interesa", "No interesa ahora", "No cualifica", "Ilocalizable",
          "Número erróneo", "Número inexistente", "No llamar"]
PRIORIDAD = ["Alta", "Media", "Baja", "Sin calificar"]
CAMPANA = ["Fisios Málaga", "Despachos Madrid", "Colegios Fisioterapia", "Webinar Colegios"]
FUENTE = ["Apify Google Maps", "Manual", "Referencia", "LinkedIn Sales Nav",
          "Meta Ads", "Web formulario", "Otro", "Test interno", "Cold email"]
OUTCOME = ["demo_agendada", "no_interesa", "callback", "no_llamar", "no_contesta"]

ESTADO_ALIAS = {"Interes calido": "Interés cálido", "Agendada": "Demo agendada"}

_VALID: dict[str, set[str]] = {
    "estado": {option_value(x) for x in ESTADO},
    "prioridad": {option_value(x) for x in PRIORIDAD},
    "campana": {option_value(x) for x in CAMPANA},
    "fuente": {option_value(x) for x in FUENTE},
    "outcome": {option_value(x) for x in OUTCOME},
}


def _airtable_select_value(field_key: str, label: Any, alias: dict | None = None) -> str | None:
    """Etiqueta Airtable → value Twenty válido, o None si no casa (se omite)."""
    if not label:
        return None
    clean = (alias or {}).get(label, label)
    value = option_value(str(clean))
    return value if value in _VALID[field_key] else None


# ── Comparadores por tipo de campo ──────────────────────────────────────────────
def _norm_phone(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))[-9:]  # últimos 9 dígitos (ignora prefijo país)


def _same_instant(a: Any, b: Any) -> bool:
    if not a and not b:
        return True
    if not a or not b:
        return False
    try:
        da = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        db = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
        return da == db
    except (ValueError, TypeError):
        return str(a) == str(b)


def _norm_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).strip()


def _norm_int(v: Any) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0


# ── Especificación de campos a comparar (airtable_field, twenty_field, tipo) ────
# tipo ∈ {"text", "phone", "instant", "int", "select:<field>"}
# name y phone NO van aquí: su campo Airtable de origen es configurable (los defaults
# 'title'/'phone' valen para malaga/fisios; abogados usan 'Name'/'Attachment Summary').
_FIELD_SPECS_REST: list[tuple[str, str, str]] = [
    ("Estado", "estado", "select:estado"),
    ("Prioridad", "prioridad", "select:prioridad"),
    ("Campaña", "campana", "select:campana"),
    ("Intentos", "intentos", "int"),
    ("Último intento", "ultimoIntento", "instant"),
    ("Próximo intento", "proximoIntento", "instant"),
    ("Email contacto", "email", "text"),
    ("city", "city", "text"),
    ("website", "website", "text"),
    ("categoryName", "categoria", "text"),
]

# Campo de cumplimiento: airtable "No llamar" ↔ twenty "noLlamar", paridad estricta.
_COMPLIANCE_AIR = "No llamar"
_COMPLIANCE_TW = "noLlamar"


@dataclass(frozen=True)
class ParityResult:
    """Resultado de comparar UN registro Airtable contra su gemelo Twenty."""

    key: str
    field_mismatches: list[str] = field(default_factory=list)
    compliance_mismatch: str | None = None  # set sólo si `noLlamar` diverge

    @property
    def is_clean(self) -> bool:
        return not self.field_mismatches and self.compliance_mismatch is None


def _field_equal(kind: str, air_val: Any, tw_val: Any) -> bool:
    if kind == "phone":
        return _norm_phone(air_val) == _norm_phone(tw_val)
    if kind == "instant":
        return _same_instant(air_val, tw_val)
    if kind == "int":
        return _norm_int(air_val) == _norm_int(tw_val)
    if kind.startswith("select:"):
        select_field = kind.split(":", 1)[1]
        alias = ESTADO_ALIAS if select_field == "estado" else None
        mapped = _airtable_select_value(select_field, air_val, alias)
        return (mapped or "") == (_norm_text(tw_val) or "")
    return _norm_text(air_val) == _norm_text(tw_val)


def compare_prospecto(
    air_record: dict[str, Any],
    twenty_node: dict[str, Any],
    name_field: str = "title",
    phone_field: str = "phone",
) -> ParityResult:
    """Compara un registro de Airtable contra su gemelo `prospecto` de Twenty.

    `air_record` es el registro crudo de Airtable ({"id", "fields": {...}}).
    `twenty_node` es el nodo GraphQL del prospecto (campos camelCase).
    `name_field`/`phone_field` son los campos Airtable de origen para nombre y teléfono
    (defaults 'title'/'phone' para malaga/fisios; 'Name'/'Attachment Summary' para abogados).
    """
    air_fields = air_record.get("fields", {})
    key = air_record.get("id") or twenty_node.get("airtableId") or "(sin id)"

    specs = [(name_field, "name", "text"), (phone_field, "phone", "phone")] + _FIELD_SPECS_REST
    mismatches: list[str] = []
    for air_key, tw_key, kind in specs:
        av = air_fields.get(air_key)
        tv = twenty_node.get(tw_key)
        if not _field_equal(kind, av, tv):
            mismatches.append(f"{tw_key}: airtable={av!r} twenty={tv!r}")

    # Cumplimiento: paridad estricta de noLlamar (booleano).
    air_no_llamar = bool(air_fields.get(_COMPLIANCE_AIR))
    tw_no_llamar = bool(twenty_node.get(_COMPLIANCE_TW))
    compliance = None
    if air_no_llamar != tw_no_llamar:
        compliance = (
            f"noLlamar (cumplimiento): airtable={air_no_llamar} twenty={tw_no_llamar}"
        )

    return ParityResult(key=key, field_mismatches=mismatches, compliance_mismatch=compliance)


# ── Runner (toca APIs; lee entorno de forma perezosa) ───────────────────────────
def _read_airtable(base: str, table: str, air_key: str) -> list[dict[str, Any]]:
    import json
    import urllib.parse
    import urllib.request

    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        url = f"https://api.airtable.com/v0/{base}/{table}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {air_key}"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        records += data["records"]
        offset = data.get("offset")
        if not offset:
            return records


def _fetch_twenty_by_airtable_id(tw_base: str, tw_key: str) -> dict[str, dict[str, Any]]:
    """Todos los prospectos de Twenty indexados por airtableId."""
    import json
    import urllib.request

    fields = ("airtableId name phone estado prioridad campana intentos ultimoIntento "
              "proximoIntento noLlamar categoria city website email")
    out: dict[str, dict[str, Any]] = {}
    after: str | None = None
    while True:
        q = ("query($after:String){ prospectos(first:60, after:$after){ edges{ node{ "
             + fields + " } } pageInfo{ hasNextPage endCursor } } }")
        body = json.dumps({"query": q, "variables": {"after": after}}).encode()
        req = urllib.request.Request(
            f"{tw_base}/graphql", data=body,
            headers={"Authorization": f"Bearer {tw_key}", "Content-Type": "application/json"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        block = data.get("data", {}).get("prospectos")
        if not block:
            return out
        for e in block["edges"]:
            node = e["node"]
            aid = node.get("airtableId")
            if aid:
                out[aid] = node
        if not block["pageInfo"]["hasNextPage"]:
            return out
        after = block["pageInfo"]["endCursor"]


def run(base: str, table: str, name_field: str = "title", phone_field: str = "phone") -> int:
    """Ejecuta el chequeo contra APIs reales. Devuelve nº de discrepancias de cumplimiento."""
    import os

    air_key = os.environ["AIRTABLE_API_KEY"]
    tw_base = os.environ["TWENTY_BASE_URL"].rstrip("/")
    tw_key = os.environ["TWENTY_API_KEY"]

    records = _read_airtable(base, table, air_key)
    twenty_by_aid = _fetch_twenty_by_airtable_id(tw_base, tw_key)

    total = len(records)
    matched: list[str] = []
    missing: list[str] = []
    field_mismatched: list[ParityResult] = []
    compliance_failures: list[ParityResult] = []

    for rec in records:
        node = twenty_by_aid.get(rec["id"])
        if node is None:
            missing.append(rec["id"])
            continue
        result = compare_prospecto(rec, node, name_field=name_field, phone_field=phone_field)
        if result.compliance_mismatch:
            compliance_failures.append(result)
        if result.field_mismatches:
            field_mismatched.append(result)
        if result.is_clean:
            matched.append(rec["id"])

    presencia = (total - len(missing)) / total * 100 if total else 100.0
    paridad = len(matched) / total * 100 if total else 100.0

    print(f"Prospectos Airtable {base}/{table}: {total}")
    print(f"  matched (idénticos):     {len(matched)}")
    print(f"  missing_in_twenty:       {len(missing)}  {missing or ''}")
    print(f"  field_mismatch:          {len(field_mismatched)}")
    for r in field_mismatched:
        print(f"    - {r.key}:")
        for d in r.field_mismatches:
            print(f"        {d}")
    print(f"\nPresencia en Twenty: {presencia:.1f}%  (criterio: 100%)")
    print(f"Paridad de campos:   {paridad:.1f}%  (criterio: ≥95%)")
    print(f"\nCUMPLIMIENTO (noLlamar) — criterio: 100%, sin excepción")
    if compliance_failures:
        print(f"  ✗ {len(compliance_failures)} discrepancias de cumplimiento (BLOQUEA el corte):")
        for r in compliance_failures:
            print(f"    - {r.key}: {r.compliance_mismatch}")
    else:
        print("  ✓ 0 discrepancias de cumplimiento")
    return len(compliance_failures)


def main() -> None:
    import argparse
    import sys

    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="app5WbiXR0qXGTc3r")   # LUCIA Bienestar
    ap.add_argument("--table", default="tblCyn7fjgBJM8rkF")  # malaga (fisios)
    ap.add_argument("--name-field", default="title",
                    help="Campo Airtable de origen del nombre (abogados: 'Name')")
    ap.add_argument("--phone-field", default="phone",
                    help="Campo Airtable de origen del teléfono (abogados: 'Attachment Summary')")
    args = ap.parse_args()
    compliance_failures = run(args.base, args.table,
                              name_field=args.name_field, phone_field=args.phone_field)
    # Salida != 0 si hay fallos de cumplimiento: sirve de puerta dura en un script.
    sys.exit(1 if compliance_failures else 0)


if __name__ == "__main__":
    main()
