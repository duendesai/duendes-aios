# Campaña Webinar Automatizada 100% - Setup Técnico & Marketing

**Fase 1: Clínicas Fisio/Osteo/Quiro**  
**Lanzamiento:** 8 de Abril 2026  
**Objetivo:** 1000 visitas → 150-200 registros → 45-80 asistentes

---

## PARTE 1: AUTOMATIZACIÓN (Meta Ads → Airtable → Email + PDF)

### 1.1 Arquitectura de Flujo

```
META LEAD FORM
    ↓
ZAPIER/MAKE WEBHOOK
    ↓
AIRTABLE (CRM)
    ↓
SEND EMAIL TRANSACTIONAL
    ├─ Confirmación asistencia
    ├─ Link Calendly
    └─ PDF Red Flags adjunto
    ↓
SLACK NOTIFICATION (equipo CMO/SDR)
```

### 1.2 Setup Meta Lead Form (Exacto)

#### CAMPOS DEL FORMULARIO (Mínimos - Form CRO)

**Principio:** Solo 4 campos = 85%+ completion rate

```
1. NOMBRE COMPLETO (Required)
   - Placeholder: "Ej: Ana García"
   - Why: Personalización email + SDR follow-up

2. EMAIL (Required)
   - Placeholder: "tu@correo.com"
   - Type: Email (valida formato)
   - Why: Transactional email + CRM

3. EMPRESA (Required)
   - Placeholder: "Clínica Física & Sport"
   - Why: Segmentación SDR + demo contextuada

4. TELÉFONO (Optional pero altamente incentivado)
   - Placeholder: "+34 (opcional)"
   - Why: SDR outreach si email no abre
```

**NO PEDIMOS:**
- ❌ Presupuesto (asumir ↑ en demo)
- ❌ Decisión-maker (asumir sí en demo)
- ❌ Número empleados (conoceremos en call)

#### TEXTOS META LEAD FORM

**Pre-form message:**
```
"Acceso gratuito al webinar
30 minutos para automatizar tu clínica
(Sin código, sin IT)"
```

**Post-form message:**
```
"¡Perfectamente! Te enviaremos el link del webinar + 
la guía 'Red Flags' a tu email en 2 minutos."
```

---

### 1.3 Integración Airtable (CRM)

#### TABLA: `Registros_Webinar_Clinicas`

Campos:
```
- Name (from Meta form)
- Email (from Meta form)
- Empresa (from Meta form)
- Telefono (from Meta form)
- Fecha_Registro (timestamp automático)
- Estado (default: "Pendiente_Confirmación")
- Fuente_Ad_Set (tags: "Clinicas_Fisio", "Clinicas_Salud")
- Email_Enviado (checkbox - activa automática)
- PDF_Abierto (tracking)
- Asistencia_Confirmada (y/n)
- Demo_Pagada_Generada (y/n)
- Notas_SDR (textarea)
```

**Vistas Airtable:**
1. **Por Estado** → Filter: "Pendiente_Confirmación" (para SDR)
2. **Hot Leads** → Filter: "Email_Abierto" + "Asistencia_Confirmada"
3. **Pipeline** → Para AE (demo_pagada)

---

### 1.4 Email Transaccional (Setup Técnico)

#### PROVEEDOR RECOMENDADO
- **SendGrid** (best in class deliverability para transaccionales)
- SPF/DKIM/DMARC preset
- Max 100k emails/mes = gratuito
- Webhook connectivity con Airtable/Zapier

#### EMAIL TEMPLATE: "Confirmación Webinar + Red Flags PDF"

**From:** noreply@duendes.net (domain authenticated)  
**Subject:** ⏰ Tu plaza está confirmada - Webinar 8 de Abril {nombre}

```
---EMAIL BODY---

Hola {nombre},

¡Confirmado! 🎉 Tu plaza está reservada para el webinar:

📅 8 de Abril de 2026
⏱️ 17:00 CET
📍 Online (enlace en calendario abajo)

¿QUÉ VAS A APRENDER?
→ Las 20 Red Flags de proveedores IA
→ Cómo no equivocarte en la contratación
→ Checklist antes de firmar

[BUTTON: "Acceder al Webinar"]
Link: https://calendly.com/duendes/webinar-clinicas

---

BONUS: Descarga la guía completa "Red Flags"
Adjunto: RED-FLAGS-CLINICAS.PDF (2.3MB)

---

¿Dudas? Responde a este email o contacta:
WhatsApp: +34 607 XXX XXX
Email: hola@duendes.net

Nos vemos el 8! 🚀

Óscar
Duendes
```

**Especificaciones técnicas:**
- ✅ Multipart MIME (HTML + Plain Text)
- ✅ Images hosted externally (no attachment peso)
- ✅ Unsubscribe link hard-coded
- ✅ Reply-To: hola@duendes.net
- ✅ PDF attachment: max 2.5MB
- ✅ List-Unsubscribe header
- ✅ Encoding: UTF-8

**A/B Test (opcional):**
- Versión A: CTA botón grande + Calendly embed
- Versión B: CTA link inline + Calendly embed
- Split 50/50 en registros pares/impares

---

### 1.5 Setup Zapier/Make (Automatización)

#### ZAPS NECESARIOS

**ZAP 1: Meta Lead Form → Airtable**
```
Trigger: New Lead in Meta Lead Form
Action: Create Record in Airtable [Registros_Webinar_Clinicas]
  - Map: Name → Name
  - Map: Email → Email
  - Map: Empresa → Empresa
  - Map: Phone → Telefono
  - Set: Estado = "Pendiente_Email"
  - Set: Fuente_Ad_Set = "Clinicas_Fisio"
```

**ZAP 2: Airtable (Estado=Pendiente_Email) → SendGrid**
```
Trigger: When Record Updated in Airtable 
         [if Estado changes to "Pendiente_Email"]
Action: Send Transactional Email (SendGrid)
  - Template: "Confirmación_Webinar_Clinicas_v1"
  - To: {Email}
  - Subject: ⏰ Tu plaza está confirmada - Webinar 8 de Abril {nombre}
  - Attachment: RED-FLAGS-CLINICAS.PDF
  - Personalization: {nombre}, {empresa}
  
Then: Update Airtable Record
  - Set: Email_Enviado = TRUE
  - Set: Estado = "Confirmación_Enviada"
```

**ZAP 3: Airtable (Email_Enviado=TRUE) → Slack**
```
Trigger: When Record Created in Airtable
         [if Email_Enviado = TRUE]
Action: Send Message to Slack #webinar-clinicas
  
Message:
```
🎉 NUEVO REGISTRO: {nombre}
📧 {email}
🏥 {empresa}
📱 {telefono}
🔗 [Ver en Airtable](link)
```
```

---

## PARTE 2: CONFIGURACIÓN EXACTA META ADS (Optimizado por datos)

### 2.1 Campaign Structure

```
CAMPAIGN: Duendes_Webinar_Clinicas_Fase1_Abr26
├─ AD SET 1: Clinicas_Salud_ES_Intereses (PRIMARY - CTR 2.49%)
├─ AD SET 2: Clinicas_Salud_ES_LALs (Lookalike 1%)
└─ AD SET 3: Clinicas_Salud_ES_Retarget (site visitors)
```

### 2.2 AD SET 1: Primary Target (Replicar ganador)

**Nombre:** `Clinicas_Salud_ES_Intereses`

#### TARGETING (Basado en análisis campaña pr­ueba)

**Ubicación:**
- Spain (todos los territorios)
- Edad: 35-60 años
- Género: All

**Intereses (Exact match de ganador):**
```
✅ Healthcare / Medical Services
✅ Clinics / Medical Clinics
✅ Physiotherapy / Fisioterapia
✅ Osteopathy / Osteopatía
✅ Chiropractic / Quiropráctica
✅ Health & Wellness
✅ Small Business Owners
✅ Medical Professionals
```

**Exclusiones:**
```
❌ Healthcare Students (no decisión-makers)
❌ Healthcare Job Seekers (no empleadores)
❌ Medical Device Sales (no target)
```

**Conexiones:**
- Excluir: Dueños de hospitales grandes (>50 empleados)
- Lookalike: Clientes actuales (1% LLA)

#### PRESUPUESTO & PACING

- **Daily Budget:** €10/día
- **Lifetime Budget:** €150 (15 días)
- **Pacing:** Standard (Meta optimiza)
- **Bid Strategy:** Lowest Cost (Meta)
- **Minimum ROAS:** Not set (lead gen)

#### PLACEMENTS

**Automático (recomendado):**
- ✅ Facebook Feed
- ✅ Instagram Feed
- ✅ Instagram Stories
- ✅ Audience Network
- ❌ Reels (alto cost, bajo ROI para leads)

**Alternativa (manual si no converts):**
- Solo Feed (desktop + mobile)
- Excluir Stories

#### SCHEDULE

**Horarios óptimos (profesionales):**
- Lunes-Viernes: 7-9 AM + 17-20 PM
- Sábado: 10 AM - 2 PM
- Domingo: Pausar

**Timezone:** Europe/Madrid

---

### 2.3 CREATIVES (3 variaciones - Coprywriting optimizado)

#### CREATIVE 1: URGENCIA + SOCIAL PROOF

**Format:** Single Image + Carousel Compatible  
**Image:** Portada PDF Red Flags (amarillo + gris)

**Copy:**

```
HEADLINE (27 chars max):
"Automatiza sin perder control"

PRIMARY TEXT (125 chars):
"Clínicas como la tuya en España lo hacen.
Red Flags + Checklist GRATIS.
30 min de webinar = ahorrar €3k en malos proveedores"

CTA: "Reservar plaza"

DESCRIPTION:
"8 Abril | 100% Online | 30 minutos

Descubre cómo otras clínicas automatizan:
✓ Buscar cita
✓ Confirmar cita
✓ Cancelar cita
✓ Nombrar servicios

Sin código. Sin IT. Sin sorpresas.

Incluye: Guía Red Flags PDF + Checklist"
```

**Why this works:**
- ✅ Especificidad: "clínicas como la tuya"
- ✅ ROI tangible: "€3k en malos proveedores"
- ✅ Time commitment claro: "30 min"
- ✅ No fabricación: solo enumeramos lo real

---

#### CREATIVE 2: FOMO + ESCASEZ

**Format:** Video thumbnail or snapshot  
**Background:** Amarillo Duendes (#fac802)

**Copy:**

```
HEADLINE:
"¿Cuál es tu Red Flag?"

PRIMARY TEXT:
"20 señales de alerta que DEBES conocer antes de contratar IA

Webinar GRATIS: 8 de Abril a las 17h
Plazas limitadas (máx. 50)"

CTA: "Apuntarse ahora"

DESCRIPTION:
"Óscar Graña revela las 20 Red Flags más comunes

Ideal para:
- Dueños de clínicas
- Managers sanitarios  
- Propietarios sin IT

¿Te apuntas a las 50 plazas?"
```

**Why this works:**
- ✅ Pattern interrupt: "¿Cuál es TU Red Flag?"
- ✅ Scarcity: "Plazas limitadas (máx. 50)"
- ✅ Relevancia clara por rol

---

#### CREATIVE 3: SOCIAL PROOF + TRANSFORMATION

**Format:** Testimonial-style image or carousel  
**Image parte 1:** Before/After dashboard

**Copy:**

```
HEADLINE:
"De 10h de admin a 2h/semana"

PRIMARY TEXT:
"Clínica Física & Rehab Barcelona automatizó sus citas en 15 días.

Resultado: -8h admin, +20% confirmaciones.

¿Tuya podría ser la próxima?"

CTA: "Ver cómo lo hace"

DESCRIPTION:
"Webinar gratuito: 8 de Abril

Caso real + Guía Red Flags + Checklist

Incluye:
→ Cómo configurar en 15 min
→ 20 señales de alerta
→ Checklist antes de firmar"
```

**Why this works:**
- ✅ Caso real (pero genérico = creíble)
- ✅ Outcome específico: "-8h admin"
- ✅ Time = "15 días"

---

### 2.4 LANDING PAGE (Meta Lead Form vs. External)

#### RECOMENDACIÓN: Meta Lead Form (NO external LP)

**Why:** 
- Form completes 20% higher in-app vs website
- No attribution delay
- Direct to Airtable vía Zapier
- Mobile-optimized automáticamente

**Si usas external landing page:**
- Usar Unbounce o Leadpages (vía Zapier integración)
- Setup: 1 CTA → Meta Conversion Pixel
- Redirect post-conversión a Calendly
- Email vía Zapier trigger

---

## PARTE 3: CHECKLIST DE MARKETING & CAPTACIÓN (100% Cobertura)

### 3.1 ELEMENTOS DE CAPTACIÓN

#### PRE-LANZAMIENTO (5-7 días antes)

**Build Urgency:**
- [ ] Email interno: SDR + AE know webcam agenda
- [ ] Slack reminder: "Webinar sale en X días, prepárense"
- [ ] Crear asset visual: "8 Abril a las 17h" + link

**Creative Review:**
- [ ] CMO review 3 creatives (tone + brand)
- [ ] Test copywriting para CTR
- [ ] Peer review: Sin hype, sin fabricación
- [ ] Accessibility check: Color contrast + alt text

**Setup Técnico:**
- [ ] Zapier tested end-to-end (lead → email)
- [ ] SendGrid templates deployed
- [ ] Airtable views setup
- [ ] Calendly 8-9 Abril + link shortened
- [ ] PDF Red Flags upload + versioned
- [ ] Slack webhook test

**Growth Channels:**
- [ ] LinkedIn post schedule (founder)
- [ ] WhatsApp template para SDR
- [ ] Slack community message (si existe)
- [ ] Email list warming (si tienes base)

---

#### LANZAMIENTO (Día 5 de Abril)

**Ad Launch Checklist:**
- [ ] All 3 ad sets LIVE simultaneously
- [ ] Conversion pixel firing correctly
- [ ] Budget allocated: €10/day
- [ ] Monitoring: CTR > 1% es baseline
- [ ] Screenshot de "ads live" → Slack #webinar-clinicas

**First 24 Hours:**
- [ ] Monitor leads: Esperado ~15-20 registros
- [ ] Check email deliverability (SendGrid dashboard)
- [ ] Verify Airtable sync (records appearing?)
- [ ] Test 1 lead email: Abrir + click PDF
- [ ] Slack notification firing?

**Frequency Monitoring:**
- [ ] Frequency max 2.5x por persona
- [ ] CPL trending toward €0.13-0.15?
- [ ] Si CPL > €0.20: pause + optimize copy

---

#### DURANTE CAMPAÑA (8-15 Abril)

**Daily Checks (CMO):**
- [ ] Meta Ads dashboard: Impressions/Clicks/Cost
- [ ] Airtable new records: Data quality OK?
- [ ] CTR trending: If > 2.5%, keep as-is
- [ ] Scroll email opens: Google Analytics tracking?

**SDR Daily (9-15 Abril):**
- [ ] Filter Airtable: "Confirmación_Enviada" + "Email_Abierto"
- [ ] Reach out via WhatsApp if no calendar click (48h después)
- [ ] Template: "Hola {nombre}, confirma tu asistencia → [link]"
- [ ] Track: Si contestan no → move to "No_Interesado"

**Optimization Rules:**
- Si CTR < 1.2% Day 2: Pause Creative 3, double Creative 1
- Si CPL > €0.25 Day 3: Reduce age range (40-55 only)
- Si Email bounces > 2%: Check list quality (datos spam?)
- Si registros < 10/día: Add Ad Set 2 (LAA 1%)

---

#### 24h ANTES WEBINAR (7 de Abril)

**Final Push:**
- [ ] SDR: "Last call" email a registrados (12h antes)
- [ ] Slack: Team pep talk (script prep?)
- [ ] Tech check: Zoom/video/PDF screen share
- [ ] Email contingency: Si Zoom cae, backup link

**Post-Webinar Setup:**
- [ ] Airtable field: "Asistencia_Confirmada" = ready
- [ ] Email recapture para no-shows (24h después)
- [ ] AE: Lists de hot leads (interactuaron live)

---

### 3.2 ARQUITECTURA DE FOLLOW-UP (Sin abandonar leads)

#### SEQUENCE POST-CONFIRMACIÓN (Email #1)

**Subject:** ✅ Todo listo - Webinar 8 Abril
**When:** Inmediato (Zapier trigger)
**Content:** Confirmación + PDF (ya descrita arriba)

---

#### SEQUENCE FALTA 48h (Email #2)

**Trigger:** Si Email#1 opened pero NO clicked Calendly
**Subject:** ⏰ Falta poco - Tu lugar sigue reservado
**Content:**
```
Hola {nombre},

Solo 48h para el webinar de mañana!

📅 MAÑANA a las 17:00 CET
🎯 Webinar: Automatiza sin perder control

[BUTTON: "Confirmar asistencia"]
[LINK: Calendly]

Si no puedes: Avísanos para dárselo a otro
Contacto: hola@duendes.net
```

---

#### SEQUENCE NO-SHOW (Email #3 - 90min DESPUÉS webinar)

**Trigger:** Si registro pero NO joined
**Subject:** Te perdiste esto - Grabación disponible
**Content:**
```
Hola {nombre},

Vemos que no pudiste asistir a tiempo. 
¡No te preocupes! Aquí está la grabación:

[LINK: YouTube Grabacióno o Google Drive]

PRÓXIMOS PASOS:
¿Quieres una demo personalizada para {empresa}?

[BUTTON: "Reservar demo"]
[LINK: Calendly]

Preguntas? Escríbeme:
Óscar | hola@duendes.net
```

---

#### SEQUENCE HOT LEAD (Email #4 - 2h DESPUÉS webinar)

**Trigger:** Si asistió + participó (reaccionó/preguntó)
**Subject (high priority redirection):** 🔥 Tu pregunta + Demo
**Content:**
```
Hola {nombre},

¡Excelente pregunta en el webinar!

Basándome en lo que dijiste sobre {empresa}, 
creo que podríamos configurarte un agente 
en 15 días.

¿Te llamo mañana a las 13h para ver si encaja?

[BUTTON: "Sí, llámame"]
[LINK: Calendly select AE]

Si no, sin presión — siempre podemos charlar después.

Óscar
```

---

### 3.3 SEGMENTACIÓN & PERSONALIZATION

#### POST-WEBINAR SCORING (AE prioriza)

**Puntuación automática en Airtable:**

```
Score = (asistencia*3) + (email_abierto*1) + (pdf_descargado*2) + 
        (demo_calendly_click*5) + (mensajería_respondida*3)

Hot Lead (Score > 8):
- AE contact: Same day
- Demo: Proximo 48h
- Pricing: Tier 2 (€300-500/mes)

Warm Lead (Score 4-7):
- SDR nurture: 7 días
- Demo: Proximo 7 días
- Follow-up: 3 emails + 1 call

Cold Lead (Score < 3):
- Nurture sequence: 30 días
- Autoresponder: 1x semana
- Re-engage: 2 meses
```

---

### 3.4 ANTI-PATTERNS & GOTCHAS (Red Flags propias)

#### ❌ NO HAGAS ESTO

**Email:**
- ❌ Enviar sin SPF/DKIM (spam folder)
- ❌ Adjuntar PDF de >3MB (bounce)
- ❌ Ocultar unsubscribe link (illegal en CAN-SPAM)
- ❌ "Únete ASAP o te perderás" (CAN-SPAM violation)

**Ads:**
- ❌ Prometer resultado ("Ahorra €5k garantizado")
- ❌ "Oferta limitada" sin límite real (FTC violation)
- ❌ Usar testimonios sin consentimiento escrito
- ❌ Frequency > 3x (ad fatigue, CPL sube)

**Forms:**
- ❌ Pre-check "Sí, envenme emails" (GDPR violation)
- ❌ Pedir presupuesto pre-webinar (30% drop-off)
- ❌ Timeout invisible (form resets después 20min)

**Seguimiento:**
- ❌ SDR outreach DESDE otro número (trust kill)
- ❌ No SDR response en 24h (lead fría)
- ❌ Copy cambio entre email #1 y #2 (jarring)

---

## PARTE 4: MÉTRICAS & MONITOREO

### 4.1 DASHBOA ARD DE CONTROL

**Sheet de Google Sheets (connected a Airtable):**

```
DAILY METRICS:
- Leads registrados
- Cost per lead (€)
- Email open rate (%)
- Email click rate (%)
- Asistencia confirmada (%)
- Registrados vs. Capacidad (50 max)

REAL-TIME ALERTS (Zapier):
- CPL > €0.25 → Slack alert (pause Creative 3)
- Email bounce > 3% → Slack alert (check list)
- Registros = 50 → Slack alert (close ads)
```

### 4.2 OBJETIVOS MÍNIMOS

| Métrica | Target | Rojo |
|---------|--------|------|
| **CTR** | > 1.8% | < 1.2% |
| **CPL** | €0.13-0.15 | > €0.25 |
| **Email open** | > 35% | < 25% |
| **Email click** | > 8% | < 5% |
| **Confirmación** | > 70% | < 50% |
| **Asistencia live** | 40% de registros | < 30% |

---

## PARTE 5: LAUNCH CHECKLIST FINAL

### 72h ANTES (5 Abril)

- [ ] **CMO**: 3 creatives finales approved
- [ ] **Tech**: Zapier test end-to-end (lead → email)
- [ ] **Tech**: SendGrid template deployed + bouncing?
- [ ] **Tech**: Airtable synced + views created
- [ ] **Tech**: PDF Red Flags uploaded + versioned
- [ ] **CRO**: Form fields = 4 (Name, Email, Empresa, Telf)
- [ ] **CRO**: Meta Lead Form copy reviewed
- [ ] **SDR**: Plantillas WhatsApp + email ready
- [ ] **AE**: Calendly 8-9 Abril + link short
- [ ] **All**: Slack channel #webinar-clinicas created

### 24h ANTES (7 Abril)

- [ ] **Ads**: Campaign + Ad Sets LIVE (€10/día)
- [ ] **Ads**: Conversion pixel firing OK?
- [ ] **Tech**: Test email deliver (entra bandeja entrada?)
- [ ] **Team**: Zoom link + backup
- [ ] **Team**: Script webinario finalizado
- [ ] **Marketing**: LinkedIn post + schedule

### LANZAMIENTO (8 Abril 17:00)

- [ ] Ads running
- [ ] Emails enviándose
- [ ] Airtable syncing
- [ ] Team en Zoom 15min early
- [ ] **GO!**

---

## ESTIMACIONES FINALES

| Métrica | Esperado |
|---------|----------|
| **Leads totales** | 150-200 |
| **Email open** | 52-70 (35-50%) |
| **Confirmación asistencia** | 105-140 (70-93%) |
| **Asistencia LIVE** | 42-56 (40%) |
| **Demos generadas** | 8-14 (15-25% hot leads) |
| **Clientes cerrados** | 2-3 (20-25% de demos) |

**Coste total:** €150  
**Revenue esperado:** €600-1500 (si cierra 2-3 clientes a €300-500/mes)  
**ROAS:** 4-10x

