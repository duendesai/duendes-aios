# Tasks: Migrar CRM Airtable → Twenty (piloto Leads/demos)

## Fase 0: Gate de infra — RAM (BLOQUEANTE, Oscar-manual)

- [ ] 0.1 [Oscar] Ejecutar `ssh root@46.225.161.222 free -h` y reportar RAM libre al AIOS.
- [ ] 0.2 [AIOS] Decidir con el dato: si libre < 8 GB → redimensionar el Hetzner (plan Oscar) antes de 1.x. Si ≥ 8 GB → avanzar.
- [ ] 0.3 [Oscar] Si aplica resize, confirmarlo hecho y volver a correr `free -h` para verificar.

**No avanzar a Fase 1 sin 0.2 resuelto.**

## Fase 1: Infra Twenty en Hetzner (depende de Fase 0)

- [ ] 1.1 [Oscar] Crear el registro DNS A (y AAAA si hay IPv6) `crm.duendes.net` → IP del VPS Hetzner, en el proveedor DNS de `duendes.net` (la zona ya existe, sirve `n8n`/`api` desde la misma IP). Verificar propagación con `dig +short crm.duendes.net` **antes** de `docker compose up`.
- [ ] 1.2 Definir el modelo de red Docker: red `twenty-network` propia para `twenty-server`+`twenty-worker`+Postgres+Redis de Twenty; Postgres/Redis de Twenty SIN publicar puertos al host. Decidir y documentar cómo Caddy (que vive en la red de n8n) alcanza a `twenty-server`: (a) unir solo `twenty-server` a la red de n8n como red externa, o (b) publicar `twenty-server` en loopback del host y proxy por ahí.
- [ ] 1.3 Verificar que los puertos de host usados por el Postgres/Redis de n8n no colisionan con los que use (si alguno) el stack de Twenty, antes de escribir el compose.
- [ ] 1.4 Crear `infra/hetzner/twenty/docker-compose.yml`: servicios Twenty (server+worker), Postgres propio, Redis propio (sin compartir instancia/credenciales con n8n), aplicando el modelo de red de 1.2 y las credenciales vía `env_file` (nunca inline en el YAML versionado).
- [ ] 1.5 Pinnear imagen Twenty estable ≥2.1.0 (verificar tag exacto en Docker Hub/GHCR antes de escribir el compose; NO usar `latest`).
- [ ] 1.6 Configurar `SERVER_URL=https://crm.duendes.net` y `FRONT_BASE_URL=https://crm.duendes.net` (idénticos, https) para evitar redirect-loop.
- [ ] 1.7 Añadir healthcheck al servicio `twenty-server` del compose (endpoint de salud de Twenty).
- [ ] 1.8 Parametrizar el destino en `infra/hetzner/sync-env.sh` (hoy hardcodeado a `/opt/n8n-recepcionista/.env`) para poder escribir también en `/opt/twenty/.env`: credenciales Postgres/Redis de Twenty, `APP_SECRET`, `TWENTY_API_KEY`. Añadir además `TWENTY_API_KEY` y `CRM_BACKEND` al `.env` de n8n (lo único que consume `teams-api`). `/opt/twenty/.env` queda fuera de git.
- [ ] 1.9 Añadir subdominio `crm.duendes.net` a `infra/hetzner/Caddyfile` (reverse proxy → puerto interno de Twenty, según lo decidido en 1.2).
- [ ] 1.10 [Oscar] `docker compose up -d` en `/opt/twenty/`, verificar arranque y acceso a `https://crm.duendes.net`.
- [ ] 1.11 [Oscar] Generar API key/token (PAT) de Twenty y guardarla en `/opt/twenty/.env` (vía 1.8, no en secret manager separado).
- [ ] 1.12 Configurar alerta mínima de monitorización: cron en el VPS que haga `curl` al endpoint de salud de Twenty y avise por email/Telegram tras N fallos consecutivos. Objetivo: no quemar en silencio la ventana de dual-write (Fase 11) si Twenty cae.

## Fase 2: Modelo de datos en Twenty (depende de 1.6)

- [ ] 2.1 Vía Twenty Metadata API (o UI admin), crear custom fields en objeto **Person**: `sector` (SELECT), `fuente` (SELECT), `estadoDemo` (SELECT), `fechaReunion` (DATE_TIME), `calBookingId` (TEXT), `notas` (TEXT), `companyName` (TEXT).
- [ ] 2.2 Cargar opciones válidas de los SELECT: `sector` (Clínica Dental/Fisioterapia/Bufete/Salud/…), `fuente` (Meta Ads/Web/Referido/Outreach/Webinar/…), `estadoDemo` (Reunión agendada/Propuesta enviada/Ganado/Perdido/…) — replicando el vocabulario real usado hoy en Airtable (Requirement: mapeo sin pérdida, spec crm-twenty-adapter).
- [ ] 2.3 Verificar manualmente en la UI de Twenty que los campos custom aparecen en el formulario de Person y aceptan los tipos esperados.

## Fase 3: Puerto CRM y modelos de dominio (independiente de Fase 1/2, puede empezar en paralelo)

- [ ] 3.1 Crear `apps/api/services/crm/__init__.py` (paquete nuevo).
- [ ] 3.2 Crear `apps/api/services/crm/models.py`: dataclasses frozen `Lead`, `LeadRef`, `LeadPatch`; `Literal` para `sector`/`fuente`/`estado` con las opciones reales de Airtable (spec crm-port, Requirement: independencia de proveedor en la firma).
- [ ] 3.3 Crear `apps/api/services/crm/port.py`: `Protocol` async `CRMClient` con `create_lead`, `get_lead`, `update_lead`, `find_lead(*, email: str | None = None, cal_booking_id: str | None = None) -> LeadRef | None` (D1: clave de identidad = email + guardia por `calBookingId`).
- [ ] 3.4 Crear `apps/api/services/crm/errors.py`: jerarquía `CRMError` (+ subclases si aplica) con `status_code` y `detail` accesibles (spec crm-port, Requirement: manejo de errores uniforme).

## Fase 4: Adaptador Airtable (depende de Fase 3)

- [x] 4.1 Crear `apps/api/services/crm/airtable_adapter.py`: `AirtableCRMAdapter` que envuelve `AirtableMultiClient` (`services/airtable_multi.py`) SIN reescribirlo.
- [x] 4.2 Implementar `create_lead`/`get_lead`/`update_lead`/`find_lead` traduciendo `Lead`↔`fields` con el mismo mapeo que usa hoy `book_demo_and_create_lead` (`typecast=True`).
- [x] 4.3 Implementar el pre-check de idempotencia (D1) DENTRO de `create_lead`: invocar `find_lead(email=..., cal_booking_id=...)` antes de crear; si matchea, devolver el `LeadRef` existente en vez de crear un registro nuevo. Esto debe funcionar con el adaptador operando en solitario (post-cutover), no solo detrás de `DualWriteCRMClient`.
- [x] 4.4 Implementar `update_lead` con mapeo que OMITE del payload remoto cualquier campo `None`/ausente del `LeadPatch`, de forma que los campos no incluidos conserven su valor previo en Airtable.
- [x] 4.5 Capturar excepciones nativas de Airtable y re-lanzar como `CRMError`.

## Fase 5: Adaptador Twenty (depende de Fase 3; Fase 2 debe estar lista para pruebas reales, no para escribir el código)

- [x] 5.1 Crear `apps/api/services/crm/twenty_adapter.py`: `TwentyCRMAdapter` con auth por API key vía variable de entorno (`TWENTY_API_KEY`); fallo explícito al construirse si falta (spec crm-twenty-adapter, Requirement: autenticación configurable).
- [x] 5.2 Implementar `create_lead`/`get_lead`/`update_lead` vía REST (`/rest/people`) mapeando todos los campos de la tabla de Design §3 (nombre→`name.firstName/lastName`, email, teléfono, `companyName`, `sector`, `fuente`, `estadoDemo`, `fechaReunion`, `calBookingId`, `notas`), Person-only (sin crear Company/Opportunity).
- [x] 5.3 Implementar `find_lead(*, email=None, cal_booking_id=None)` vía GraphQL (filtro server-side por `emails` o por el custom field `calBookingId`).
- [x] 5.4 Implementar el pre-check de idempotencia (D1) DENTRO de `create_lead`: invocar `find_lead` (email y/o `calBookingId`) antes de crear un `Person` nuevo; si matchea, devolver el `LeadRef` existente. Debe funcionar con el adaptador operando en solitario (`CRM_BACKEND=twenty` puro o como `primary` del dual-write invertido post-cutover), no solo detrás de `DualWriteCRMClient`.
- [x] 5.5 Implementar `update_lead` con mapeo que OMITE del payload REST/GraphQL cualquier campo `None`/ausente del `LeadPatch`, de forma que los campos no incluidos conserven su valor previo en Twenty.
- [x] 5.6 Normalizar en este adaptador (y SOLO aquí) los valores rotos que manda hoy el workflow Meta: `Sector="Clínicas"` → `Salud`, `Estado="Nuevo"` → estado inicial válido del SELECT. NO tocar `airtable_adapter.py` ni `airtable_multi.py`.
- [x] 5.7 Capturar errores HTTP/GraphQL (auth, validación, rate limit, timeout) y re-lanzar como `CRMError` con status code y body original.

## Fase 6: Dual-write compuesto (depende de Fase 4 y 5)

- [x] 6.1 Crear `apps/api/services/crm/dual_write.py`: `DualWriteCRMClient(primary, secondary)`. Genérico en roles: sirve tanto para el dual-write del piloto (`primary=Airtable, secondary=Twenty`) como para el dual-write invertido post-cutover (`primary=Twenty, secondary=Airtable`, ver Fase 13).
- [x] 6.2 Implementar `create_lead`: escribe primero en `primary`; si falla, propaga el error tal cual (no llama a `secondary`). Si `primary` tiene éxito, intenta `secondary`. La idempotencia de cada escritura (pre-check `find_lead`) ya la resuelve internamente cada adaptador (Fase 4.3/5.4, D1) — `DualWriteCRMClient` NO reimplementa ese pre-check, solo orquesta el orden y la propagación de fallos.
- [x] 6.3 Si `secondary` falla, capturar y loguear (`logger.error` con `lead_id`/`booking_id`), NUNCA propagar ni bloquear la respuesta al caller. Devolver siempre el `LeadRef` de `primary`.
- [x] 6.4 Implementar `get_lead`/`update_lead`/`find_lead` delegando a `primary` (fuente de verdad activa, sea Airtable durante el piloto o Twenty durante la ventana de seguridad post-cutover).

## Fase 7: Wiring en config y routers (depende de Fase 4/5/6)

- [x] 7.1 Añadir `crm_backend: Literal["airtable","twenty","dual","dual_reversed"] = "airtable"` y `twenty_api_key`, `twenty_base_url` a `Settings` en `apps/api/config.py`. `dual` = piloto (Airtable=primary, Twenty=secondary); `dual_reversed` = ventana de seguridad post-cutover (Twenty=primary, Airtable=secondary, ver Fase 13).
- [x] 7.2 Añadir `get_crm() -> CRMClient` a `apps/api/deps.py` (patrón `@lru_cache` existente) que construye el adaptador según `crm_backend`, incluyendo `dual_reversed` con los roles de `DualWriteCRMClient` invertidos.
- [x] 7.3 Modificar `apps/api/routers/calls.py`: inyectar `crm: CRMClient = Depends(get_crm)` y cambiar `book_demo_and_create_lead` para usar `crm.create_lead(...)` en vez de `air.create_record(BASE_CRM, ...)`. El paso 3 (PATCH `malaga`) queda intacto en Airtable directo (fuera de scope).
- [~] 7.4 Verificación manual [Oscar]: con `CRM_BACKEND=airtable` (default), confirmar que `/calcom/book` sigue creando leads en Airtable exactamente igual que antes del refactor (regresión cero). Cubierto además por el test de contrato del adaptador Airtable (mismo mapeo + typecast + crm_url).

## Fase 8: pytest scaffolding + test de contrato (depende de Fase 4 y 5; puede correr en paralelo a Fase 6/7)

- [x] 8.1 Añadir `pytest`, `pytest-asyncio`, `respx` a `apps/api/requirements.txt`. (+ `pytest.ini` con `asyncio_mode=auto`, mirror de cold-outreach)
- [x] 8.2 Crear `apps/api/tests/__init__.py` y `apps/api/tests/conftest.py` (scaffolding mínimo: inserta `apps/api` en `sys.path` para imports planos).
- [x] 8.3 Crear `apps/api/tests/test_crm_contract.py`: test parametrizado que ejercita `AirtableCRMAdapter` (mock de Airtable API) y `TwentyCRMAdapter` (respx mock de Twenty API) contra las mismas aserciones, cubriendo:
  - `create_lead`/`get_lead`/`update_lead` devuelven `lead_id`/`crm_url` (spec crm-port, Requirement: contrato compartido entre adaptadores).
  - `find_lead` por email y por `cal_booking_id` devuelve el `LeadRef` esperado o `None` en ambos adaptadores.
  - Idempotencia: reintentar `create_lead` con el mismo email o el mismo `cal_booking_id` devuelve el lead ya existente y NO crea un segundo registro, en ambos adaptadores operando en solitario (sin `DualWriteCRMClient`).
  - Patch parcial: `update_lead` con un `LeadPatch` que solo trae un campo, seguido de `get_lead`, confirma que el resto de campos (`sector`, `notas`, `fecha_reunion`, etc.) conservan su valor previo, en ambos adaptadores.
  - (Extra) Normalización: Twenty normaliza `Sector="Clínicas"→Salud` y `Estado="Nuevo"→Reunión agendada`; Airtable NO normaliza (escribe tal cual).
- [x] 8.4 Ejecutar `pytest apps/api/tests/` y verificar verde antes de continuar a Fase 9. **18 passed** (Python 3.13, venv apps/api/.venv).

## Fase 9: Recableo del workflow n8n Meta (depende de Fase 7)

- [ ] 9.1 Decidir mecanismo: HTTP Request del workflow n8n a un endpoint FastAPI que use `crm.create_lead(...)` (recomendado, reutiliza el puerto) vs. nodo directo Twenty en n8n (descartado en este piloto — fuera de scope el nodo `n8n-nodes-twenty`).
- [ ] 9.2 Si se opta por endpoint FastAPI: crear/exponer ruta (p.ej. en `routers/calls.py` o nuevo router) que reciba el payload del form Meta y llame a `crm.create_lead(...)`.
- [ ] 9.3 Modificar `workflows/n8n-webinar-lead-automation-UPDATED.json`: apuntar el nodo que hoy escribe a Airtable directamente hacia el nuevo endpoint/puerto, aplicando la normalización de `Sector`/`Estado` corregida en el adaptador (Fase 5.4), no en n8n.
- [ ] 9.4 [Oscar] Probar el workflow con un envío de prueba del formulario Meta y confirmar creación del lead en ambos sistemas (dual-write activo).

## Fase 10: Scripts de paridad y backfill (depende de Fase 6, en paralelo a Fase 9)

- [ ] 10.1 Crear `infra/scripts/crm_parity_check.py`: recibe ventana de tiempo, lista leads Airtable, busca gemelo en Twenty por email/`calBookingId` vía `find_lead`.
- [ ] 10.2 Reportar `matched / missing_in_twenty / field_mismatch` por lead y campo, siguiendo el mapeo de la tabla Design §3. Comparar `fechaReunion` **por instante** (parsear ambos lados a `datetime` aware y comparar el timestamp), NUNCA por igualdad de string — ver política de TZ en Design §3 (Twenty almacena en UTC ISO-8601).
- [ ] 10.3 [Oscar] Ejecutar el script manualmente una vez tras las primeras cargas de dual-write para validar que el reporte es legible y correcto antes de dejarlo correr en ventana larga.
- [ ] 10.4 Crear `infra/scripts/crm_backfill.py`: lista los Leads/demos existentes en Airtable (base "Duendes CRM" `appFIn3ntFb39vGXF`, tabla `Leads`) y los crea en Twenty vía `TwentyCRMAdapter.create_lead` (idempotente por diseño gracias al pre-check de la Fase 5.4 — puede reejecutarse o solaparse con dual-write sin duplicar).

## Fase 11: Backfill + dual-write en producción — ventana de validación (depende de Fase 9 y 10; Oscar-manual, cronológica)

- [ ] 11.1 [Oscar+AIOS] Ejecutar `crm_backfill.py` (D2) para cargar en Twenty los Leads/demos ya existentes en Airtable, antes o al inicio de la ventana de dual-write, de forma que Twenty no arranque vacío.
- [ ] 11.2 [Oscar] Fijar `CRM_BACKEND=dual` en producción y redeploy.
- [ ] 11.3 [Oscar] Dejar correr dual-write ≥ 2 semanas / ≥ 20 leads reales.
- [ ] 11.4 [Oscar+AIOS] Ejecutar `crm_parity_check.py` al cierre de la ventana; evaluar contra el umbral: 100% presencia + ≥95% paridad de campos.
- [ ] 11.5 Si no se cumple el umbral: documentar causas (normalizaciones pendientes, bugs de mapeo) y decidir si se extiende la ventana o se corrige el adaptador antes de reintentar.

## Fase 12: PUERTA DURA — backup y restore (depende de Fase 1; puede prepararse en paralelo a Fase 11, pero debe completarse antes de Fase 13)

- [ ] 12.1 [Oscar] Provisionar el Hetzner Storage Box (o confirmar uno existente), configurar SSH key/subcuenta y verificar conectividad (`ssh -p23 <box> ls` y/o rsync de un fichero de prueba) ANTES de configurar la copia off-box.
- [ ] 12.2 Configurar cron diario de `pg_dump` del Postgres de Twenty → `/opt/twenty/backups/` con retención 7 días.
- [ ] 12.3 Configurar copia off-box del dump al Hetzner Storage Box (SSH/rsync o BorgBackup), usando la conectividad verificada en 12.1.
- [ ] 12.4 [Oscar] Ejecutar un restore de prueba: restaurar un dump en un contenedor Postgres efímero (separado de producción) y verificar (a) que las columnas/custom fields de `Person` existen (`sector`, `fuente`, `estadoDemo`, `fechaReunion`, `calBookingId`, `notas`, `companyName`), y (b) que 1-2 leads conocidos (por email o `calBookingId`) reaparecen con sector/fuente/estadoDemo/fechaReunion/notas iguales a los valores esperados. NO basta con `count(Person) > 0`. No hace falta `pg_dumpall` (Twenty single-tenant: los schemas conviven en la misma BD, `pg_dump` los incluye).
- [ ] 12.5 Documentar el resultado del restore probado (fecha, comando usado, columnas verificadas, leads y valores comprobados) como evidencia para la puerta dura de cutover.

## Fase 13: Cutover con ventana de seguridad invertida y verificación final (depende de Fase 11 con umbral cumplido Y Fase 12 completada — ambas condiciones obligatorias)

- [ ] 13.1 [Oscar] Confirmar que ambas puertas están satisfechas: paridad ≥95%/100% presencia (Fase 11) Y backup+restore verificado (Fase 12).
- [ ] 13.2 [Oscar] Cambiar `CRM_BACKEND=dual_reversed` en producción y redeploy (D3: cutover deja Twenty=primary, Airtable=secondary como espejo, NUNCA `twenty` puro de inmediato — sin tocar `routers/calls.py` ni el workflow n8n, solo config).
- [ ] 13.3 [Oscar] Verificar en producción que un lead nuevo (booking real o de prueba) se crea correctamente en Twenty (primary) y que también llega a Airtable (secondary, espejo).
- [ ] 13.4 [Oscar] Mantener la ventana de seguridad en `dual_reversed` hasta confiar plenamente en Twenty (sin incidencias observadas); solo entonces cambiar a `CRM_BACKEND=twenty` puro y apagar el espejo.
- [ ] 13.5 Documentar el plan de rollback probado, distinguiendo los dos escenarios: rollback PRE-cutover (`CRM_BACKEND=airtable`, trivial, Airtable nunca dejó de ser primary) vs. rollback POST-cutover durante la ventana de seguridad (reconfigurar `CRM_BACKEND=airtable` o `dual` con roles originales; no pierde datos porque `dual_reversed` mantuvo a Airtable como espejo completo). `docker compose down` en Twenty no rompe el flujo en ningún escenario.

---

## Orden crítico (dependencias fuertes)

```
Fase 0 (gate RAM)
  → Fase 1 (infra Twenty: DNS, red docker, compose, secretos, healthcheck+alerta)
      → Fase 2 (modelo Twenty)
      → Fase 12 (Storage Box, backups, restore endurecido — en paralelo desde que Twenty está arriba)
  Fase 3 (puerto, en paralelo desde el inicio)
      → Fase 4 (adaptador Airtable: incluye idempotencia + patch parcial)
      → Fase 5 (adaptador Twenty, necesita Fase 2 para pruebas reales: incluye find_lead, idempotencia, patch parcial, normalización)
          → Fase 6 (dual-write compuesto, genérico en roles)
              → Fase 7 (wiring routers: crm_backend soporta dual y dual_reversed)
                  → Fase 9 (workflow n8n)
              → Fase 8 (tests contrato: incluye find_lead/idempotencia/patch parcial, en paralelo a 7/9)
              → Fase 10 (scripts de paridad —por instante, TZ— y backfill)
                  → Fase 11 (backfill inicial + ventana dual-write 2+ semanas)
                      → Fase 13 (cutover a dual_reversed + ventana de seguridad → twenty puro) ← requiere también Fase 12 completada
```
