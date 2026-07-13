"""
Tests del comparador de paridad Airtable `malaga` ↔ Twenty `prospecto` (C2).

Lógica pura (sin red): compara un registro de Airtable contra su gemelo en Twenty
con las mismas reglas que `infra/twenty/parity_check.py` (instante para fechas,
dígitos para teléfono) y, además, trata `noLlamar` como discrepancia de CUMPLIMIENTO
estricta (RGPD/opt-out): un `No llamar=true` que no migre NO es un mismatch genérico
más, es un fallo de cumplimiento que se reporta explícitamente.

El módulo bajo prueba vive en `infra/twenty/` (junto a su hermano parity_check.py);
lo importamos añadiendo esa carpeta al path.
"""
from __future__ import annotations

import pathlib
import sys

_INFRA_TWENTY = pathlib.Path(__file__).resolve().parents[3] / "infra" / "twenty"
if str(_INFRA_TWENTY) not in sys.path:
    sys.path.insert(0, str(_INFRA_TWENTY))

from prospecto_parity import compare_prospecto  # noqa: E402


def test_identical_record_is_clean():
    air = {
        "id": "rec1",
        "fields": {
            "title": "Bufete X",
            "phone": "+34600111222",  # Twenty guarda sin prefijo país
            "No llamar": False,
            "Estado": "Pendiente",
            "Intentos": 2,
        },
    }
    tw = {
        "airtableId": "rec1",
        "name": "Bufete X",
        "phone": "600111222",
        "noLlamar": False,
        "estado": "PENDIENTE",
        "intentos": 2,
    }
    result = compare_prospecto(air, tw)
    assert result.is_clean
    assert result.field_mismatches == []
    assert result.compliance_mismatch is None


def test_no_llamar_divergence_flagged_as_compliance_not_generic():
    """Airtable dice No llamar=true, Twenty dice false → discrepancia de cumplimiento."""
    air = {
        "id": "rec2",
        "fields": {"title": "Bufete Y", "phone": "+34600333444", "No llamar": True},
    }
    tw = {
        "airtableId": "rec2",
        "name": "Bufete Y",
        "phone": "600333444",
        "noLlamar": False,
    }
    result = compare_prospecto(air, tw)

    # Se reporta EXPLÍCITAMENTE como cumplimiento...
    assert result.compliance_mismatch is not None
    assert "llamar" in result.compliance_mismatch.lower()
    assert not result.is_clean
    # ...y NO se cuela como un mismatch de campo genérico más.
    assert not any("llamar" in m.lower() for m in result.field_mismatches)


def test_generic_field_mismatch_is_not_compliance():
    """Un teléfono distinto es mismatch de campo, no cumplimiento."""
    air = {
        "id": "rec3",
        "fields": {"title": "Bufete Z", "phone": "+34600000001", "No llamar": False},
    }
    tw = {
        "airtableId": "rec3",
        "name": "Bufete Z",
        "phone": "600000999",  # dígitos finales distintos
        "noLlamar": False,
    }
    result = compare_prospecto(air, tw)
    assert result.compliance_mismatch is None
    assert any("phone" in m or "telefono" in m for m in result.field_mismatches)
    assert not result.is_clean


def test_date_compared_by_instant_not_string():
    """ultimoIntento con .000Z de Twenty vs sin milisegundos de Airtable = mismo instante."""
    air = {
        "id": "rec4",
        "fields": {
            "title": "Bufete W",
            "phone": "+34600111000",
            "No llamar": False,
            "Último intento": "2026-07-01T10:00:00Z",
        },
    }
    tw = {
        "airtableId": "rec4",
        "name": "Bufete W",
        "phone": "600111000",
        "noLlamar": False,
        "ultimoIntento": "2026-07-01T10:00:00.000Z",
    }
    result = compare_prospecto(air, tw)
    assert result.is_clean
