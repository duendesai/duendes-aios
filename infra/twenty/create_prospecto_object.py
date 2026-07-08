#!/usr/bin/env python3
"""Crea (idempotente) el objeto custom `prospecto` en Twenty y todos sus campos.

Es el objeto de la COLA del dialer saliente: se migra aquí `malaga` (fisios) de la
base LUCIA + los despachos de la base Abogados. Reemplaza a Airtable como origen de
la cola de llamadas.

Reproducible: tras un redeploy de Twenty, reejecutar recrea objeto + campos.
Los `value` de los SELECT salen de `option_value()` (misma fuente que el piloto),
así que casan con lo que escribe la migración.

Uso (con el venv del backend, que expone option_value):
    TWENTY_BASE_URL=https://crm.duendes.net TWENTY_API_KEY=<pat> \\
        apps/api/.venv/bin/python infra/twenty/create_prospecto_object.py
"""
import json
import os
import unicodedata
import urllib.error
import urllib.request


def option_value(label: str) -> str:
    """UPPER_SNAKE slug para los `value` de SELECT en Twenty.

    COPIA EXACTA de apps/api/services/crm/models.py:option_value. Debe seguir
    casando con lo que escribe el adapter/migración (misma normalización)."""
    nfkd = unicodedata.normalize("NFKD", label)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() else " " for c in ascii_only)
    return "_".join(cleaned.upper().split())


BASE = os.environ["TWENTY_BASE_URL"].rstrip("/")
KEY = os.environ["TWENTY_API_KEY"]
_COLORS = ["green", "blue", "turquoise", "sky", "purple", "pink", "red",
           "orange", "yellow", "gray"]

# ─── SELECT: sets limpios (deduplicados de la suciedad de Airtable) ──────────
ESTADO = ["Pendiente", "No contesta", "Contestador", "Comunica", "Gatekeeper",
          "Info solicitada", "Rellamar", "Interés cálido", "Demo agendada",
          "No interesa", "No interesa ahora", "No cualifica", "Ilocalizable",
          "Número erróneo", "Número inexistente", "No llamar"]
PRIORIDAD = ["Alta", "Media", "Baja", "Sin calificar"]
CAMPANA = ["Fisios Málaga", "Despachos Madrid", "Colegios Fisioterapia",
           "Webinar Colegios"]
FUENTE = ["Apify Google Maps", "Manual", "Referencia", "LinkedIn Sales Nav",
          "Meta Ads", "Web formulario", "Otro", "Test interno", "Cold email"]
OUTCOME = ["demo_agendada", "no_interesa", "callback", "no_llamar", "no_contesta"]


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


def _find_object(name_singular):
    r = _gql("query { objects(paging:{first:200}){ edges { node { id nameSingular } } } }")
    for e in r["data"]["objects"]["edges"]:
        if e["node"]["nameSingular"] == name_singular:
            return e["node"]["id"]
    return None


def _create_object():
    obj = {
        "nameSingular": "prospecto", "namePlural": "prospectos",
        "labelSingular": "Prospecto", "labelPlural": "Prospectos",
        "icon": "IconPhoneOutgoing",
        "description": "Cola del dialer saliente (fisios, abogados). Migrado de Airtable malaga.",
    }
    r = _gql(
        "mutation($input:CreateOneObjectInput!){ createOneObject(input:$input){ id nameSingular } }",
        {"input": {"object": obj}},
    )
    node = r.get("data", {}).get("createOneObject") if isinstance(r, dict) else None
    if not node:
        raise SystemExit(f"No pude crear el objeto prospecto: {json.dumps(r, ensure_ascii=False)[:400]}")
    return node["id"]


def _existing_field_names(object_id):
    r = _gql(
        "query($id:UUID!){ fields(paging:{first:500}, filter:{objectMetadataId:{eq:$id}})"
        "{ edges { node { name } } } }",
        {"id": object_id},
    )
    return {e["node"]["name"] for e in r["data"]["fields"]["edges"]}


def _opts(labels):
    return [{"label": l, "value": option_value(l), "color": _COLORS[i % len(_COLORS)],
             "position": i} for i, l in enumerate(labels)]


def _create_field(object_id, name, label, ftype, description, options=None):
    field = {"name": name, "label": label, "type": ftype,
             "objectMetadataId": object_id, "description": description}
    if options is not None:
        field["options"] = options
    r = _gql(
        "mutation($input:CreateOneFieldMetadataInput!){ createOneField(input:$input){ id name type } }",
        {"input": {"field": field}},
    )
    node = r.get("data", {}).get("createOneField") if isinstance(r, dict) else None
    return node, r


# (name, label, type, options)  ── `name` (label del record) lo crea Twenty solo
FIELDS = [
    # ── Cola del dialer (críticos) ──
    ("phone", "Teléfono", "TEXT", None),
    ("estado", "Estado", "SELECT", ESTADO),
    ("prioridad", "Prioridad", "SELECT", PRIORIDAD),
    ("campana", "Campaña", "SELECT", CAMPANA),
    ("fuente", "Fuente", "SELECT", FUENTE),
    ("outcome", "Outcome", "SELECT", OUTCOME),
    ("intentos", "Intentos", "NUMBER", None),
    ("ultimoIntento", "Último intento", "DATE_TIME", None),
    ("proximoIntento", "Próximo intento", "DATE_TIME", None),
    ("noLlamar", "No llamar", "BOOLEAN", None),
    ("enriquecido", "Enriquecido", "BOOLEAN", None),
    # ── Negocio / contacto ──
    ("categoria", "Categoría", "TEXT", None),
    ("subSector", "Sub-sector", "TEXT", None),
    ("city", "Ciudad", "TEXT", None),
    ("street", "Dirección", "TEXT", None),
    ("website", "Web", "TEXT", None),
    ("email", "Email contacto", "TEXT", None),
    ("reviewsCount", "Reseñas", "NUMBER", None),
    ("score", "Score", "NUMBER", None),
    ("tamano", "Tamaño", "TEXT", None),
    ("presenciaDigital", "Presencia digital", "TEXT", None),
    ("bookingOnline", "Booking online", "BOOLEAN", None),
    ("redesSociales", "Redes sociales", "TEXT", None),
    # ── Seguimiento de llamada ──
    ("contactoAlcanzado", "Contacto alcanzado", "TEXT", None),
    ("contactoNombre", "Contacto nombre", "TEXT", None),
    ("motivoPerdida", "Motivo pérdida", "TEXT", None),
    ("callbackSolicitado", "Callback solicitado", "DATE_TIME", None),
    ("callbackNotas", "Callback notas", "TEXT", None),
    ("agendadaFecha", "Agendada fecha", "DATE_TIME", None),
    ("crmUrl", "CRM Duendes URL", "TEXT", None),
    # ── Enriquecimiento + trazabilidad ──
    ("datosEnriquecidos", "Datos enriquecidos", "TEXT", None),
    ("notas", "Notas", "TEXT", None),
    ("airtableId", "Airtable ID", "TEXT", None),  # idempotencia + linkeo Calls futuro
]


def main():
    oid = _find_object("prospecto")
    if oid:
        print(f"= objeto 'prospecto' ya existe -> {oid}")
    else:
        oid = _create_object()
        print(f"+ objeto 'prospecto' creado -> {oid}")

    existing = _existing_field_names(oid)
    for name, label, ftype, opts in FIELDS:
        if name in existing:
            print(f"  = {name}: ya existe")
            continue
        options = _opts(opts) if opts is not None else None
        node, raw = _create_field(oid, name, label, ftype, label, options)
        if node:
            print(f"  + {name} ({ftype}) -> {node['id']}")
        else:
            print(f"  ! {name}: ERROR {json.dumps(raw, ensure_ascii=False)[:220]}")


if __name__ == "__main__":
    main()
