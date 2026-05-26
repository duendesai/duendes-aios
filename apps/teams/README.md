# teams.duendes.net — espacio de operaciones interno

Webapp Next.js que vive en `apps/teams/` y sirve como dashboard de operaciones de Oscar para dirigir Duendes.

**Feature v1**: `/sdr` — power dialer para hacer llamadas en frío (sustituye al agente IA Lucía mientras el modelo siga siendo detectado como robot).

**Features futuras**: CRM de clientes Duendes, gestión de campañas, lo que venga.

## Stack

- Next.js 15.2.4 (App Router) + React 19 + TypeScript
- Tailwind 3.4 + Radix UI + Zustand 5
- Supabase SSR para auth (magic link)
- Backend: `apps/api/` (FastAPI) — router `/calls`
- Telefonía: extensión Chrome **Zadarma Click to Call** (intercepta `tel:` URIs)
- Booking: Cal.com v2 (event `5693752` · 30min · `cal.com/duendes/demo`)
- Datos: Airtable directo (sin n8n)
  - `app5WbiXR0qXGTc3r` (LUCIA Bienestar) → `malaga` (cola) + `Calls` (log)
  - `appFIn3ntFb39vGXF` (Duendes CRM) → `Leads` (cuando se agenda demo)

## Arrancar en local

```bash
# Desde la raíz del monorepo
pnpm install --filter teams        # ya hecho
pnpm --filter teams dev            # arranca en localhost:3001
# (en otra terminal) — arrancar backend
pnpm api                           # uvicorn en localhost:8000
```

Variables de entorno en `apps/teams/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=...        # mismo que apps/web
NEXT_PUBLIC_SUPABASE_ANON_KEY=...   # mismo que apps/web
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Variables del backend (en `.env` raíz — ya configuradas):

```
AIRTABLE_API_KEY=...
CALCOM_API_KEY=cal_live_b5477a8c642374d0b66f621857f2624d
CALCOM_EVENT_TYPE_ID=5693752
```

## Setup de la extensión Chrome Zadarma

Una sola vez:

1. Instala la extensión "Click to call Zadarma" desde el Chrome Web Store (si no la tienes).
2. Abre la extensión → **Extensión de la centralita** = tu extensión SIP (la que termine en tu número outbound).
3. **Clave de integración** → haz clic en "Generar" y pégala.
4. **Entrar**.

A partir de ese momento, cualquier número con formato `tel:+34XXXXXXXXX` que se abra en una pestaña de Chrome dispara la llamada vía Zadarma — sin marcar nada manualmente.

## Flujo de uso `/sdr`

```
1. Abres /sdr → cola izquierda con todos los prospectos pendientes (no llamar=false,
   estado no final, próximo intento <= hoy)
2. Se autoselecciona el primero. Ves su ficha + datos enriquecidos (scraping previo)
3. Pulsas "Llamar" (o tecla C) → la extensión Zadarma marca el número
4. Cuando cuelgas, pulsas "Terminar" (o H/Esc) → aparece el formulario
5. Rellenas disposition + contacto + buying signal + notas → submit (o S)
6. Si disposition = Agendada → aparece el panel de Cal.com → eliges hueco → confirma
   → se crea booking + lead en CRM + actualiza malaga
7. Avanza al siguiente prospecto. Repite.
```

### Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `C` | Iniciar llamada |
| `H` / `Esc` | Terminar llamada (mostrar formulario) |
| `1`-`9` | Seleccionar disposition por número (en wrap-up) |
| `S` | Guardar formulario |
| `N` | Siguiente prospecto |
| `?` | Mostrar ayuda de atajos |

## Esquema de datos

**`app5WbiXR0qXGTc3r/malaga`** (prospectos):

| Campo | Tipo | Notas |
|-------|------|-------|
| `title` | text | Nombre del negocio (primary) |
| `phone` | phone | Número a llamar |
| `city` / `categoryName` / `website` | text/url | Info básica |
| `Estado` | singleSelect | Disposition del prospect en pipeline |
| `Lane` | singleSelect | Pendiente / En curso / Programado / Cerrado |
| `Intentos` | number | Auto-incrementa en cada submit |
| `Último intento` / `Próximo intento` | dateTime | Para callbacks |
| `Notas` | longtext | Append en cada llamada (no reemplaza) |
| `Datos enriquecidos` | longtext (JSON) | Scraping previo — se muestra en CallPanel |
| `Contacto alcanzado` / `Motivo pérdida` | singleSelect | Rellenados desde el form |
| `No llamar` | checkbox | Auto = true si disposition = "No llamar" |
| `Agendada fecha` / `CRM Duendes URL` | dateTime/url | Auto al agendar demo |
| `outcome` | singleSelect | Canonical (demo_agendada / no_interesa / callback / ...) |

**`app5WbiXR0qXGTc3r/Calls`** (log):

| Campo | Tipo | Notas |
|-------|------|-------|
| `Call ID` | text | `M-{uuid8}` |
| `Prospect` | linked | Link a malaga |
| `Fecha y hora` | dateTime | now |
| `Duracion (seg)` | number | Timer del frontend |
| `Disposition` / `Buying signal` / `Motivo fin` | singleSelect | |
| `Objeciones` | multipleSelects | Array de strings |
| `Discovery completo` | checkbox | |
| `Notas` / `Transcripcion` | longtext | |
| `outcome` | singleSelect | Mismo enum que malaga.outcome |

**`appFIn3ntFb39vGXF/Leads`** (CRM, cuando se agenda):

| Campo | Tipo | Notas |
|-------|------|-------|
| `Nombre` / `Email` / `Empresa` / `Teléfono` / `Sector` | varios | Del formulario de booking |
| `Fuente` | singleSelect | `"SDR Manual"` |
| `Estado` | singleSelect | `"Demo agendada"` |
| `Fecha reunión` | dateTime | `slot_start` |
| `Cal Booking ID` | text | `uid` del booking |

## Estructura del proyecto

```
apps/teams/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root + Toaster dark
│   │   ├── globals.css             # Tema dark (HSL)
│   │   ├── page.tsx                # redirige a /sdr
│   │   ├── login/page.tsx          # Magic link Supabase
│   │   ├── auth/
│   │   │   ├── callback/route.ts   # exchangeCodeForSession
│   │   │   └── confirm/route.ts    # verifyOtp (link tradicional)
│   │   └── (workspace)/
│   │       ├── layout.tsx          # Auth guard + Sidebar
│   │       └── sdr/page.tsx        # Power dialer (orquesta componentes + shortcuts)
│   ├── components/
│   │   ├── ui/                     # button, card, badge, input, dialog, ...
│   │   ├── layout/sidebar.tsx
│   │   └── sdr/
│   │       ├── CallQueue.tsx       # Lista lateral
│   │       ├── CallPanel.tsx       # Ficha + botón Llamar + historial
│   │       ├── CallForm.tsx        # Formulario post-llamada
│   │       ├── BookingPanel.tsx    # Slots Cal.com inline
│   │       ├── ScriptReference.tsx # Script SDR colapsable
│   │       ├── SessionHeader.tsx   # Contadores en vivo
│   │       └── ShortcutsHelp.tsx   # Dialog con atajos
│   ├── lib/
│   │   ├── utils.ts                # cn() + normalizePhoneEs()
│   │   ├── supabase/{client,server,middleware}.ts
│   │   └── sdr/
│   │       ├── types.ts            # Tipos compartidos con apps/api
│   │       ├── enums.ts            # Valores reales de Airtable
│   │       ├── scripts.ts          # Script SDR hardcoded
│   │       ├── api.ts              # Cliente HTTP (5 endpoints)
│   │       └── useKeyboardShortcuts.ts
│   ├── store/
│   │   └── useCallSessionStore.ts  # Zustand: cola + call lifecycle + stats
│   └── middleware.ts               # Auth refresh + protección de rutas
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.ts
└── .env.local.example
```

## Backend (`apps/api/`)

Endpoints registrados en `routers/calls.py` bajo prefijo `/api/calls`:

| Método | Path | Hace |
|--------|------|------|
| GET | `/queue` | Cola de prospectos (filtros + sort canónico) |
| GET | `/prospect/{id}` | Detalle + últimas 3 llamadas |
| POST | `/result` | Log en Calls + PATCH en malaga (Intentos++, Estado, append Notas) |
| GET | `/calcom/slots?days=N` | Slots disponibles del event 5693752 |
| POST | `/calcom/book` | Booking Cal.com + lead CRM + actualiza malaga |

CORS añade `http://localhost:3001` y `https://teams.duendes.net`.

## Deploy a producción (cuando estés listo)

1. Crear proyecto en Vercel apuntando a `apps/teams`:
   - Root Directory: `apps/teams`
   - Install: `cd ../.. && pnpm install --frozen-lockfile`
   - Build: `cd ../.. && pnpm --filter teams build`
   - Variables: las 3 del `.env.local` (apuntando al backend de producción)
2. Vercel → Settings → Domains → `teams.duendes.net`
3. Namecheap → CNAME `teams` → `cname.vercel-dns.com`
4. Supabase → Authentication → URL Configuration:
   - Site URL: `https://teams.duendes.net`
   - Redirect URLs: `https://teams.duendes.net/auth/callback`, `https://teams.duendes.net/auth/confirm`
5. Backend (`apps/api/`): desplegar donde corresponda (Railway / Fly / Vercel Python). Hoy es solo local — cuando esté en producción, actualiza `NEXT_PUBLIC_API_URL` en Vercel.

## Cosas que NO incluye (por diseño)

- Multi-tenant / SaaS vendible
- Tests automatizados (single-user, valida manualmente)
- Cliente REST de Zadarma (todo va por `tel:` + extensión)
- Detección automática de fin de llamada (manual con botón / `H`)
- Edición de prospectos (lo hace `cold-outreach/`)
- Realtime / websockets (refresh con botón en la cola)
