# Apply Progress — change `crm` (Fases 4-8, Standard Mode)

> Live progress file. Updated incrementally as each file lands on disk.

## Scope of this apply run

Fases 4-8 del `tasks.md`. Fase 3 (puerto + modelos + errores) YA estaba en disco antes de empezar; no se reescribe.

- Fase 4 — `AirtableCRMAdapter` (envuelve `AirtableMultiClient`)
- Fase 5 — `TwentyCRMAdapter` (REST + GraphQL)
- Fase 6 — `DualWriteCRMClient` (primary + secondary)
- Fase 7 — wiring: `config.py` (crm_backend + twenty settings) + `deps.py` (`get_crm`) + `routers/calls.py` (`book_demo_and_create_lead` → puerto)
- Fase 8 — pytest + respx dev deps + `tests/test_crm_contract.py`

Fuera de scope de este run: Fases 0-2 (infra Hetzner, modelo Twenty), 9 (n8n), 10-13 (paridad/backfill/backup/cutover — Oscar-manual).

## Status

- [x] Leídos Fase 3 + design + specs + código de integración (airtable_multi, calls, config, deps)
- [x] Fase 4 — airtable_adapter.py (`AirtableCRMAdapter`, mapeo idéntico + typecast, idempotencia, patch parcial, errores→CRMError)
- [x] Fase 5 — twenty_adapter.py (`TwentyCRMAdapter`, REST create/update/get + GraphQL find_lead, normalización sector/estado/fecha UTC, idempotencia, patch parcial, errores→CRMError/subclases)
- [x] Fase 6 — dual_write.py (`DualWriteCRMClient`, primary bloqueante + secondary best-effort logueado, genérico en roles; `__init__.py` exporta adaptadores)
- [x] Fase 7 — config.py (`crm_backend` + `twenty_base_url` + `twenty_api_key`), deps.py (`get_crm()`), routers/calls.py (inyecta `crm`) + calls_service.py (`book_demo_and_create_lead` usa `crm.create_lead`)
- [x] Fase 8 — requirements + pytest.ini + tests/__init__.py + tests/conftest.py + tests/test_crm_contract.py
- [x] Tests ejecutados — **18 passed**

## Test result

```
cd apps/api && .venv/bin/python -m pytest tests/ -q
18 passed in 1.41s
```

Entorno: `apps/api/.venv` (Python 3.13.12), ya presente con las deps de runtime;
se instalaron `pytest==8.3.4`, `pytest-asyncio==0.25.2`, `respx==0.22.0`.
respx mockea el HTTP de Airtable (`api.airtable.com`) y Twenty (`/rest/people` +
`/graphql`) sobre un backend en memoria stateful (create/get/update/find reales
contra el store), de forma que idempotencia y patch parcial se verifican de
extremo a extremo sin red.

Cobertura del test de contrato (ambos adaptadores salvo donde se indica):
- create_lead → LeadRef con id/provider/url
- get_lead roundtrip de campos
- find_lead por email / por cal_booking_id / miss→None
- idempotencia por email y por cal_booking_id (adaptador en solitario, sin dual-write)
- patch parcial preserva campos no incluidos (verificado vía get_lead)
- normalización Twenty (Clínicas→Salud, Nuevo→Reunión agendada) y NO-normalización Airtable

## Verificación de wiring (import check)

`python -c "import config, deps; from services.crm import *; import routers.calls, services.calls_service"`
→ OK. `deps.get_crm()` con backend default (`airtable`) devuelve `AirtableCRMAdapter`
sin tocar red. `book_demo_and_create_lead` ahora recibe `(air, calcom, crm, payload)`.

## Regresión cero (Fase 7.4, pendiente de verificación manual de Oscar en prod)

Con `CRM_BACKEND=airtable` (default) el paso 2 de `/calcom/book` escribe en Airtable
con el MISMO mapeo de campos + `typecast=True` + mismo formato de `crm_url`
(`https://airtable.com/{base}/{table}/{id}`). Única diferencia de comportamiento:
el adaptador hace un `find_lead` (idempotencia D1) antes de crear — para un booking
nuevo es un GET extra que devuelve None y luego crea idéntico. El paso 3 (PATCH
`malaga`) sigue en Airtable directo, fuera del puerto (por diseño).

## Code-review fixes (2026-07-07)

Correcciones de hallazgos confirmados del code review, con tests que los cubren.

### Producción

- **FIX 1 (HIGH bug) — `twenty_adapter.py::_raise_for_status`**: el guardia mutante
  `if resp.status_code < 9999:  # MUTANTE` (dead-code toda la traducción de errores)
  se cambió a `if resp.status_code < 400:` y se quitó el comentario. Ahora 401/403 →
  `CRMAuthError`, 400/422 → `CRMValidationError`, 404 → `CRMNotFoundError`, resto →
  `CRMError`. Verificado: 4 tests de error Twenty fallan si se restaura el mutante.
- **FIX 3 (MEDIUM regresión) — pre-check idempotencia read-tolerant (AMBOS adaptadores)**:
  el `find_lead(...)` de pre-check en `create_lead` (Airtable y Twenty) se envolvió en
  `try/except CRMError`: si la LECTURA falla (transitorio), `logger.warning(...)` y se
  CONTINÚA creando ("no se pudo verificar" = "no existe"). El error del POST de creación
  NO se traga (sigue propagando). Se añadió `import logging`/`logger` a `airtable_adapter.py`.
- **FIX 9 (LOW) — `twenty_adapter.py::_person_to_ref`**: `person["id"]` (KeyError potencial)
  → `pid = person.get("id")`; si falsy, `raise CRMError("Twenty devolvió una respuesta sin
  id de Person", detail=person)`. Manejo de error uniforme en create/update/find.
- **#4 (calls_service.py `except Exception` alrededor de `crm.create_lead`)**: NO TOCADO
  (diferido a decisión de cutover-hardening).

### Tests añadidos (17 nuevos; 18 → 35 total)

- **T-errors** (`test_crm_contract.py`): errores HTTP → `CRMError` tipado en ambos adaptadores.
  Twenty vía respx (401→`CRMAuthError`, 422→`CRMValidationError`, 500→`CRMError`, 404 get→None) +
  Airtable vía fake (500 find→`CRMError`, 422 create→`CRMError`, 500 update→`CRMError`, 404 get→None).
  Se asserta `status_code`/`detail`. Incluye 2 tests de tolerancia del pre-check (FIX 3).
- **T-dualwrite** (`test_crm_dualwrite.py`, módulo nuevo, adaptadores fake in-memory):
  fallo de `secondary` no bloquea y loguea (devuelve ref de primary); fallo de `primary`
  propaga y NO invoca `secondary`; simétrico en dirección invertida (post-cutover).
- **T-fecha** (`test_crm_contract.py`): Twenty normaliza `fecha_reunion` con offset no-UTC
  (`+02:00`) y naive a UTC canónico (`2026-07-10T09:00:00+00:00`); + assert de `fecha_reunion`
  añadido al test de patch parcial existente (que lo prometía en el docstring y no lo comprobaba).
- **T-roundtrip** (`test_crm_contract.py`): los 10 campos de `Lead` sobreviven create→get en
  ambos adaptadores (`fecha_reunion` comparada por instante, no por string).
- **T-precedence** (`test_crm_contract.py`): en `find_lead`, email gana sobre `cal_booking_id`;
  fallback a `cal_booking_id` si el email no matchea. Ambos adaptadores.

## Test result (post code-review fixes)

```
cd apps/api && .venv/bin/python -m pytest tests/ -q
35 passed in 2.29s
```
