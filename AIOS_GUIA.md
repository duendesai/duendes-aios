# Duendes AIOS — Guía de Uso

> Para Oscar. Sin rodeos.

---

## 1. Arquitectura en 30 segundos

```
                    ┌─────────────────────────┐
                    │         OSCAR            │
                    └────────┬────────┬────────┘
                             │        │
                    Slack    │        │  Telegram
                  (desktop)  │        │  (móvil)
                             │        │
                    ┌────────▼────────▼────────┐
                    │         AIOS              │
                    │   (Claude Sonnet 4.6)     │
                    │                           │
                    │  orquestador / cmo / sdr  │
                    │  ae / coo / cfo / cs      │
                    └───┬──────────┬────────────┘
                        │          │
              ┌─────────▼──┐   ┌───▼──────────┐
              │  Airtable   │   │   Instantly   │
              │  (Engram)   │   │  (campañas)   │
              └─────────────┘   └──────────────┘
```

Todo pasa por Claude. Slack es el centro de operaciones (desktop), Telegram es acceso rápido (móvil).

---

## 2. Lo que funciona solo (sin hacer nada)

Tres procesos autónomos en background. No requieren intervención.

### Brief diario — 8:00h todos los días

`brief.py` se ejecuta vía launchd a las 8:00. Llega a **Telegram + #orquestador en Slack**.

Secciones que incluye (solo aparecen si hay datos):

| Sección | Fuente |
|---------|--------|
| Foco del día | IA (estrategia actual) |
| Tareas prioritarias | Airtable — tareas pendientes reales |
| Follow-ups SDR | Airtable — leads que necesitan contacto |
| Posts pendientes de publicar | Airtable — borradores en estado "listo" |
| Pipeline de cierre (AE) | Airtable — deals en Demo/Propuesta/Negociación |
| Facturas pendientes | Airtable — facturas sin cobrar |
| Clientes — check-in pendiente | Airtable — clientes sin contacto reciente |

### Reporte semanal — lunes a las 8:00h

Los lunes el brief incluye un bloque extra con: MRR total, leads nuevos (últimos 7 días), estado del pipeline AE y total de cobros pendientes.

### Monitor autónomo — cada 4 horas (14.400 segundos)

`aios_monitor.py` corre cada 4h. Solo te manda un mensaje si hay algo que hacer. Si todo está bien, silencio.

Las alertas van a **Telegram + al canal Slack correspondiente** (CFO → #finanzas, CS → #clientes, etc.).

| Check | Umbral | Acción automática |
|-------|--------|-------------------|
| CFO | Facturas con fecha de vencimiento pasada | Las marca como "Vencida" en Airtable + alerta |
| CS | Clientes con churn_risk=Alto + sin check-in en +14 días | Alerta |
| SDR | Leads en estado "Nuevo" sin contacto en +3 días | Alerta (máx. 10) |
| AE | Deals activos (Demo/Propuesta/Negociación) sin actividad en +7 días | Alerta |

### Sync de Airtable — 7:50h (antes del brief)

`airtable_sync.py` sincroniza datos antes del brief para que las secciones tengan datos frescos.

---

## 3. Slack — Centro de operaciones

### Canales y sus agentes

| Canal | Agente | Rol |
|-------|--------|-----|
| `#orquestador` / `#general` | Orquestador | Coordinador ejecutivo. Delega a otros departamentos automáticamente si detecta intención clara. Punto de entrada para preguntas generales y peticiones multi-depto. |
| `#marketing` / `#cmo` | CMO | Director de Marketing. Experto en contenido B2B, copywriting y posicionamiento. Genera posts LinkedIn, ideas de contenido y copy en el tono de Duendes. |
| `#captacion` / `#sdr` | SDR | Desarrollo de negocio. Prospección B2B, outreach en frío, gestión del pipeline de entrada. Puede lanzar búsquedas de leads via Apify. |
| `#ventas` / `#ae` | AE | Account Executive. Gestiona deals, genera propuestas comerciales y guía negociaciones hasta el cierre. |
| `#operaciones` / `#coo` | COO | Operaciones. Gestiona tareas, SOPs y procesos internos. |
| `#finanzas` / `#cfo` | CFO | Finanzas. Facturas, MRR y cashflow. |
| `#clientes` / `#cs` | CS | Customer Success. Retención, check-ins y detección de riesgo de churn. |

Cada canal carga el `CLAUDE.md` del departamento como system prompt. El agente es un experto en su área con conocimiento del contexto de Duendes.

### Comandos de lectura (datos reales de Airtable)

**#captacion (SDR)**

| Comando | Qué devuelve |
|---------|-------------|
| `leads` | Lista todos los leads activos |
| `lead N` | Detalle completo del lead #N |
| `calificar` | Score ICP con IA de todos los leads en estado "prospecto" |
| `campañas` | Campañas de Instantly activas |

**#ventas (AE)**

| Comando | Qué devuelve |
|---------|-------------|
| `deals` | Pipeline completo de deals |

**#operaciones (COO)**

| Comando | Qué devuelve |
|---------|-------------|
| `tareas` | Todas las tareas pendientes |

**#finanzas (CFO)**

| Comando | Qué devuelve |
|---------|-------------|
| `facturas` | Facturas pendientes |
| `mrr` | MRR actual |

**#clientes (CS)**

| Comando | Qué devuelve |
|---------|-------------|
| `clientes` | Lista de clientes activos |
| `churn` | Alertas de riesgo de churn |

**Cualquier canal**

| Comando | Qué devuelve |
|---------|-------------|
| `dashboard` / `resumen` / `estado del negocio` / `cómo vamos` | Snapshot de todos los módulos: MRR, clientes, leads, pipeline, tareas |

### Comandos de escritura (añadir/actualizar)

**#captacion (SDR)**

| Comando | Qué hace |
|---------|---------|
| `añadir lead Empresa \| Sector \| Ciudad` | Añade un lead nuevo a Airtable |
| `nota lead N texto` | Añade nota al lead #N |
| `estado lead N nuevo_estado` | Cambia el estado del lead #N |
| `push lead N M` | Genera email frío con IA y añade el lead #N a la campaña Instantly #M. Actualiza estado a "contactado" |

**#ventas (AE)**

| Comando | Qué hace |
|---------|---------|
| `añadir deal Empresa \| Sector` | Añade un deal nuevo |
| `nota deal N texto` | Añade nota al deal #N |
| `estado deal N nuevo_estado` | Actualiza el estado del deal #N |

**#operaciones (COO)**

| Comando | Qué hace |
|---------|---------|
| `añadir tarea texto` / `nueva tarea texto` | Añade tarea nueva |
| `hecho N` / `completar tarea N` / `tarea N hecha` | Marca la tarea #N como completada |

**#clientes (CS)**

| Comando | Qué hace |
|---------|---------|
| `checkin N` / `check-in N` | Registra check-in con el cliente #N (actualiza fecha de último contacto) |
| `nota cliente N texto` | Añade nota al cliente #N |

**#finanzas (CFO)**

| Comando | Qué hace |
|---------|---------|
| `añadir factura Cliente \| Concepto \| Importe` | Crea factura nueva en Airtable |

### Sub-agentes especializados

Se activan automáticamente cuando detectan intención, antes de pasar la pregunta al agente genérico del canal.

**#marketing — CMO Content Writer**

Detecta intención de generar contenido:
- Pide un post → genera post LinkedIn con voz/tono de Duendes
- Pide ideas → genera 5 ideas de contenido para el sector mencionado

Ejemplos que lo activan:
- _"Escríbeme un post sobre agentes de voz para fisios"_
- _"Dame ideas de contenido para esta semana"_

**#captacion — SDR Email Sequencer**

Detecta intención de crear secuencias o follow-ups:
- Pide una secuencia → genera secuencia de emails para la empresa/sector
- Pide un follow-up rápido → genera email de seguimiento con días especificados

Ejemplos:
- _"Crea una secuencia de 3 emails para Clínica Norte (dental)"_
- _"Genera un follow-up a 5 días para Fisio Madrid"_

**#ventas — AE Proposal Writer**

Detecta intención de propuestas o preparación de demos:
- Pide propuesta → genera propuesta comercial usando el contexto de ofertas
- Pide prep de demo → genera guía de puntos clave para la demo

Ejemplos:
- _"Prepara propuesta para Clínica García"_
- _"Prepárame para la demo de mañana con fisios"_

### Reuniones multi-departamento

Menciona varios agentes en cualquier canal con `@mentions` y cada uno responde en paralelo:

```
@marketing @sdr prepara una campaña para fisios en Madrid
```

El bot responde con las perspectivas de cada departamento concatenadas:
- `[Marketing]:` estrategia de contenido
- `[SDR]:` plan de prospección

Menciones disponibles: `@marketing`, `@cmo`, `@sdr`, `@ventas`, `@ae`, `@operaciones`, `@coo`, `@finanzas`, `@cfo`, `@clientes`, `@cs`

### Notas de voz

Graba un audio y envíalo al canal. El bot lo descarga y transcribe con OpenAI Whisper (idioma: español), luego procesa el texto transcrito como si fuera un mensaje de texto.

**Nota importante**: el audio se procesa en el canal donde lo envías. Enviar un audio en `#captacion` activa al agente SDR, no al orquestador.

### Comando universal: dashboard / resumen

Funciona en cualquier canal. Devuelve un snapshot en tiempo real de todos los módulos:

```
Dashboard Duendes — 26/03 09:15
MRR: 2.300€
Clientes activos: 4
Leads: 3 nuevos | 8 contactados | 2 en reunión
Pipeline AE: 5 deals activos
Tareas pendientes: 7
```

---

## 4. Telegram — Acceso móvil

Bot: `@DuendesCRM_bot`. Solo responde a tu Telegram ID. Bueno para: leer el brief, consultas rápidas en movimiento, actualizaciones de estado desde el móvil.

### Comandos generales

| Comando | Qué hace |
|---------|---------|
| `/start` | Reinicia el historial de conversación |
| `/status` | Estado del bot y archivos de contexto cargados |
| `/brief` | Genera y envía el brief ahora (sin esperar las 8h) |
| `/dashboard` | Snapshot de todos los módulos |
| `/sync` | Recarga el contexto de negocio desde los archivos `.md` |

### COO — Operaciones

| Comando | Qué hace |
|---------|---------|
| `/tareas [categoria]` | Lista tareas pendientes, opcionalmente filtradas por categoría |
| `/nueva <texto>` | Añade tarea. Formato: `/nueva alta:Llamar García #sales` |
| `/hecho <N>` | Marca la tarea #N como completada |
| `/pendiente` | Tareas vencidas hoy o atrasadas |

### SDR — Prospección

| Comando | Qué hace |
|---------|---------|
| `/leads [estado\|sector]` | Lista leads, opcionalmente filtrados |
| `/lead <N>` | Detalle del lead #N (ejecutar `/leads` primero) |
| `/lead <nombre>, <sector>, <ciudad>` | Añade un lead nuevo |
| `/leadstatus <N> <estado>` | Cambia el estado del lead #N |
| `/leadnota <N> <texto>` | Añade nota al lead #N |
| `/sdr buscar <sector> <ciudad>` | Busca prospectos en Google Maps via Apify. Tarda 2-3 min. |
| `/calificar` | Score ICP con IA de todos los leads en estado "prospecto" |
| `/calificar <N>` | Score ICP del lead #N |
| `/followup` | Lista leads que necesitan follow-up |
| `/email <N>` | Genera email frío para el lead #N (sin enviarlo) |
| `/campanas` | Lista campañas de Instantly activas |
| `/push <N_lead> <N_campaña>` | Genera email + añade lead a campaña Instantly |

### CMO — Contenido

| Comando | Qué hace |
|---------|---------|
| `/post [sector]` | Genera post de LinkedIn (general o por sector) |
| `/post idea` | Genera 3 ideas de contenido para LinkedIn |
| `/postguardar <texto>` | Guarda un post manual como borrador |
| `/posts [estado]` | Lista borradores guardados |
| `/poststatus <N> <estado>` | Cambia el estado del borrador #N (borrador / listo / publicado) |

### AE — Cierre

| Comando | Qué hace |
|---------|---------|
| `/deals [estado]` | Pipeline de deals, opcionalmente filtrado |
| `/deal <N>` | Detalle del deal #N |
| `/deal <empresa>, <sector>, <ciudad>, <contacto>` | Añade un deal nuevo |
| `/dealstatus <N> <estado>` | Actualiza el estado del deal #N |
| `/propuesta <N>` | Genera propuesta comercial para el deal #N con IA. La guarda en Airtable. |
| `/objecion <N> <texto>` | Registra una objeción del cliente en el deal #N |
| `/dealnota <N> <texto>` | Añade nota al deal #N |

### CFO — Finanzas

| Comando | Qué hace |
|---------|---------|
| `/ingresos` | Lista todas las facturas (marca vencidas automáticamente) |
| `/factura <N_cliente> \| <concepto> \| <importe>` | Añade factura. Ejecutar `/clientes` primero para ver los números. |
| `/pagada <N>` | Marca la factura #N como pagada |
| `/mrr` | MRR total calculado desde clientes activos |

### CS — Customer Success

| Comando | Qué hace |
|---------|---------|
| `/clientes` | Lista clientes activos + MRR total |
| `/cliente_nuevo <nombre> \| <contacto> \| <sector> \| <mrr>` | Añade cliente nuevo |
| `/checkin <N> [notas]` | Registra check-in con el cliente #N |
| `/churn` | Informe de clientes en riesgo |

### Lenguaje natural en Telegram

El bot también detecta intención en texto libre antes de pasar a Claude:

- `"tareas"` / `"qué tengo pendiente"` → `/tareas`
- `"añadir tarea X"` → añade tarea
- `"hecho 3"` → completa tarea #3
- `"leads"` → `/leads`
- `"factura"` / `"ingresos"` / `"mrr"` → muestra facturas

---

## 5. Flujos de trabajo recomendados

### Rutina de mañana (5 min)

1. Leer el brief de las 8h que llegó a Telegram
2. Si hay alertas del monitor activas → actuar primero (leads sin contactar, deals parados, clientes en riesgo)
3. Si hay follow-ups SDR → en Telegram `/followup` o en `#captacion` escribe `leads`
4. Si hay deals calientes → en `#ventas` escribe `deals` o en Telegram `/deals`
5. Si hay posts listos → publicar en LinkedIn y actualizar estado: `/poststatus N publicado`
6. Si hay check-ins pendientes → en `#clientes` escribe `clientes` y hace `/checkin N`

### Flujo completo de prospección

1. En Telegram: `/sdr buscar fisio Madrid` (o el sector/ciudad que toque)
2. Esperar 2-3 minutos → llega resumen con leads encontrados y guardados en Airtable
3. `/calificar` → score ICP de los nuevos leads
4. `/leads` → ver la lista actualizada e identificar los mejores
5. `/campanas` → ver campañas Instantly disponibles
6. Para cada lead prioritario con email: `/push N M` → email generado con IA + añadido a campaña automáticamente. Estado actualizado a "contactado".
7. El monitor avisará si llevan +3 días sin respuesta

### Flujo de cierre

1. Lead responde a campaña → actualizar estado en Telegram: `/leadstatus N interesado`
2. Crear deal: `/deal Clínica X, fisio, Madrid, Ana`
3. Preparar demo en `#ventas`: _"prepara puntos clave para la demo de Clínica X (fisioterapia, quieren reducir llamadas perdidas)"_
4. Después de la demo: `/dealstatus N propuesta`
5. Generar propuesta: `/propuesta N` (se guarda en Airtable automáticamente)
6. Si hay objeción: `/objecion N el precio les parece alto`
7. Monitor avisará si el deal lleva +7 días sin actividad
8. Cierre ganado: `/dealstatus N ganado`
9. Añadir cliente: `/cliente_nuevo Clínica X | Ana | fisio | 229`

### Flujo de contenido

1. En `#marketing` pide ideas: _"Dame ideas de contenido para esta semana"_
2. El sub-agente CMO genera 5 ideas
3. Elige una y pide el post: _"Escríbeme un post sobre la idea 3, tono directo con datos"_
4. Si está bien, guarda como borrador: `/postguardar [texto del post]`
5. Cuando lo publiques en LinkedIn, actualiza estado: `/poststatus N publicado`
6. El brief del día siguiente reflejará si quedan posts en estado "listo"

---

## 6. Servicios del sistema (launchd)

Cinco plist en `~/Library/LaunchAgents/`. El Mac tiene que estar encendido para que se ejecuten.

| Servicio | Label | Cuándo corre | Qué hace |
|---------|-------|-------------|---------|
| Bot Telegram | `com.duendes.aios.bot` | Siempre activo (keepAlive) | Atiende comandos y mensajes de Telegram en polling mode |
| Slack Bot | `com.duendes.aios.slack` | Siempre activo (keepAlive) | Atiende mensajes de Slack en socket mode |
| Brief diario | `com.duendes.aios.brief` | 8:00h diario | Genera y envía el brief a Telegram + #orquestador |
| Monitor autónomo | `com.duendes.aios.monitor` | Cada 4h (14.400s) | Comprueba vencimientos, churn, leads parados, deals parados |
| Sync Airtable | `com.duendes.aios.sync` | 7:50h diario | Sincroniza datos de Airtable antes del brief |

### Gestión de servicios

```bash
# Ver estado de todos los servicios AIOS
launchctl list | grep duendes

# Parar un servicio
launchctl unload ~/Library/LaunchAgents/com.duendes.aios.bot.plist

# Arrancar un servicio
launchctl load ~/Library/LaunchAgents/com.duendes.aios.bot.plist

# Ver logs
tail -f /Users/oscargrana/duendes-aios/scripts/logs/bot.log
tail -f /Users/oscargrana/duendes-aios/scripts/logs/slack_bot.log
tail -f /Users/oscargrana/duendes-aios/scripts/logs/brief.log
tail -f /Users/oscargrana/duendes-aios/scripts/logs/monitor.log
```

---

## 7. Glosario rápido

| Término | Qué significa en este AIOS |
|---------|---------------------------|
| **Orquestador** | El agente de `#orquestador`. Detecta delegación con Haiku (micro-llamada barata) y enruta al departamento correcto |
| **Context OS** | Los archivos `.md` de `context/` (estrategia, negocio, ofertas, clientes-ideales). Se cargan como contexto de todos los agentes |
| **CLAUDE.md** | El system prompt del departamento. Uno por módulo en `modulos/<dept>/CLAUDE.md` |
| **Engram** | Sistema de memoria persistente. Los módulos lo usan para leer/escribir datos de Airtable via el cliente |
| **Display ID** | El número secuencial (#1, #2, #3) que ves en las listas. No es el ID de Airtable. Se renueva en cada `/leads`, `/deals`, etc. |
| **Estado "prospecto"** | El estado inicial de un lead antes de ser calificado o contactado |
| **Churn risk** | Campo del cliente en Airtable: Bajo / Medio / Alto. El monitor solo alerta en Alto + check-in >14 días |
| **ICP score** | Puntuación del calificador SDR (0-10). Mide qué tan bien encaja el lead con el Ideal Customer Profile |
| **Push a Instantly** | Generar email frío con IA + añadir lead a campaña de email outreach de Instantly en un solo paso |
| **Sub-agente** | Módulo especializado que se activa antes de la llamada genérica a Claude. CMO Writer, SDR Sequencer, AE Proposal Writer |

---

_Duendes AIOS — actualizado el 26/03/2026_
