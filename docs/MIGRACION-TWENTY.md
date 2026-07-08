# Migración Airtable → Twenty (dialer) — Runbook vivo

> Fecha: 2026-07-08. Decisión de Oscar (bajo incidente): jubilar Airtable y llevar
> TODO a Twenty, empezando por el dialer. Detonante: el plan Free de Airtable topa a
> **1.000 registros/base**; la base LUCIA se pasó (había 160 abogados metidos por error
> en la base de fisios) y bloqueó el teléfono saliente del comercial. Oscar separó los
> abogados a una base nueva y, en pánico, borró Calls (511) + Emails (200) para bajar
> del tope. El teléfono quedó desbloqueado.

## Estado actual

### ✅ Hecho
- **Objeto `prospecto` en Twenty** (`crm.duendes.net`), 34 campos. Script idempotente:
  `infra/twenty/create_prospecto_object.py`. Object id `900d6116-…`.
- **175 fisios migrados** (base LUCIA `malaga` → Twenty `prospecto`), 0 errores, sin
  duplicados (idempotente por `airtableId`). 133 en estado `PENDIENTE` (la cola).
  Script: `infra/twenty/migrate_prospectos.py` (throttle 0.7s + backoff 429).
- Twenty tiene rate limit **100 req/min**: la migración lo respeta.
- **Recableo teams-api LISTO (sin desplegar aún):**
  - `apps/api/services/prospecto_twenty.py` — cliente + casos de uso Twenty del dialer
    (fetch_queue / submit_call_result / count_campaigns / fetch_agenda /
    fetch_prospect_detail / book_demo_and_create_lead), DTOs idénticos al camino Airtable.
  - Flag `dialer_backend` en `config.py` (default `airtable`) + branch en `routers/calls.py`
    (aditivo, cero regresión en el camino vivo) + provider en `deps.py`.
  - Queries GraphQL (list/get) y PATCH REST validados contra Twenty real (HTTP 200).
  - Tests: `apps/api/tests/test_prospecto_twenty.py` (6) → suite **43 passed**.
  - Sin gating por email (Emails borrado) y sin log `Calls` por ahora (el resultado
    actualiza el propio prospecto; objeto `llamada` = iteración futura).

### ✅ CRM de negocio modelado en Twenty (2026-07-08)
- Objetos custom `cliente`, `deal`, `invoice`, `proyecto`, `tarea` creados (calco de las
  tablas de la base Airtable "Duendes CRM"). Script: `infra/twenty/create_crm_objects.py`.
- **Decisión de Oscar:** objetos CUSTOM (no nativos) + **un solo corte grande** cuando esté
  TODO reapuntado (el comercial sigue en Airtable hasta entonces).
- **Sin datos que migrar:** la base Duendes CRM está casi vacía (Leads=1 ya en Twenty como
  `person`; Clients/Projects/Invoices=0; Tareas/Deals=1 fila plantilla vacía). Los ÚNICOS
  datos reales en todo Airtable son los prospectos del dialer.

### ⬜ Pendiente para el corte único
- **164 abogados** → `prospecto` (necesita PAT con acceso a base `Abogados` appqDawY24kiaPWFu;
  `pat58` no la ve). `migrate_prospectos.py --base appqDawY24kiaPWFu --table <tbl>`.
- **Reapuntar los escritores automáticos de Airtable a Twenty/teams-api** (los que estén VIVOS
  — CONFIRMAR con Oscar cuáles corren de verdad):
  - Tools ElevenLabs de LUC.IA (voz IA): `log_call`/`update_lead_outcome`/`create_crm_lead`
    escriben Airtable directo → reapuntar a `/api/calls/result` + `/api/calls/crm-lead`
    (ya escriben Twenty). Ojo: la config vive en ElevenLabs (dashboard/API), no solo en el repo.
  - n8n webinar-lead → `/api/calls/crm-lead`.
  - smartlead_sync / despachos_import (si el cold email está activo).
- **CRM de negocio manual:** Oscar pasa a usar la UI de Twenty para clientes/deals/facturas
  (los objetos ya están). No hay scripts vivos que migrar (la base está vacía + el modelo de
  "departamentos" scripts/ está DISUELTO por el override del proyecto).
- **Corte + apagado:** deploy teams-api + `DIALER_BACKEND=twenty`, verificar, Airtable
  solo-lectura de reserva unos días, rotar los 2 PAT, retirar.

## Cables críticos del dialer (del inventario del repo)

El teléfono del **comercial humano** (app `apps/teams`, SDR) usa teams-api:
- **Cola:** `GET /api/calls/queue` → `calls_service.fetch_queue` (lee `malaga` + `Emails`,
  ordena warm/cold/callbacks). `apps/api/services/calls_service.py:227`.
- **Resultado:** `POST /api/calls/result` → `submit_call_result` (POST `Calls` + PATCH
  `malaga`). `calls_service.py:591`.
- Otros: `/calls/agenda` (callbacks), `/calls/campaigns` (conteo), `/calls/prospect/{id}` (ficha).

Nota: la voz IA LUC.IA (ElevenLabs, NO VAPI) usa otro camino (snapshots JSON ad-hoc de
`malaga` + tools ElevenLabs que escriben Airtable directo). Eso se recablea aparte.

## Runbook de cutover (esta tarde, con Oscar, comercial ya libre)

El código ya está. El cutover es: desplegar + flip del flag + verificar. Rollback = quitar el flag.

1. **Desplegar teams-api** con el código nuevo (flag sigue en `airtable`, cero cambio de
   comportamiento): `infra/hetzner/deploy.sh` (empaqueta `apps/api` → scp → rebuild
   container). Verificar que arranca: `docker compose … exec -T teams-api python -c "import routers.calls"`.
2. **Flip:** en el `.env` de Hetzner poner `DIALER_BACKEND=twenty` y recrear el container
   teams-api. Verificar: `docker compose … exec -T teams-api python -c "from config import get_settings as g; print(g().dialer_backend)"` → `twenty`.
3. **Verificar end-to-end:**
   - `GET https://teams.duendes.net/api/calls/queue?mode=cold` → devuelve prospectos de Twenty
     (deben salir ~133 PENDIENTE fisios; `total` > 0).
   - `GET /api/calls/campaigns` → cuenta "Fisios Málaga".
   - El comercial hace UNA llamada de prueba y registra resultado → `POST /api/calls/result`
     → comprobar en Twenty que el prospecto subió `intentos` y cambió `estado`.
4. **Si algo falla:** `DIALER_BACKEND=airtable` + recrear container → vuelve al camino vivo
   (Airtable) al instante. Airtable sigue teniendo los datos intactos.
5. **Después (no bloquea al comercial):** migrar los 164 abogados (con el PAT), modelar el
   objeto `llamada`, y dejar Airtable en solo-lectura de reserva unos días antes de retirarlo.

## 🔴 Secretos a rotar (al jubilar Airtable)
- PAT raíz de Airtable (base CRM + LUCIA), en `.env`. Hardcodeado además en el
  workflow n8n "LUCIA - Dialer" (nodo HTTP) y referenciado por las tools ElevenLabs.
- PAT de cold-outreach (`cold-outreach/.env`, base OUTREACH).
- Los `secret_id` de ElevenLabs Secrets Manager que apuntan al PAT raíz.
- La `TWENTY_API_KEY` se pegó en chat en una sesión previa → rotar también.
(Valores concretos: ver los `.env`, NUNCA aquí.)

## Archivos nuevos de esta migración
- `infra/twenty/create_prospecto_object.py` — modela `prospecto` en Twenty.
- `infra/twenty/migrate_prospectos.py` — vuelca Airtable → Twenty `prospecto`.
- `data/abogados-despachos-madrid-backup.json` — (vacío; el backup por script no cuajó
  porque `pat58` no ve la base Abogados; los 164 viven en la base Airtable `Abogados`).
