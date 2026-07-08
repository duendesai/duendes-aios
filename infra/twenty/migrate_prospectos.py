#!/usr/bin/env python3
"""Migra prospectos de Airtable → objeto `prospecto` de Twenty (idempotente).

Origen por defecto: base LUCIA `malaga` (fisios). Parametrizable por --base/--table
para migrar también la base Abogados (cuando haya un PAT con acceso).

- Lee Airtable con `AIRTABLE_API_KEY` (raw API, campos por NOMBRE).
- Escribe Twenty con `TWENTY_API_KEY` (REST `POST /rest/prospectos`).
- Idempotente por `airtableId`: pre-carga los ya existentes en Twenty y los salta,
  así reejecutar no duplica.
- SELECT: mapea etiqueta Airtable → etiqueta limpia (alias de duplicados) →
  `option_value()` (UPPER_SNAKE). Si el value no existe como opción, OMITE ese campo
  (no rompe el registro) y lo cuenta.

Uso (en Hetzner, que alcanza Twenty y tiene el .env):
    set -a; . /opt/n8n-recepcionista/.env; set +a
    python3 migrate_prospectos.py --dry-run
    python3 migrate_prospectos.py --limit 3      # valida en 3 reales
    python3 migrate_prospectos.py                # bulk completo
"""
import argparse
import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

AIR_KEY = os.environ["AIRTABLE_API_KEY"]
TW_BASE = os.environ["TWENTY_BASE_URL"].rstrip("/")
TW_KEY = os.environ["TWENTY_API_KEY"]

DEFAULT_BASE = "app5WbiXR0qXGTc3r"   # LUCIA Bienestar
DEFAULT_TABLE = "tblCyn7fjgBJM8rkF"  # malaga (fisios)


def option_value(label: str) -> str:
    """COPIA EXACTA de apps/api/services/crm/models.py:option_value (UPPER_SNAKE)."""
    nfkd = unicodedata.normalize("NFKD", label)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() else " " for c in ascii_only)
    return "_".join(cleaned.upper().split())


# ── SELECT: mismos sets limpios que create_prospecto_object.py ──────────────
ESTADO = ["Pendiente", "No contesta", "Contestador", "Comunica", "Gatekeeper",
          "Info solicitada", "Rellamar", "Interés cálido", "Demo agendada",
          "No interesa", "No interesa ahora", "No cualifica", "Ilocalizable",
          "Número erróneo", "Número inexistente", "No llamar"]
PRIORIDAD = ["Alta", "Media", "Baja", "Sin calificar"]
CAMPANA = ["Fisios Málaga", "Despachos Madrid", "Colegios Fisioterapia", "Webinar Colegios"]
FUENTE = ["Apify Google Maps", "Manual", "Referencia", "LinkedIn Sales Nav",
          "Meta Ads", "Web formulario", "Otro", "Test interno", "Cold email"]
OUTCOME = ["demo_agendada", "no_interesa", "callback", "no_llamar", "no_contesta"]

# Alias de la suciedad de Airtable → etiqueta limpia (antes de option_value)
ESTADO_ALIAS = {"Interes calido": "Interés cálido", "Agendada": "Demo agendada"}

# Valores válidos (option_value de cada set limpio) por campo SELECT de prospecto
_VALID = {
    "estado": {option_value(x) for x in ESTADO},
    "prioridad": {option_value(x) for x in PRIORIDAD},
    "campana": {option_value(x) for x in CAMPANA},
    "fuente": {option_value(x) for x in FUENTE},
    "outcome": {option_value(x) for x in OUTCOME},
}
_dropped_selects: dict[str, int] = {}


def _sel(field: str, label, alias: dict | None = None):
    """Etiqueta Airtable → value válido de Twenty, o None si no casa (se omite)."""
    if not label:
        return None
    clean = (alias or {}).get(label, label)
    value = option_value(clean)
    if value in _VALID[field]:
        return value
    _dropped_selects[field] = _dropped_selects.get(field, 0) + 1
    return None


# ── Airtable ────────────────────────────────────────────────────────────────
def read_airtable(base: str, table: str) -> list[dict]:
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        url = f"https://api.airtable.com/v0/{base}/{table}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AIR_KEY}"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        records += data["records"]
        offset = data.get("offset")
        if not offset:
            return records


# ── Twenty ────────────────────────────────────────────────────────────────
def _tw_graphql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        f"{TW_BASE}/graphql", data=body,
        headers={"Authorization": f"Bearer {TW_KEY}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def existing_airtable_ids() -> set[str]:
    ids, after = set(), None
    while True:
        q = ("query($after:String){ prospectos(first:60, after:$after){ "
             "edges{ node{ airtableId } } pageInfo{ hasNextPage endCursor } } }")
        data = _tw_graphql(q, {"after": after}).get("data", {}).get("prospectos")
        if not data:
            return ids
        for e in data["edges"]:
            aid = e["node"].get("airtableId")
            if aid:
                ids.add(aid)
        if not data["pageInfo"]["hasNextPage"]:
            return ids
        after = data["pageInfo"]["endCursor"]


def create_prospecto(payload: dict, retries: int = 4) -> tuple[bool, str]:
    """POST a Twenty. En 429 (rate limit 100/min) espera y reintenta."""
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{TW_BASE}/rest/prospectos", data=body,
            headers={"Authorization": f"Bearer {TW_KEY}", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30).read()
            return True, ""
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(62)  # la ventana del rate limit es de 60s
                continue
            return False, f"{e.code}: {e.read().decode()[:200]}"
        except urllib.error.URLError as e:
            return False, f"URLError: {e}"
    return False, "429: reintentos agotados"


# ── Mapeo malaga → prospecto ────────────────────────────────────────────────
def _num(v):
    return v if isinstance(v, (int, float)) else None


def _text(v):
    if v is None:
        return None
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def map_record(rec: dict) -> dict:
    f = rec.get("fields", {})
    p: dict = {"airtableId": rec["id"]}

    def put(key, val):
        if val is not None and val != "":
            p[key] = val

    put("name", _text(f.get("title") or f.get("Name")))
    put("phone", _text(f.get("phone")))
    put("estado", _sel("estado", f.get("Estado"), ESTADO_ALIAS))
    put("prioridad", _sel("prioridad", f.get("Prioridad")))
    put("campana", _sel("campana", f.get("Campaña")))
    put("fuente", _sel("fuente", f.get("Fuente")))
    put("outcome", _sel("outcome", f.get("outcome")))
    put("intentos", _num(f.get("Intentos")))
    put("ultimoIntento", f.get("Último intento"))
    put("proximoIntento", f.get("Próximo intento"))
    p["noLlamar"] = bool(f.get("No llamar"))
    p["enriquecido"] = bool(f.get("Enriquecido"))
    put("categoria", _text(f.get("categoryName")))
    put("subSector", _text(f.get("Sub-sector")))
    put("city", _text(f.get("city")))
    put("street", _text(f.get("street")))
    put("website", _text(f.get("website")))
    put("email", _text(f.get("Email contacto")))
    put("reviewsCount", _num(f.get("reviewsCount")))
    put("score", _num(f.get("Score")))
    put("tamano", _text(f.get("Tamaño")))
    put("presenciaDigital", _text(f.get("Presencia digital")))
    p["bookingOnline"] = bool(f.get("Booking online"))
    put("redesSociales", _text(f.get("Redes sociales")))
    put("contactoAlcanzado", _text(f.get("Contacto alcanzado")))
    put("contactoNombre", _text(f.get("Contacto nombre")))
    put("motivoPerdida", _text(f.get("Motivo pérdida")))
    put("callbackSolicitado", f.get("Callback solicitado"))
    put("callbackNotas", _text(f.get("Callback notas")))
    put("agendadaFecha", f.get("Agendada fecha"))
    put("crmUrl", _text(f.get("CRM Duendes URL")))
    put("datosEnriquecidos", _text(f.get("Datos enriquecidos")))
    put("notas", _text(f.get("Notas")))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = todos")
    args = ap.parse_args()

    records = read_airtable(args.base, args.table)
    print(f"Airtable {args.base}/{args.table}: {len(records)} registros")

    seen = set() if args.dry_run else existing_airtable_ids()
    print(f"Ya en Twenty (por airtableId): {len(seen)}")

    to_do = [r for r in records if r["id"] not in seen]
    if args.limit:
        to_do = to_do[:args.limit]
    print(f"A migrar: {len(to_do)}{' (LIMIT)' if args.limit else ''}\n")

    created = skipped = errors = 0
    for rec in to_do:
        payload = map_record(rec)
        name = payload.get("name", "(sin nombre)")
        if args.dry_run:
            print(f"  [dry] {name} | estado={payload.get('estado')} "
                  f"campana={payload.get('campana')} phone={payload.get('phone')}")
            continue
        ok, err = create_prospecto(payload)
        if ok:
            created += 1
            print(f"  + {name}")
        else:
            errors += 1
            print(f"  ! {name}: {err}")
        time.sleep(0.7)  # ~85/min, bajo el límite de 100/min de Twenty

    print(f"\nResumen: {created} creados, {skipped} saltados, {errors} errores")
    if _dropped_selects:
        print(f"SELECT omitidos (valor no en el set limpio): {_dropped_selects}")
    if args.dry_run:
        print("DRY-RUN: no se escribió nada.")


if __name__ == "__main__":
    main()
