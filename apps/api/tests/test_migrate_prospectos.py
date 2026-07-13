"""
Test mínimo de `migrate_prospectos.map_record` para el campo de teléfono configurable.

Cubre la clase de fallo que casi migra los 164 abogados sin teléfono: el mapeo leía
siempre `f.get("phone")`, pero en la base de abogados el teléfono vive en el campo
`Attachment Summary`. Un prospecto sin `phone` cae de la cola del dialer (fallo silencioso).

El script `migrate_prospectos.py` lee credenciales en el top del módulo; les damos
valores dummy ANTES de importarlo (no se usan: `map_record` es pura, sin red).
"""
from __future__ import annotations

import os

os.environ.setdefault("AIRTABLE_API_KEY", "test-key")
os.environ.setdefault("TWENTY_BASE_URL", "https://twenty.test")
os.environ.setdefault("TWENTY_API_KEY", "test-key")

import pathlib  # noqa: E402
import sys  # noqa: E402

_INFRA_TWENTY = pathlib.Path(__file__).resolve().parents[3] / "infra" / "twenty"
if str(_INFRA_TWENTY) not in sys.path:
    sys.path.insert(0, str(_INFRA_TWENTY))

import migrate_prospectos as mp  # noqa: E402


def test_default_phone_field_regresion_fisios():
    """Sin --phone-field, el teléfono se lee de `phone` (comportamiento fisios/malaga)."""
    rec = {"id": "rec1", "fields": {"Name": "Fisio X", "phone": "+34600111222"}}
    out = mp.map_record(rec)
    assert out["phone"] == "+34600111222"


def test_phone_field_override_abogados():
    """Con --phone-field='Attachment Summary', el teléfono se popula desde ahí."""
    rec = {"id": "rec2", "fields": {"Name": "Bufete Y", "Attachment Summary": "+34600333444"}}
    out = mp.map_record(rec, phone_field="Attachment Summary")
    assert out["phone"] == "+34600333444"


def test_default_phone_field_misses_abogados_layout():
    """Documenta el fallo evitado: con el default, el teléfono de abogados no se recoge."""
    rec = {"id": "rec3", "fields": {"Name": "Bufete Z", "Attachment Summary": "+34600555666"}}
    out = mp.map_record(rec)
    assert "phone" not in out
