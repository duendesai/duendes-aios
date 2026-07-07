# Design: Migrar CRM operativo Airtable → Twenty (piloto Leads/demos)

## Technical Approach

Puerto hexagonal `CRMClient` en `apps/api/services/` con tres adaptadores intercambiables (Airtable, Twenty, DualWrite). Los consumidores (`routers/calls.py`, workflow n8n) escriben contra el puerto, no contra el proveedor. El toggle vive en config + `deps.py` (patrón `@lru_cache` ya existente). Airtable es fuente de verdad hasta que la paridad del dual-write pase el umbral; el cutover es un cambio de `CRM_BACKEND`. Cumple la regla de Oscar: 1 cambio → 1 test → 1 medición (paridad) → 1 decisión (cutover).

## 1. Puerto hexagonal y adaptadores

**Modelos de dominio** (`services/crm/models.py`, dataclasses frozen): `Lead(nombre, email, telefono, empresa, sector, fuente, estado, fecha_reunion, cal_booking_id, notas)` + `LeadRef(id, provider, url)`. Estado/Fuente/Sector como `Literal` reutilizando las opciones reales de Airtable (evita divergencia de vocabulario).

**Puerto** (`services/crm/port.py`, `Protocol` async):
```python
class CRMClient(Protocol):
    async def create_lead(self, lead: Lead) -> LeadRef: ...
    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef: ...
    async def get_lead(self, ref: LeadRef) -> Lead | None: ...
    async def find_lead(self, *, email: str | None = None, cal_booking_id: str | None = None) -> LeadRef | None: ...
```

**Decisión de idempotencia (D1, 2026-07-01):** la clave de identidad primaria es el **email** (una `Person` por humano). Además, `create_lead` aplica un **guardia por `calBookingId`**: si el email no matchea pero el `calBookingId` sí, se trata como el mismo lead (evita duplicar cuando Cal.com reenvía el webhook de una reserva ya procesada). `find_lead` acepta ambos criterios de forma independiente para soportar esto.

**Idempotencia vive en el adaptador, no solo en el compositor.** El pre-check de idempotencia (`find_lead` por email y/o `calBookingId` antes de crear) DEBE ejecutarse dentro del `create_lead` de **cada adaptador** (`AirtableCRMAdapter` y `TwentyCRMAdapter`), no únicamente en `DualWriteCRMClient`. Motivo: tras el cutover, `CRM_BACKEND=twenty` (o el dual-write invertido, ver §4) opera con `TwentyCRMAdapter` sin que `DualWriteCRMClient` intermedie con Airtable como primary — si la idempotencia solo viviera en el compositor, un reenvío del webhook de Cal.com duplicaría el lead en cuanto Twenty deje de ser el `secondary` protegido por el pre-check del compositor. Cada adaptador es responsable de su propia idempotencia de extremo a extremo.

**Adaptadores** (`services/crm/`): `AirtableCRMAdapter` **envuelve** `AirtableMultiClient` (sin reescribir): traduce `Lead`↔`fields` con el mismo mapeo que hoy usa `book_demo_and_create_lead`, `typecast=True`; su `create_lead` hace `find_lead` (email y/o `calBookingId`) antes de crear. `TwentyCRMAdapter` habla con la API de Twenty y aplica la misma disciplina de pre-check en su `create_lead`. `DualWriteCRMClient(primary, secondary)` compone ambos — en el sentido Airtable→Twenty durante el piloto, y en el sentido invertido (Twenty→Airtable) durante la ventana de seguridad post-cutover (ver §4).

**Wiring**: `Settings.crm_backend: Literal["airtable","twenty","dual"] = "airtable"` en `config.py`; `get_crm() -> CRMClient` en `deps.py` construye el adaptador según el toggle. `routers/calls.py` recibe `crm: CRMClient = Depends(get_crm)`; `book_demo_and_create_lead` pasa a usar `crm.create_lead(...)` en vez de `air.create_record(BASE_CRM,...)`. El paso 3 (PATCH `malaga`) sigue en Airtable directo (fuera de scope).

| Decisión | Alternativa | Trade-off |
|---|---|---|
| `Protocol` async, no ABC | ABC/herencia | Menos acoplamiento; DualWrite compone sin heredar |
| Envolver airtable_multi | reescribir | Cero riesgo sobre el flujo vivo del dialer |

## 2. Modelo en Twenty

Pipeline mínimo: reutilizar objeto estándar **Person** (contacto) + custom fields para el pipeline de demos. NO usar Companies/Opportunities en el piloto (over-engineering para un solo dominio; Person cubre Lead/demo). Objeto/campos custom en Person: `sector` (SELECT), `fuente` (SELECT), `estadoDemo` (SELECT), `fechaReunion` (DATE_TIME), `calBookingId` (TEXT), `notas` (TEXT). `name`, `emails`, `phones` son estándar.

| Operación | API | Justificación |
|---|---|---|
| create/update/get Lead | **REST** (`/rest/people`) | CRUD 1:1 simple, sin joins; menos superficie |
| find_lead por email y/o calBookingId (paridad + idempotencia) | **GraphQL** | filtro server-side por `emails` o por el custom field `calBookingId` en 1 request; REST filtering es limitado |

`find_lead` soporta buscar por email, por `calBookingId`, o ambos (ver D1 en §1): el `TwentyCRMAdapter.create_lead` lo invoca internamente antes de escribir para no duplicar en reintentos del webhook de Cal.com.

Mantener el acceso API limpio (token PAT, sin lógica de negocio en el adaptador) deja la puerta abierta al MCP `jezweb/twenty-mcp` sin refactor.

## 3. Mapeo Airtable `Leads` (appFIn3ntFb39vGXF / tblyTzWUXxpWeHJaB) → Twenty Person

| Airtable | Twenty Person | Nota |
|---|---|---|
| Nombre (primary) | `name.firstName/lastName` | split simple por primer espacio |
| Email | `emails.primaryEmail` | clave de idempotencia |
| Teléfono | `phones.primaryPhoneNumber` | |
| Empresa | `companyName` (custom TEXT) | no crear Company en piloto |
| Fuente (SELECT) | `fuente` (SELECT) | replicar opciones: Meta Ads/Web/Referido/Outreach/webinar… |
| Sector (SELECT) | `sector` (SELECT) | replicar: Clínica Dental/Fisioterapia/Bufete… |
| Estado (SELECT) | `estadoDemo` (SELECT) | Reunión agendada/Propuesta enviada/Ganado/Perdido… |
| Fecha reunión | `fechaReunion` (DATE_TIME) | |
| Cal Booking ID | `calBookingId` (TEXT) | dedup de bookings |
| Notas | `notas` (TEXT) | |
| **Convertido / Clients / Próximo seguimiento / Último contacto** | — | **sin destino limpio**: derivados o fuera del piloto; NO migrar |

**Flag**: el workflow Meta hoy escribe `Sector="Clínicas"` y `Estado="Nuevo"` — valores que NO existen en el SELECT (dependían de `typecast`). Al recablear, normalizar a opciones válidas (`Salud`, y un estado inicial real). Esta normalización ocurre SOLO en `TwentyCRMAdapter`, nunca en `AirtableCRMAdapter` (ver Open Questions).

**Política de zona horaria (`fechaReunion`):** `TwentyCRMAdapter` normaliza `fechaReunion` a **UTC ISO-8601 canónico** antes de escribir en el campo `DATE_TIME` de Twenty, con independencia de la zona horaria de origen (Cal.com/Airtable). Esto evita ambigüedad de TZ al comparar ambos lados. Ver §4 para cómo `crm_parity_check.py` compara estas fechas (por instante, no por string).

## 4. Backfill, dual-write, paridad y cutover

**Backfill inicial (D2, 2026-07-01):** antes de (o al inicio de) la ventana de dual-write (Fase 11), se ejecuta una **carga one-time** de los Leads/demos ya existentes en Airtable (base "Duendes CRM" `appFIn3ntFb39vGXF`, tabla `Leads`) a Twenty, vía el mismo `TwentyCRMAdapter.create_lead`. Es idempotente por construcción: como el pre-check de idempotencia vive en el adaptador (§1, D1), el backfill puede solaparse en el tiempo con leads nuevos que ya estén llegando por dual-write sin duplicarlos — `find_lead` (email/`calBookingId`) detecta el solape. Sin este backfill, Twenty arranca vacío y no es un CRM usable durante todo el piloto.

**Orden dual-write (piloto)**: Airtable primero (source of truth), luego Twenty. **Semántica de fallo**: fallo en Twenty se captura y loguea (`logger.error`), NUNCA propaga — el flujo de usuario no se rompe. `DualWriteCRMClient` devuelve el `LeadRef` de `primary`. La idempotencia de cada escritura la resuelve el adaptador de destino internamente (§1), no el compositor.

**Paridad** (script `infra/scripts/crm_parity_check.py`): lista Leads Airtable de la ventana, busca su gemelo en Twenty por email/`calBookingId`, compara campos mapeados. Reporta `matched / missing_in_twenty / field_mismatch`. Las comparaciones de fecha (`fechaReunion`) se hacen **por instante** (parsear ambos lados a `datetime` aware y comparar el timestamp resultante), nunca por igualdad de string — ver política de TZ en §3. **Umbral cutover**: ventana ≥ 2 semanas de dual-write y ≥ 20 leads con **100% presencia** y ≥ 95% paridad de campos (los mismatches restantes = normalizaciones conocidas de SELECT, documentadas).

**Cutover (D3, 2026-07-01) — dual-write invertido como ventana de seguridad**: el cutover NO deja `CRM_BACKEND=twenty` puro de inmediato. Deja `CRM_BACKEND=dual` con los roles **invertidos**: `primary=TwentyCRMAdapter`, `secondary=AirtableCRMAdapter`. Twenty pasa a ser la fuente de verdad operativa (lecturas/escrituras primarias), pero Airtable sigue recibiendo una copia de todo durante la ventana de seguridad — así un rollback posterior nunca pierde datos. Solo cuando Twenty es de plena confianza (tras la ventana de seguridad, sin incidencias) se apaga el espejo y se pasa a `CRM_BACKEND=twenty` puro.

**Rollback — dos escenarios distintos**:
- **PRE-cutover** (durante el piloto, Airtable=primary): rollback es reapuntar `CRM_BACKEND=airtable`; trivial y sin pérdida de datos porque Airtable nunca dejó de ser primary.
- **POST-cutover** (durante la ventana de seguridad, Twenty=primary/Airtable=secondary): rollback es reapuntar `CRM_BACKEND=airtable` (o `dual` con roles originales); tampoco pierde datos porque el dual-write invertido mantuvo a Airtable como espejo completo durante toda la ventana. Twenty se puede `docker compose down` sin afectar el flujo en cualquiera de los dos escenarios.

**PUERTA DURA — backups (antes del cutover):** `pg_dump` diario del Postgres de Twenty (cron en el VPS) a `/opt/twenty/backups/` con retención 7 días + copia off-box (Hetzner Storage Box, ver §5). **Restore probado y endurecido**: restaurar el dump en un contenedor Postgres efímero (separado de producción) y verificar (a) que las columnas/custom fields de Person existen tras el restore (`sector`, `fuente`, `estadoDemo`, `fechaReunion`, `calBookingId`, `notas`, `companyName`), y (b) que 1-2 leads conocidos (buscados por email o `calBookingId`) reaparecen con los valores esperados de sector/fuente/estadoDemo/fechaReunion/notas — no basta con `count(Person) > 0`. No hace falta `pg_dumpall`: en Twenty single-tenant los schemas conviven en la misma BD y `pg_dump` los incluye. El cutover NO se declara sin este restore verificado y documentado.

**Monitorización durante la ventana de dual-write:** healthcheck en el servicio `twenty-server` del compose + una alerta mínima y barata (cron en el VPS con `curl` a un endpoint de salud de Twenty, aviso por email/Telegram tras N fallos consecutivos) y al menos un chequeo de paridad intermedio a mitad de la ventana. Objetivo: no quemar en silencio las ≥2 semanas de la ventana si Twenty cae.

## 5. Infra (Hetzner)

**Primer paso innegociable**: `ssh root@46.225.161.222 free -h`. Si RAM libre < 8 GB → **redimensionar el VPS ANTES** de instalar nada (Twenty pide 8 GB).

**DNS**: `crm.duendes.net` es un registro nuevo. La zona de `duendes.net` ya existe (sirve `n8n`/`api` desde la misma IP del VPS), así que es añadir un registro A (y AAAA si hay IPv6) apuntando a la IP del Hetzner, y verificar propagación con `dig +short crm.duendes.net` antes de `docker compose up`. Es tarea manual de Oscar en el proveedor DNS, no algo que el AIOS pueda ejecutar.

Twenty en `/opt/twenty/` vía Docker Compose **con Postgres+Redis PROPIOS** (aislados de los de n8n — no compartir `POSTGRES_PASSWORD` ni instancia). Subdominio `crm.duendes.net` en Caddy (reverse proxy → puerto Twenty). Config anti-redirect-loop: `SERVER_URL=https://crm.duendes.net` y `FRONT_BASE_URL=https://crm.duendes.net` idénticos y con https.

**Modelo de red Docker**: red `twenty-network` propia para `twenty-server` + `twenty-worker` + Postgres + Redis de Twenty. Postgres y Redis de Twenty NO publican puertos al host (solo accesibles dentro de `twenty-network`) — evita colisión con los puertos de host ya usados por el Postgres/Redis de n8n. Caddy vive en la red de n8n, no en `twenty-network`, así que necesita alcanzar a `twenty-server`; dos opciones válidas (decidir al escribir el compose, documentar cuál se usó):
1. Unir **solo** `twenty-server` a la red de n8n como red externa (`docker network connect`), sin exponer Postgres/Redis de Twenty a esa red.
2. Publicar el puerto de `twenty-server` en loopback del host (`127.0.0.1:PUERTO:3000`) y que Caddy haga proxy a `127.0.0.1:PUERTO`.

Verificar explícitamente, antes de levantar el compose, que los puertos de host que vaya a usar el Postgres/Redis de n8n no colisionan con los que use (si alguno) el stack de Twenty.

**Secretos / `.env`**: Twenty lee su configuración de `/opt/twenty/.env` (no del `.env` de n8n). `sync-env.sh` debe parametrizar el destino del bloque de variables (hoy está hardcodeado a `/opt/n8n-recepcionista/.env`) para poder escribir también en `/opt/twenty/.env` las credenciales de Postgres/Redis de Twenty, `APP_SECRET` y `TWENTY_API_KEY`. Al `.env` de n8n (el que consume `teams-api`) solo se añaden `TWENTY_API_KEY` y `CRM_BACKEND` — es lo único que ese proceso necesita. Las credenciales llegan siempre por `env_file` en el compose, nunca inline en el YAML versionado; `/opt/twenty/.env` queda fuera de git, igual que el resto de `.env` de producción.

Reusar el patrón de `infra/hetzner/`: nuevo `infra/hetzner/twenty/docker-compose.yml` + entrada de env en `sync-env.sh`.

## Testing Strategy

| Layer | Qué | Cómo |
|---|---|---|
| Contrato (ligero) | Ambos adaptadores satisfacen `CRMClient`, incluyendo `find_lead`, idempotencia de `create_lead` y patch parcial de `update_lead` | pytest + respx, mock de Airtable y Twenty |
| Validación real | Paridad Airtable↔Twenty (incluyendo backfill inicial) | `crm_parity_check.py` sobre datos reales del dual-write |

No hay gate test-por-cambio (build nuevo, decisión Oscar 2026-07-01).

## Open Questions — RESUELTAS (2026-07-01)

- [x] **Normalización valores rotos Meta**: SOLO en el adaptador Twenty. Airtable se deja como está (piloto-safe, no se toca el flujo vivo). El arreglo de origen en Airtable queda como tarea aparte diferida.
- [x] **Backup off-box**: Hetzner Storage Box (SSH/rsync o BorgBackup, misma nube). Retención 7 días local + copia a Storage Box. Provisión/verificación de conectividad al Storage Box es tarea manual de Oscar (Fase 12), antes de configurar la copia off-box.
- [x] **RAM del VPS**: la mide Oscar y pasa el dato (`free -h`); el AIOS decide resize si <8 GB libres. Bloquea el arranque de infra.
- [x] **Twenty image tag**: pinnear la última estable ≥2.1.0 single-tenant (verificar tag exacto al arrancar infra, no usar `latest`).
- [x] **Idempotencia (D1)**: clave de identidad = email + guardia por `calBookingId`; pre-check vive en cada adaptador (`create_lead`), no solo en el compositor dual-write. Necesario para que la idempotencia sobreviva al cutover con `CRM_BACKEND=twenty`.
- [x] **Backfill (D2)**: carga one-time de Leads/demos existentes en Airtable a Twenty, vía `TwentyCRMAdapter`, idempotente, antes/al inicio de la ventana de dual-write (Fase 11).
- [x] **Rollback post-cutover (D3)**: el cutover deja `CRM_BACKEND=dual` invertido (Twenty=primary, Airtable=secondary) durante una ventana de seguridad, no `twenty` puro. El espejo se apaga cuando Twenty es de plena confianza.
