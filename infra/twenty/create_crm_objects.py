#!/usr/bin/env python3
"""Crea (idempotente) los objetos custom del CRM de negocio en Twenty:
`cliente`, `deal`, `invoice`, `proyecto`, `tarea` — calco de las tablas de la base
Airtable "Duendes CRM" (que están casi vacías; esto es solo estructura para jubilar
Airtable). Los Leads/demos ya viven en el objeto `person` (piloto), no se recrean.

Las relaciones entre tablas (Cliente↔Invoices, etc.) se dejan como `airtableId` de
referencia por ahora; se pueden convertir en relaciones nativas de Twenty más adelante.

Uso (en Hetzner, alcanza Twenty):
    set -a; . /opt/n8n-recepcionista/.env; set +a
    python3 create_crm_objects.py
"""
import json
import os
import unicodedata
import urllib.error
import urllib.request


def option_value(label: str) -> str:
    """COPIA EXACTA de apps/api/services/crm/models.py:option_value (UPPER_SNAKE)."""
    nfkd = unicodedata.normalize("NFKD", label)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() else " " for c in ascii_only)
    return "_".join(cleaned.upper().split())


BASE = os.environ["TWENTY_BASE_URL"].rstrip("/")
KEY = os.environ["TWENTY_API_KEY"]
_COLORS = ["green", "blue", "turquoise", "sky", "purple", "pink", "red",
           "orange", "yellow", "gray"]


def _gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{BASE}/metadata", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
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


def _create_object(obj):
    r = _gql(
        "mutation($input:CreateOneObjectInput!){ createOneObject(input:$input){ id nameSingular } }",
        {"input": {"object": obj}})
    node = r.get("data", {}).get("createOneObject") if isinstance(r, dict) else None
    if not node:
        raise SystemExit(f"No pude crear {obj['nameSingular']}: {json.dumps(r, ensure_ascii=False)[:300]}")
    return node["id"]


def _existing_field_names(object_id):
    r = _gql(
        "query($id:UUID!){ fields(paging:{first:500}, filter:{objectMetadataId:{eq:$id}})"
        "{ edges { node { name } } } }", {"id": object_id})
    return {e["node"]["name"] for e in r["data"]["fields"]["edges"]}


def _opts(labels):
    return [{"label": l, "value": option_value(l), "color": _COLORS[i % len(_COLORS)],
             "position": i} for i, l in enumerate(labels)]


def _create_field(object_id, name, label, ftype, options=None):
    field = {"name": name, "label": label, "type": ftype,
             "objectMetadataId": object_id, "description": label}
    if options is not None:
        field["options"] = _opts(options)
    r = _gql(
        "mutation($input:CreateOneFieldMetadataInput!){ createOneField(input:$input){ id name } }",
        {"input": {"field": field}})
    return r.get("data", {}).get("createOneField") if isinstance(r, dict) else None, r


# ── Definición de los 5 objetos (name, label, type, options) ────────────────
# `name` (label del record) lo crea Twenty solo → se mapea al primary de Airtable.
SECTOR = ["Clínica Dental", "Fisioterapia", "Centro de Estética", "Peluquería / Barbería",
          "Bufete / Legal", "Gestoría", "Consultoría", "Fontanería", "Electricidad",
          "Reformas", "Comercio", "Otro"]
SERVICIO = ["Agente de Voz 24/7", "Agendamiento de Citas", "Cualificación de Leads",
            "Filtrado de Consultas", "Gestión de Urgencias", "Atención Telefónica",
            "Integración Personalizada", "Consultoría"]

OBJECTS = [
    {"nameSingular": "cliente", "namePlural": "clientes", "labelSingular": "Cliente",
     "labelPlural": "Clientes", "icon": "IconUserCheck",
     "description": "Clientes de Duendes (migrado de Airtable Duendes CRM/Clients).",
     "fields": [
         ("empresa", "Empresa", "TEXT", None),
         ("email", "Email", "TEXT", None),
         ("telefono", "Teléfono", "TEXT", None),
         ("sector", "Sector", "SELECT", SECTOR),
         ("servicio", "Servicio", "SELECT", SERVICIO),
         ("estado", "Estado", "SELECT", ["Activo", "Pausado", "Completado", "Churn"]),
         ("valorContrato", "Valor contrato", "NUMBER", None),
         ("stripeCustomerId", "Stripe Customer ID", "TEXT", None),
         ("driveFolderUrl", "Drive Folder URL", "TEXT", None),
         ("notionPageUrl", "Notion Page URL", "TEXT", None),
         ("setupCompleto", "Setup completo", "BOOLEAN", None),
         ("fechaInicio", "Fecha inicio", "DATE_TIME", None),
         ("churnRisk", "Churn risk", "SELECT", ["Bajo", "Medio", "Alto"]),
         ("ultimoCheckin", "Último check-in", "DATE_TIME", None),
         ("notasCs", "Notas CS", "TEXT", None),
         ("airtableId", "Airtable ID", "TEXT", None),
     ]},
    {"nameSingular": "deal", "namePlural": "deals", "labelSingular": "Deal",
     "labelPlural": "Deals", "icon": "IconTargetArrow",
     "description": "Oportunidades comerciales (migrado de Airtable Duendes CRM/Deals).",
     "fields": [
         ("sector", "Sector", "TEXT", None),
         ("ciudad", "Ciudad", "TEXT", None),
         ("contacto", "Contacto", "TEXT", None),
         ("estado", "Estado", "SELECT",
          ["Nuevo", "Demo", "Propuesta", "Negociacion", "Ganado", "Perdido"]),
         ("valorMensual", "Valor mensual", "NUMBER", None),
         ("setup", "Setup", "NUMBER", None),
         ("siguientePaso", "Siguiente paso", "TEXT", None),
         ("objeciones", "Objeciones", "TEXT", None),
         ("propuesta", "Propuesta", "TEXT", None),
         ("notas", "Notas", "TEXT", None),
         ("razonPerdido", "Razón perdido", "TEXT", None),
         ("source", "Source", "TEXT", None),
         ("fechaCreacion", "Fecha creación", "DATE_TIME", None),
         ("fechaActualizacion", "Fecha actualización", "DATE_TIME", None),
         ("fechaCierre", "Fecha cierre", "DATE_TIME", None),
         ("airtableId", "Airtable ID", "TEXT", None),
     ]},
    {"nameSingular": "invoice", "namePlural": "invoices", "labelSingular": "Factura",
     "labelPlural": "Facturas", "icon": "IconFileInvoice",
     "description": "Facturas (migrado de Airtable Duendes CRM/Invoices).",
     "fields": [
         ("importe", "Importe", "NUMBER", None),
         ("fecha", "Fecha", "DATE_TIME", None),
         ("estado", "Estado", "SELECT", ["Pendiente", "Pagada", "Vencida"]),
         ("stripePaymentId", "Stripe Payment ID", "TEXT", None),
         ("gmailLink", "Gmail Link", "TEXT", None),
         ("concepto", "Concepto", "TEXT", None),
         ("fechaVencimiento", "Fecha vencimiento", "DATE_TIME", None),
         ("notas", "Notas", "TEXT", None),
         ("clienteAirtableId", "Cliente (Airtable ID)", "TEXT", None),
         ("airtableId", "Airtable ID", "TEXT", None),
     ]},
    {"nameSingular": "proyecto", "namePlural": "proyectos", "labelSingular": "Proyecto",
     "labelPlural": "Proyectos", "icon": "IconFolders",
     "description": "Proyectos de cliente (migrado de Airtable Duendes CRM/Projects).",
     "fields": [
         ("estado", "Estado", "SELECT",
          ["Planificación", "En progreso", "Revisión", "Entregado", "Cerrado"]),
         ("entregables", "Entregables", "TEXT", None),
         ("fechaLimite", "Fecha límite", "DATE_TIME", None),
         ("driveUrl", "Drive URL", "TEXT", None),
         ("notionUrl", "Notion URL", "TEXT", None),
         ("horasTrabajadas", "Horas trabajadas", "NUMBER", None),
         ("clienteAirtableId", "Cliente (Airtable ID)", "TEXT", None),
         ("airtableId", "Airtable ID", "TEXT", None),
     ]},
    {"nameSingular": "tarea", "namePlural": "tareas", "labelSingular": "Tarea",
     "labelPlural": "Tareas", "icon": "IconChecklist",
     "description": "Tareas internas (migrado de Airtable Duendes CRM/Tareas).",
     "fields": [
         ("estado", "Estado", "SELECT", ["Pendiente", "Completada"]),
         ("prioridad", "Prioridad", "SELECT", ["High", "Medium", "Low"]),
         ("categoria", "Categoría", "SELECT", ["Sales", "Content", "Ops", "Admin"]),
         ("fechaVencimiento", "Fecha vencimiento", "DATE_TIME", None),
         ("fechaCompletada", "Fecha completada", "DATE_TIME", None),
         ("fechaCreacion", "Fecha creación", "DATE_TIME", None),
         ("airtableId", "Airtable ID", "TEXT", None),
     ]},
]


def main():
    for obj in OBJECTS:
        fields = obj.pop("fields")
        oid = _find_object(obj["nameSingular"])
        if oid:
            print(f"= objeto '{obj['nameSingular']}' ya existe -> {oid}")
        else:
            oid = _create_object(obj)
            print(f"+ objeto '{obj['nameSingular']}' creado -> {oid}")
        existing = _existing_field_names(oid)
        for name, label, ftype, options in fields:
            if name in existing:
                print(f"  = {name}")
                continue
            node, raw = _create_field(oid, name, label, ftype, options)
            if node:
                print(f"  + {name} ({ftype})")
            else:
                print(f"  ! {name}: ERROR {json.dumps(raw, ensure_ascii=False)[:180]}")


if __name__ == "__main__":
    main()
