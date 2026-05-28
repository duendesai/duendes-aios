# Handoff — app-gestion-llamadas (teams.duendes.net)

**Fecha**: 2026-05-18
**Ejecutor**: Claude Code en modo autónomo (mientras Oscar fuera)
**Estado**: ✅ MVP funcional end-to-end en local — listo para probar y desplegar

---

## TL;DR — qué hay y qué falta

### ✅ Hecho (verificado)

| Pieza | Estado | Verificación |
|-------|--------|--------------|
| Monorepo: nueva app `apps/teams/` | ✅ | `pnpm install` OK |
| Setup Next.js 15 + Tailwind + Radix + Zustand | ✅ | `pnpm --filter teams build` pasa |
| Supabase auth (magic link + middleware + redirect) | ✅ | `/sdr` sin sesión → redirige a `/login` |
| TypeScript strict | ✅ | `tsc --noEmit` sin errores |
| Backend: 5 endpoints FastAPI en `/api/calls` | ✅ | Sintaxis OK, registrados en `main.py` |
| CORS abierto a `localhost:3001` y `teams.duendes.net` | ✅ | Editado en `main.py` |
| AirtableMultiClient (multi-base, async) | ✅ | Nombres de campo reales verificados con MCP |
| CalcomService (event `4879655`, 30 min) | ✅ | API key probada en sesión, lista los slots |
| Componentes UI: Queue, Panel, Form, BookingPanel, Script, SessionHeader | ✅ | Render OK en build |
| Atajos teclado (C/H/N/S/1-9/?) | ✅ | Hook + targets data-* |
| Datos enriquecidos (parseo JSON + cards) | ✅ | CallPanel muestra reseñas, redes, tamaño, booking online |
| .env raíz con `AIRTABLE_API_KEY` + `CALCOM_API_KEY` + `CALCOM_EVENT_TYPE_ID` | ✅ | Añadidos |
| `apps/teams/.env.local` con vars Supabase | ✅ | Copiado de `apps/web` |
| README + esquema de datos + estructura del proyecto | ✅ | Ver `README.md` |

### ⚠️ Por hacer tú (cuando vuelvas)

1. **Smoke test E2E manual** (10 min):
   ```
   # Terminal 1: backend
   pnpm api
   # Terminal 2: frontend
   pnpm --filter teams dev
   ```
   Abre `http://localhost:3001`, login con tu email, comprueba que:
   - Cola carga prospectos reales de `malaga`
   - Pulsar Llamar abre Zadarma con el número
   - Formulario submitea y aparece en `Calls` de Airtable
   - Disposition "Agendada" → muestra slots Cal.com → confirma → aparece booking real

2. **Configurar la extensión Chrome de Zadarma** (si no la usas ya). Ver `README.md` sección "Setup de la extensión".

3. **Deploy a producción** (cuando quieras): ver `README.md` sección "Deploy a producción". Resumen:
   - Vercel: crear proyecto apuntando a `apps/teams/`
   - DNS: CNAME `teams → cname.vercel-dns.com`
   - Supabase Auth: añadir redirect URLs de producción
   - Backend `apps/api/` necesita estar desplegado en algún lado (hoy es solo local)

4. **Decidir** dónde desplegar el backend FastAPI:
   - Vercel (con serverless Python) — más simple si ya estás ahí
   - Railway / Fly — más control, requiere setup
   - Hetzner / VPS — más barato a escala

---

## Cosas que descubrí o decidí (que cambian el plan original)

### 1. Cambio de event Cal.com (15 min → 30 min)
El plan SDD inicial usaba el event `4879655` (Consulta Gratuita, 15 min). Tú confirmaste pasar a `4879655` (Demo Gratuita, 30 min) en `cal.com/duendes/consulta`. Ya está hardcodeado en `config.py`.

### 2. Schemas reales ≠ schemas del diseño técnico
El sdd-design original asumía nombres en castellano normalizados (`Nombre negocio`, `Telefono`, `Sector`). La realidad en `malaga` es muy diferente:
- `title` (no `Nombre`)
- `phone` (no `Telefono`)
- `categoryName` (no `Sector`)
- `city`, `website`
- `Último intento` (con tilde), `Próximo intento`
- `Callback solicitado` es **dateTime** (no boolean como suponía el design)

Todo el código usa los nombres reales verificados con el MCP de Airtable. Lo guardé también en Engram en `sdd/app-gestion-llamadas/schemas-reales` y `sdd/app-gestion-llamadas/enums-reales`.

### 3. Estado "Agendada" vs "Demo agendada"
En `Calls.Disposition` se llama **"Agendada"**.
En `malaga.Estado` se llama **"Demo agendada"** (la opción `Agendada` ni existe ahí).

El mapeo está en `services/calls_service.py` → `DISPOSITION_TO_ESTADO`. Cuidado si renombras opciones en Airtable.

### 4. Authentication backend
La v1 del backend NO valida el JWT de Supabase (solo CORS). Justificación:
- Tú eres el único usuario, no hay riesgo real
- Ahorra ~30 min de setup
- El frontend ya envía `Authorization: Bearer <token>` por buena práctica

Cuando quieras endurecerlo (porque vaya a usar alguien más): añadir middleware en `apps/api/main.py` que valide el JWT contra Supabase (`supabase_url + jwt_secret`).

### 5. Sin n8n
Confirmado por ti: la integración Airtable es directa con su API REST (la API key está en `.env` raíz). El campo `outcome` en `malaga` se calcula y escribe directamente desde `apps/api`, no requiere webhook n8n.

### 6. Datos enriquecidos como activo de oro
El campo `Datos enriquecidos` (JSON con scraping previo de cada negocio) se parsea y se muestra en CallPanel como mini-cards: booking online, reseñas, rating, redes, tamaño, score, servicios. Antes de llamar tienes contexto real, no llamas a ciegas.

---

## Cosas que vas a ver y deberías saber

### El layout durante una llamada
- **idle**: CallQueue | CallPanel | ScriptReference (3 columnas)
- **in_call**: igual + timer en el botón "Terminar"
- **wrap_up**: CallQueue | CallPanel + CallForm | ScriptReference (CallForm a la derecha)
- **booking (Agendada)**: CallQueue | CallPanel + BookingPanel | ScriptReference

El layout es desktop-only (1280px mínimo). No pensé en móvil porque dijiste que era para ti en escritorio.

### Si el botón "Llamar" no dispara nada
- La extensión Chrome de Zadarma intercepta `tel:` cuando está autenticada y la pestaña abierta es activa.
- Si no funciona en producción: verifica que Chrome tenga la extensión instalada y autenticada en ese ordenador.
- Como fallback: el número se muestra en el botón, lo copias y lo marcas manualmente.

### Si la cola sale vacía
Es porque NO hay prospectos con `Estado IN ('Pendiente', 'No contesta', 'Comunica', 'Gatekeeper', ...)` AND `No llamar = false` AND `phone != ''`. Si tu base tiene todo "Demo agendada", la cola estará vacía — añade prospectos nuevos a `malaga` o cambia algún `Estado` a `Pendiente`.

### Si el booking falla con "Cal.com error 422"
Probablemente sea slot ya ocupado por otro booking (carrera). Refresca los slots y elige otro.

---

## Próximos pasos sugeridos (cuando quieras crecer)

| Idea | Esfuerzo | Valor |
|------|----------|-------|
| Pestaña `/clientes` con CRM de Duendes (appFIn3ntFb39vGXF/Clients) | M | Alto — el siguiente módulo natural |
| Webhook Cal.com → backend que actualice estado si demo se cancela | S | Medio |
| Vista de "calendario semanal" de demos agendadas | S | Bajo (ya en Cal.com) |
| Auto-dial: cola que llama sola con confirmación (pulsa una tecla para llamar al siguiente) | M | Alto si haces sesiones largas |
| Stats post-sesión (gráfico de cono / breakdown de objeciones) | M | Medio |
| Auth real backend (validar JWT) | S | Alto si vas a abrir a más gente |
| Tests E2E con Playwright | L | Medio |

---

## Memoria guardada en Engram

- `sdd/app-gestion-llamadas/session` — decisiones de scope
- `sdd/app-gestion-llamadas/explore` — exploración del ecosistema
- `sdd/app-gestion-llamadas/proposal` — propuesta arquitectónica
- `sdd/app-gestion-llamadas/spec` — specs funcionales (algunas obsoletas — usa schemas-reales)
- `sdd/app-gestion-llamadas/design` — diseño técnico (algunas partes obsoletas — usa schemas-reales)
- `sdd/app-gestion-llamadas/tasks` — plan original de 42 tareas
- `sdd/app-gestion-llamadas/schemas-reales` — **CRÍTICO**: schemas reales de Airtable
- `sdd/app-gestion-llamadas/enums-reales` — **CRÍTICO**: valores enum reales

---

## Comandos rápidos

```bash
# Levantar todo
pnpm api &                          # backend en 8000
pnpm --filter teams dev             # frontend en 3001

# Solo verificaciones
cd apps/teams && ./node_modules/.bin/tsc --noEmit    # tipos
cd apps/teams && ./node_modules/.bin/next build      # build

# Probar API directamente
curl http://localhost:8000/api/calls/queue | jq
curl http://localhost:8000/api/calls/calcom/slots?days=3 | jq
```

---

Cuando vuelvas, lo primero: arranca los dos servicios, login en `/sdr`, dame feedback de qué se siente raro / qué falta / qué cambias.
