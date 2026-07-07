# Proposal: Migrar el CRM operativo de Airtable a Twenty (self-hosted) — piloto Leads/demos

## Intent

Airtable es hoy el CRM operativo de Duendes y está cableado en ~6 frentes (cliente central `airtable_multi.py`, power-dialer, sync Smartlead, cold-outreach, voice-agent, 3+ workflows n8n). Esto genera dependencia de un SaaS propietario, límites de API, coste por uso y datos fuera de nuestra infra. Queremos un CRM open-source, self-hosted, sobre PostgreSQL estándar, que además el AIOS pueda leer/escribir en lenguaje natural vía MCP. **Twenty** cumple. Migramos con riesgo mínimo: **primero un piloto** (pipeline Leads/demos), lo validamos, y solo después atacamos el bloque pesado.

## Scope

### In Scope (esta iteración)
- Puerto de dominio `CRMClient` (hexagonal) en `apps/api` + dos adaptadores: `AirtableCRMAdapter` (envuelve `airtable_multi.py`) y `TwentyCRMAdapter` (REST/GraphQL).
- Modelar el objeto Leads/demos en Twenty (Person + campos custom del pipeline de demos; sin Company/Opportunity en el piloto).
- Desplegar Twenty en el VPS Hetzner existente (Docker Compose, Postgres+Redis propios).
- Recablear a `CRMClient` la reserva Cal.com (`routers/calls.py` → `POST /calls/calcom/book`) y el workflow n8n del formulario Meta (`workflows/n8n-webinar-lead-automation-UPDATED.json`).
- **Backfill one-time** de los Leads/demos existentes en Airtable a Twenty (carga inicial idempotente vía `TwentyCRMAdapter`), para que el piloto arranque con un CRM usable en vez de vacío.
- **Dual-write** a Airtable durante validación, medir paridad, y cortar (cutover).
- Tras el cutover, ventana de seguridad con **dual-write invertido** (Twenty=primary, Airtable=secondary como espejo) hasta confiar plenamente en Twenty.
- Añadir pytest a `apps/api` como prerequisito (decisión explícita, ver Approach).

### Out of Scope (iteraciones SDD futuras)
- Prospects (`malaga`), tablas `Calls` y `Emails`, cold-outreach (CrewAI), voice-agent, cola del power-dialer.
- Twenty MCP server (`jezweb/twenty-mcp`) y nodo n8n `n8n-nodes-twenty` (beta): se evalúan tras el piloto.
- Decomisionar Airtable por completo.

## Capabilities

### New Capabilities
- `crm-port`: interfaz de dominio `CRMClient` (contrato CRUD sobre el vocabulario conceptual Lead/Person/Company/Opportunity, materializado en el piloto solo como Person) desacoplada del proveedor.
- `crm-twenty-adapter`: adaptador Twenty (REST/GraphQL) que satisface el puerto para el pipeline Leads/demos, Person-only.
- `crm-dual-write`: escritura simultánea Airtable+Twenty durante cutover (y su inversa post-cutover), con backfill inicial, medición de paridad y rollback.

### Modified Capabilities
- None (no hay specs previos en `openspec/specs/`; el comportamiento de `/calcom/book` y del workflow Meta se re-expresa contra el nuevo puerto, no cambia su contrato externo).

## Approach

**Arquitectura guía (norte):** hexagonal. Un puerto `CRMClient` con adaptadores intercambiables permite migrar dominio a dominio, con dual-write en cutover y rollback trivial (volver a apuntar al adaptador Airtable). Cada dominio migrado = **1 cambio → 1 test → 1 medición → 1 decisión** (regla inmutable de Oscar).

**Decisión — pytest ligero de contrato (no gate del build):** Oscar acotó (2026-07-01) que la regla "1 cambio, 1 test" aplica a corrección de bugs/tuning, NO a crear sistemas nuevos. Este piloto es un build, así que NO se gatea el desarrollo con un test por cambio. Se introduce pytest + respx en `apps/api` de forma **ligera y acotada**: un test de contrato que verifique que ambos adaptadores (`AirtableCRMAdapter` y `TwentyCRMAdapter`) satisfacen el mismo puerto `CRMClient` — barato y útil para cazar divergencia entre adaptadores. **La validación real del piloto es la medición de paridad del dual-write**, no los tests unitarios.

**Infra — reusar Hetzner con guardrail de RAM:** Twenty pide mín. 4 vCPU / 8 GB RAM. El VPS ya corre n8n + Postgres + Redis + FastAPI. **Primer paso de infra, innegociable: medir RAM libre real (`free -h`).** Si no entran los 8 GB, redimensionar el Hetzner ANTES de instalar nada.

## Affected Areas

| Área | Impacto | Descripción |
|------|--------|-------------|
| `apps/api/services/` | Nuevo | Puerto `CRMClient`, `AirtableCRMAdapter`, `TwentyCRMAdapter` |
| `apps/api/services/airtable_multi.py` | Modificado | Envuelto por el adaptador Airtable (sin reescribir) |
| `apps/api/routers/calls.py` | Modificado | `POST /calls/calcom/book` escribe vía `CRMClient` |
| `apps/api/` (tests) | Nuevo | pytest + respx para el contrato del puerto |
| `workflows/n8n-webinar-lead-automation-UPDATED.json` | Modificado | Formulario Meta escribe a Twenty vía `CRMClient` |
| Infra Hetzner | Nuevo | Twenty vía Docker Compose (Postgres+Redis propios) |

## Risks

| Riesgo | Prob. | Mitigación |
|--------|-------|------------|
| RAM insuficiente en Hetzner | Media | Guardrail `free -h` antes de instalar; redimensionar si no caben 8 GB |
| Twenty production-ready reciente (single-tenant desde v2.1.0, abr-2026) | Media | Piloto acotado; Airtable sigue vivo (dual-write); rollback por adaptador |
| Carga de mantenimiento self-host (backups, updates, monitorización) | Media | Empezar con un solo dominio; **backup automatizado + restore probado como PUERTA DURA antes del cutover** |
| Licencia AGPL-3.0 | Baja | Uso interno self-hosted; no redistribuimos el software → sin obligación de liberar |
| Deriva de paridad Airtable↔Twenty en dual-write | Media | Medición explícita de paridad como criterio de cutover |
| `apps/api` sin tests hoy | Baja | Es un build nuevo (regla 1-test no aplica); test de contrato ligero + la paridad del dual-write como validación real |
| Twenty caído en silencio durante la ventana de dual-write (≥2 semanas) | Media | Healthcheck en el compose + alerta mínima (cron con curl a endpoint de salud, aviso por email/Telegram) |

## Rollback Plan

Rollback por diseño, en dos escenarios:
- **PRE-cutover**: mientras dure el dual-write (Airtable=primary, Twenty=secondary), Airtable conserva todos los datos. Si Twenty falla, se reapunta `CRMClient` a `AirtableCRMAdapter` (cambio de config, sin tocar routers ni workflows). Twenty se puede apagar (`docker compose down`) sin afectar el flujo.
- **POST-cutover**: durante la ventana de seguridad, el cutover deja `CRM_BACKEND` en dual-write invertido (Twenty=primary, Airtable=secondary como espejo), no en `twenty` puro. Así un rollback tras el cutover nunca pierde datos: Airtable sigue recibiendo copia. El espejo se apaga solo cuando Twenty es de plena confianza.

El cutover solo se declara tras medición de paridad OK y backfill completado.

## Dependencies

- VPS Hetzner con Docker; Postgres y Redis dedicados para Twenty (no reutilizar los de n8n).
- Credenciales/API key de Twenty; acceso a Cal.com y al workflow n8n del formulario Meta.
- pytest + respx en `apps/api` (se introduce en esta iteración).

## Success Criteria

- [ ] `free -h` verificado en Hetzner; RAM suficiente confirmada o VPS redimensionado antes de instalar.
- [ ] Twenty desplegado y accesible; objeto Person modelado con sus campos custom (sin Company/Opportunity).
- [ ] Puerto `CRMClient` + ambos adaptadores implementados; test de contrato ligero (paridad de contrato entre adaptadores, incluyendo `find_lead` e idempotencia) en verde.
- [ ] Backfill one-time de los Leads/demos existentes en Airtable cargado en Twenty de forma idempotente.
- [ ] `/calcom/book` y el workflow Meta escriben en Twenty vía `CRMClient`.
- [ ] Dual-write activo; paridad Airtable↔Twenty medida y validada (validación real del piloto).
- [ ] **PUERTA DURA:** backup automatizado del Postgres de Twenty configurado Y restore probado con éxito (columnas/custom fields + valores de leads conocidos) ANTES del cutover.
- [ ] Cutover del pipeline Leads/demos a Twenty, con ventana de seguridad en dual-write invertido (Twenty=primary, Airtable=secondary) y rollback documentado y probado.
