# Playbook — Lanzar una campaña nueva en teams.duendes.net

> **Para Oscar**: lee la sección "La cocina y los menús" primero.
> **Para Claude en sesión futura**: si Oscar te pide "lanzar una nueva campaña" / "cambiar de ciudad" / "cambiar de sector", lee este documento entero antes de proponer nada. Aquí está el patrón completo, paths, IDs y decisiones ya tomadas.

---

## La cocina y los menús (resumen para Oscar)

Imagina que tienes una **cocina industrial** montada. La cocina la levantamos en mayo 2026: fogones (el dialer en `teams.duendes.net`), horno (Smartlead), nevera (Airtable), grifería (Zadarma), salida de humos (n8n)... todo conectado y funcionando.

**Cada campaña nueva es un menú diferente** en esa misma cocina.

| Ejemplo | Compras carne nueva | Cambias receta | Cambias la cocina |
|---------|---|---|---|
| Misma campaña, otra oferta | NO | SÍ (nuevo copy email) | NO |
| Misma ciudad, otro sector | SÍ | SÍ | NO |
| Otra ciudad, mismo sector | SÍ | medio (adaptar copy) | NO |
| Vertical totalmente nueva (hoteles) | SÍ | SÍ | medio (nueva tabla Airtable) |

**Lo importante**: NO se vuelve a montar la cocina. Cada campaña reutiliza toda la infra que ya existe.

---

## Stack montado (qué reutiliza cada campaña)

| Pieza | Dónde vive | Qué hace |
|---|---|---|
| Dialer | https://teams.duendes.net | Donde haces las llamadas |
| Backend API | https://api.duendes.net (VPS Hetzner) | Lógica de queue, llamadas Zadarma, booking Cal.com |
| Airtable | base `app5WbiXR0qXGTc3r` ("LUCIA Bienestar") | Source of truth: tabla `malaga` (prospects) + `Calls` (log) + `Emails` (cold email tracking) |
| CRM | base `appFIn3ntFb39vGXF` ("Duendes CRM") tabla `Leads` | Aquí aterrizan las demos agendadas |
| Zadarma | número `+34936942094` | Click-to-call desde el dialer |
| Cal.com | event `4879655` (cal.com/duendes/consulta, 30 min) | Booking de demos |
| Smartlead | campaña actual: `3368353` ("Fisios Malaga May 26") | Envío cold email |
| n8n workflows | https://n8n.duendes.net | (1) Webhook Smartlead→Airtable. (2) Cron horario sync. |
| Auth | Supabase project `qbbmwonhzprizrrsodcy` | Login con password + magic link |
| Deploy frontend | Vercel `duendes-teams` | CI/CD desde GitHub `duendesai/duendes-aios` |
| Deploy backend | Docker compose en `/opt/n8n-recepcionista/` del VPS | Junto a n8n |

---

# Escenarios

## Escenario A — Solo cambia el copy del email (misma campaña, nueva propuesta)

**Ejemplo**: "Fisios Malaga, oferta junio"

### Lo que hace Oscar
1. Editar la secuencia en Smartlead (mismo campaign_id) → escribir nuevo email
2. Activar
3. **Nada más**

### Lo que hace Claude en sesión nueva
Nada. La infra ya está apuntando a esa campaña.

### Tiempo total: 0 min de Claude.

---

## Escenario B — Nueva ciudad, mismo sector (Fisios Valencia)

**Lo que hace Oscar**:

1. **Scrapeo nuevos leads** con Apify ("fisioterapia valencia") → CSV
2. **Importa CSV a la tabla `malaga`** (la tabla soporta multi-ciudad — el campo `city` ya es singleSelect)
3. **Enriquecimiento web** (mismo pipeline de scraping que ya tienes)
4. **Genera CSV optimizado para Smartlead** con los emails
5. **Crea nueva campaña Smartlead** "Fisios Valencia June" → sube CSV
6. **Pega webhook URL** (siempre es `https://n8n.duendes.net/webhook/smartlead-emails`) en la nueva campaña
7. **Marca los 5 eventos** (EMAIL_SENT, EMAIL_OPEN, EMAIL_LINK_CLICK, EMAIL_REPLY, LEAD_UNSUBSCRIBED)
8. **Le dice a Claude**: "Añade la campaña Smartlead `XXX` (Fisios Valencia June) al cron sync"

**Lo que hace Claude** (5 min):

1. Edita `apps/api/services/smartlead_sync.py` → cambiar `DEFAULT_CAMPAIGN_ID` por una lista de IDs activos, o añadir parámetro `campaign_ids: list[int]`
2. Actualiza el workflow n8n "Cron Smartlead Sync (hourly)" id `WQuerqpUAYRgUYOL` para iterar sobre múltiples campaign_ids
3. Verifica con un sync manual:
   ```bash
   curl -X POST "https://api.duendes.net/api/admin/sync-smartlead?campaign_id=NUEVO_ID" \
     -H "X-Admin-Token: $ADMIN_TOKEN"
   ```
4. (Opcional, recomendado) Añade un **dropdown en el sidebar** `/sdr` que filtra por `city` + `categoryName` para que Oscar elija "Estoy llamando hoy a Fisios Valencia" — esto requiere editar:
   - Backend: `apps/api/routers/calls.py` endpoint `GET /calls/queue` añadir `?city=Valencia&category=Fisioterapeuta`
   - Frontend: `apps/teams/src/components/sdr/CallQueue.tsx` añadir Selector arriba

**Tiempo total Claude**: 5 min (sin dropdown) o 1 hora (con dropdown).

---

## Escenario C — Otro sector (Dentistas Málaga)

Igual que el Escenario B + **adaptar dos cosas más**:

**Lo que hace Oscar**:
- Pasos 1-7 del escenario B (con scraping de "clínicas dentales málaga")
- Mandar el copy del nuevo email a Claude o escribirlo él mismo

**Lo que hace Claude adicional** (~30 min):

1. **Script SDR** en `apps/teams/src/lib/sdr/scripts.ts` → adaptar las objeciones específicas del sector dentista (no "fisio invasiva" sino "pacientes que llaman para urgencias dentales")
2. **Categorías** en Airtable: añadir "Dentista" a `categoryName` si no existe
3. **Mapeo de scoring** en el enriquecimiento (si Oscar quiere): adaptar las señales (cantidad de sillones, ortodoncia, urgencias 24h)
4. Lo demás igual que B

**Tiempo total Claude**: ~30 min.

---

## Escenario D — Vertical totalmente nueva (Hoteles, abogados)

Solo cuando el ICP es radicalmente distinto y los campos del prospect no encajan en `malaga`.

**Lo que hace Oscar**:
- Decide los campos clave del nuevo vertical (en hoteles: `stars`, `rooms`, `chain`, `tipo`)
- Scraping nuevo
- Decide si reutiliza el mismo número Zadarma o uno nuevo

**Lo que hace Claude** (~2-3 horas):

1. Crear **nueva tabla en Airtable** (`hoteles`, `abogados`, etc.) con los campos del nuevo vertical
2. Backend: parametrizar el `source` del queue. `GET /calls/queue?source=hoteles` apunta a la nueva tabla. Constantes nuevas en `apps/api/services/airtable_multi.py`:
   ```python
   TABLE_HOTELES = "tblXXXXXXXXXXXXXX"
   ```
3. Frontend: el dropdown del sidebar añade "Hoteles" como source más
4. Script SDR adaptado al nuevo dolor
5. Smartlead campaign nueva, webhook como siempre

**Tiempo total Claude**: 2-3 horas la primera vez. Las siguientes verticales del mismo tipo serán más rápidas.

---

# Cómo arrancar una sesión nueva con Claude

Cuando llegue el momento, abre Claude Code en el proyecto y dile algo como:

> "Quiero lanzar una campaña nueva para [ciudad/sector]. Lee el playbook en `infra/PLAYBOOK-NUEVA-CAMPANA.md` y dime qué necesitas de mí."

Yo (Claude) automáticamente:
1. Buscaré en Engram referencias a "campaña nueva" o "playbook"
2. Encontraré la nota que apunta a este documento
3. Lo leeré entero
4. Te diré exactamente qué necesito de ti y empezaré

---

# Referencias técnicas (para Claude, no para Oscar)

## Endpoints del backend
- `GET /api/calls/queue` — cola del dialer, filtros: `max_records`, eventualmente `?city`, `?category`, `?source`
- `GET /api/calls/agenda` — callbacks programados
- `POST /api/calls/result` — guarda resultado de llamada
- `POST /api/calls/calcom/book` — agenda demo
- `POST /api/calls/zadarma/dial` — click-to-call
- `POST /api/admin/sync-smartlead?campaign_id=X` — sync manual (requiere header `X-Admin-Token`)

## IDs de Airtable
```
BASE_LUCIA  = app5WbiXR0qXGTc3r
  TABLE_MALAGA = tblCyn7fjgBJM8rkF
  TABLE_CALLS  = tblZTdqQlnRg6KF7Z
  TABLE_EMAILS = tblsOIzcXlleNjAat

BASE_CRM = appFIn3ntFb39vGXF
  TABLE_LEADS = tblyTzWUXxpWeHJaB
```

## Workflows n8n
- `XatANUKmhi78XJYC` — Smartlead → Airtable Emails (webhook tiempo real)
- `WQuerqpUAYRgUYOL` — Cron Smartlead Sync (cada 1h)

## Scripts útiles
- `infra/scripts/sync_smartlead.py` — sync manual desde el Mac
- `infra/hetzner/deploy.sh` — deploy backend al VPS
- `infra/hetzner/sync-env.sh` — sincroniza vars del .env local al VPS

## Variables de entorno (todas en `.env` raíz)
```
AIRTABLE_API_KEY
SMARTLEAD_API_KEY
CALCOM_API_KEY (event 4879655)
ZADARMA_API_KEY, ZADARMA_API_SECRET, ZADARMA_SIP_USERNAME
SUPABASE_URL, SUPABASE_ANON_KEY
ADMIN_TOKEN (para endpoints /api/admin/*)
POSTGRES_PASSWORD (de n8n)
```

## Campaigns Smartlead activas
- `3368353` → Fisios Malaga May 26 (109 leads, ~20 enviados)
- *(añadir aquí cada nueva campaña)*

## Decisiones de diseño tomadas (no re-discutir sin razón)
- **Auth**: password + magic link fallback. Passkey aplazado.
- **Click-to-call**: API REST de Zadarma (NO `tel:`). Firmas HMAC normalizadas sin `+`.
- **Estado dual**: en Airtable `malaga.Estado` = "Demo agendada", en `Calls.Disposition` = "Agendada" (mapping en `DISPOSITION_TO_ESTADO`).
- **Backend deploy**: Hetzner (no Vercel Python) por cold starts.
- **Tema visual**: brand-cream + Zilla Slab + brand-purple/yellow (alineado con duendes.net).
