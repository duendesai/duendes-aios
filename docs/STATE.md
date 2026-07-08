# STATE — Memoria viva del AIOS de Duendes

> Lee esto PRIMERO al arrancar. Fuente de verdad de QUÉ se usa hoy.
> Cuando algo cambie de estado, EDITA o BORRA aquí (narrow, disposable). No acumules eventos.
> Última actualización: 2026-07-08.

## Cómo se trabaja hoy

- **El sistema de trabajo es Claude Code + ECC** (en el Mac, sobre la suscripción Max), operando en el repo `duendes-aios`. Aquí viven los "departamentos" (agentes de ECC: marketing, planner, reviewers, etc.). Es REACTIVO: trabaja cuando Oscar está.
- **Trasno (Hermes) DESCARTADO (2026-07-06).** Se montó en un VPS Netcup (siempre encendido, dashboard web/iPhone, delegaba a Claude Code). Conclusión de Oscar, con razón: no aportaba valor diferencial, era Claude Code con app y cerebro más flojo. Lo que Oscar quiere de verdad es que la empresa avance en su ausencia (autonomía real), y eso no se construyó. Se desinstala Hermes del servidor y el box se reutiliza para Twenty CRM.
- **Obsidian**: solo un VISOR opcional de los markdown del repo (grafo + backlinks). NO es un sistema de trabajo ni una memoria aparte.
- **Memoria**: este `docs/STATE.md` + `context/`. Engram retirado.
- **Canales**: Slack y Telegram FUERA.

## Foco actual: Twenty CRM — migración del dialer (2026-07-08)

- Twenty **DESPLEGADO y VIVO** en `crm.duendes.net` (VPS Netcup, 159.195.195.215). Material en `infra/twenty/` + adaptadores en `apps/api/services/crm/`. Dual-write de Leads/demos ACTIVO (`CRM_BACKEND=dual`, alcanzable solo desde Hetzner por firewall).
- **Incidente 2026-07-08:** el plan Free de Airtable topa a 1.000 registros/base; la base LUCIA (fisios) se pasó por 160 abogados metidos por error → bloqueó el teléfono saliente del comercial. Oscar separó los abogados a una base nueva (`Abogados`, 164) y, en pánico, borró Calls (511) + Emails (200) para bajar del tope (no recuperables). Teléfono desbloqueado. Decisión de Oscar: **jubilar Airtable, todo a Twenty**, empezando por el dialer.
- **Migración del dialer (hoy, HECHA en código, SIN desplegar):** objeto `prospecto` en Twenty + 175 fisios migrados + recableo de teams-api tras flag `DIALER_BACKEND` (aditivo, cero regresión). Detalle y runbook de cutover en `docs/MIGRACION-TWENTY.md`. **Cutover pendiente: esta tarde con Oscar** (comercial parado). Rollback = `DIALER_BACKEND=airtable`.
- Airtable sigue VIVO como fuente hasta el cutover; después queda de reserva unos días. Los 164 abogados y las otras bases (OUTREACH, CRM Clients/Invoices/Deals) migran en sesiones siguientes.

## Estado por área (resto)

### 🟢 VIVO
- `turecepcionista/platform/` + `web/` — producto estrella (voz, ElevenLabs+Zadarma+n8n+Airtable). Demo: +34 936 942 343.
- `apps/teams/` (dialer SDR, teams.duendes.net), `apps/web/` (dashboard), `apps/api/` (FastAPI en Hetzner).
- `infra/hetzner/`, `infra/scripts/`. `cold-outreach/` (CrewAI, gitignored, 1 campaña real despachos Madrid).
- `scripts/` vivos: `airtable_client`/`airtable_sync`/`aios_monitor` (launchd) + tools de datos por depto + `notion_writer`, `langfuse_init`.
- `context/` (dominio de negocio, vigente). ECC v2.0.0 en `.claude/`.
- n8n: workflows LUC.IA de voz activos.

### 🔴 MUERTO / LEGACY
- **Trasno/Hermes**: descartado, en desinstalación del VPS.
- Slack y Telegram: todo fuera. Pendiente: baja launchd `com.duendes.aios.slack`, borrar `scripts/slack_*.py` + `bot.py`, apagar workflow n8n `Duendes CRM Bot` (manual).
- Basura a borrar (Frente A): `n8n-mcp/` raíz (3.1 GB dup, el activo es `tools/n8n-mcp/`), `tools/n8n-workflows/` (81 MB), `gentle-ai/` (6 MB ajeno), `data/` (slack_history + specs marzo).
- `voice-agent/`: legacy, se mantiene como ESPEJO (contiene el agente Lucía). No borrar.

## Próximos pasos (por prioridad)
1. **Cutover del dialer a Twenty** (esta tarde, con Oscar, comercial parado): seguir el runbook de `docs/MIGRACION-TWENTY.md` (deploy teams-api → `DIALER_BACKEND=twenty` → verificar `/api/calls/queue` + llamada de prueba). Rollback = quitar el flag.
2. **Migrar los 164 abogados** a `prospecto` (necesita PAT de Airtable con acceso a la base `Abogados`, que `pat58` no ve): `infra/twenty/migrate_prospectos.py --base appqDawY24kiaPWFu --table <tbl>`.
3. Migrar el resto de bases a Twenty (OUTREACH 428 leads, CRM Clients/Projects/Invoices/Deals) y recablear sus orígenes (cold-outreach, tools ElevenLabs de LUC.IA, scripts AIOS, n8n). Rotar los PAT al terminar.
4. Terminar de desinstalar Trasno del VPS; Frente A de limpieza del monorepo (pendientes previos).

## Log de sesiones
- 2026-07-02: Desconectado Telegram. Auditoría del monorepo (7 áreas). Instalado ECC en la raíz. Creado STATE.md.
- 2026-07-03: Desplegado Trasno (Hermes) en VPS Netcup: Ubuntu 24.04, blindaje SSH+firewall+fail2ban, dashboard HTTPS + Nous OAuth en `trasno.duendes.net`, delegación a Claude Code/Max probada (respondió Opus 4.8). Entregado manual de Trasno.
- 2026-07-06 (lunes): Oscar concluye que Trasno no aporta valor diferencial (Claude Code con pasos de más) y decide DESCARTARLO, reutilizando el VPS para Twenty CRM. Aprendizaje clave: no montar infraestructura antes de validar el valor (ver memoria feedback). Sesión cerrada para empezar una limpia enfocada en Twenty. Pendiente confirmar si el VPS de Twenty (crm.duendes.net) es el mismo de Trasno.
- 2026-07-08 (martes): incidente Airtable (tope 1.000 registros bloqueó el teléfono del comercial por 160 abogados mal metidos en la base de fisios). Desbloqueado. Decisión: jubilar Airtable → Twenty, empezando por el dialer. HECHO en código (sin desplegar): objeto `prospecto` en Twenty, 175 fisios migrados, recableo teams-api tras flag `DIALER_BACKEND`, 43 tests verdes. Cutover pendiente para la tarde con Oscar. Ver `docs/MIGRACION-TWENTY.md`.
