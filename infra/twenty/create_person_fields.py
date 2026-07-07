#!/usr/bin/env python3
"""Crea (idempotente) los custom fields de Person en Twenty para el pipeline de
demos (Fase 2 del piloto CRM). Reproducible: tras un redeploy de Twenty, ejecutar
esto para recrear los campos.

Uso (con el venv del backend, que trae las deps y expone option_value):
    TWENTY_BASE_URL=https://crm.duendes.net TWENTY_API_KEY=<pat> \\
        apps/api/.venv/bin/python infra/twenty/create_person_fields.py

Los `value` de los SELECT se derivan de `option_value()` en
apps/api/services/crm/models.py (fuente ÚNICA), así que casan EXACTAMENTE con lo
que escribe el TwentyCRMAdapter. El id del objeto Person se descubre en runtime
(cambia en cada instalación nueva).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from typing import get_args

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
from services.crm.models import Estado, Fuente, Sector, option_value  # noqa: E402

BASE = os.environ["TWENTY_BASE_URL"].rstrip("/")
KEY = os.environ["TWENTY_API_KEY"]
_COLORS = ["green", "blue", "turquoise", "sky", "purple", "pink", "red",
           "orange", "yellow", "gray"]


def _gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{BASE}/metadata", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=25).read())
    except urllib.error.HTTPError as e:
        return {"HTTPError": e.code, "body": e.read().decode()[:400]}


def _person_object_id():
    r = _gql("query { objects(paging:{first:200}){ edges { node { id nameSingular } } } }")
    for e in r["data"]["objects"]["edges"]:
        if e["node"]["nameSingular"] == "person":
            return e["node"]["id"]
    raise SystemExit("No se encontró el objeto 'person'")


def _existing_field_names(person_id):
    r = _gql(
        "query($id:UUID!){ fields(paging:{first:300}, filter:{objectMetadataId:{eq:$id}})"
        "{ edges { node { name } } } }",
        {"id": person_id},
    )
    return {e["node"]["name"] for e in r["data"]["fields"]["edges"]}


def _opts(labels):
    return [{"label": l, "value": option_value(l), "color": _COLORS[i % len(_COLORS)],
             "position": i} for i, l in enumerate(labels)]


def _create(person_id, name, label, ftype, description, options=None):
    field = {"name": name, "label": label, "type": ftype,
             "objectMetadataId": person_id, "description": description}
    if options is not None:
        field["options"] = options
    r = _gql(
        "mutation($input:CreateOneFieldMetadataInput!){ createOneField(input:$input)"
        "{ id name type } }",
        {"input": {"field": field}},
    )
    return r.get("data", {}).get("createOneField") if isinstance(r, dict) else None, r


def main():
    pid = _person_object_id()
    existing = _existing_field_names(pid)
    fields = [
        ("sector", "Sector", "SELECT", "Sector del negocio del lead", _opts(get_args(Sector))),
        ("fuente", "Fuente", "SELECT", "Canal de origen del lead", _opts(get_args(Fuente))),
        ("estadoDemo", "Estado demo", "SELECT", "Etapa del pipeline de demos", _opts(get_args(Estado))),
        ("companyName", "Empresa", "TEXT", "Nombre de la empresa del lead", None),
        ("calBookingId", "Cal Booking ID", "TEXT", "ID de reserva de Cal.com (idempotencia)", None),
        ("notas", "Notas", "TEXT", "Notas del lead", None),
        ("fechaReunion", "Fecha reunión", "DATE_TIME", "Fecha/hora de la demo (UTC)", None),
    ]
    for name, label, ftype, desc, opts in fields:
        if name in existing:
            print(f"= {name}: ya existe, se omite")
            continue
        node, raw = _create(pid, name, label, ftype, desc, opts)
        if node:
            print(f"+ {name} ({ftype}) creado -> {node['id']}")
        else:
            print(f"! {name}: ERROR {json.dumps(raw, ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    main()
