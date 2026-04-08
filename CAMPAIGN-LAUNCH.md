# 🚀 LANZAMIENTO INMEDIATO — Campaña Meta Ads Wellness

**Estado:** Listo para lanzar YA
**Presupuesto:** €100
**Periodo:** 30 mar - 8 abr (10 días)
**Objetivo:** 8-10 leads al CPL de €0.10-0.12

---

## Opción 1: Lanzamiento MANUAL (Meta Business Suite) — 15 minutos

### Step 1: Acceso a Meta Ads Manager
1. Ve a [ads.facebook.com](https://ads.facebook.com)
2. Selecciona **Ad Account:** `4415681465377005` (Duendes)
3. Click en **Campaigns** (sidebar izquierdo)

### Step 2: Crear campaña
1. Click en **+ Create** (botón azul)
2. **Campaign Objective:** `Lead Generation`
3. **Campaign name:** `Wellness Professionals — April 2026`
4. Click **Continue**

### Step 3: Configurar ad set
1. **Ad Set Name:** `Wellness Pros — Masaje + Fisio + Quiropráctica`
2. **Budget:** `€100` (total, no daily)
3. **Schedule:**
   - **Start Date:** 30 Mar 2026
   - **End Date:** 8 Apr 2026
   - ✅ **Run ads all day** (SIN restricciones horarias)

### Step 4: Audience (Audiencia)
1. **Target Audience:** `Create New`
2. **Location:** Spain
3. **Age:** 30-55
4. **Interests (ADD ALL):**
   - Wellness
   - Natural Health
   - Massage Therapy
   - Physiotherapy
   - Physical Therapy
   - Chiropractic
   - Small Business Owners
   - Entrepreneurship
   - Digital Marketing

5. **Exclusions (REMOVE THESE):**
   - Psychologists / Psychiatrists
   - Medical Doctors / Specialists
   - Dental Clinics
   - Hospitals
   - Pharmacies
   - Health Insurance

6. **Audience size:** Debe estar entre 200k-500k

### Step 5: Placements
1. **Automatic Placements:** OFF
2. **Manual Placements:** Selecciona SOLO:
   - ✅ Facebook Feed
   - ✅ Instagram Feed
   - ❌ Facebook Reels (descarta)
   - ❌ Messenger (descarta)
   - ❌ WhatsApp (descarta)

### Step 6: Crear Instant Form
1. Desde el ad set, click en **Forms**
2. Click **+ Create Form**
3. **Form Name:** `Wellness Webinar April`
4. **Tipo de formulario:** Instant Form
5. **Presentación:** (default)

**Step 6a: Configurar Preguntas**
   - Full Name (required)
   - Email (required)
   - Empresa (REQUIRED) ← obligatorio
   - Teléfono (optional) ← opcional
   - Sector: Remover (no disponible en Meta, lo ponemos automático: "Clínicas")

**Step 6b: Política de Privacidad**
En la sección "Política de privacidad", copia esto:
```
Usaremos tu información para:

• Enviarte la invitación y acceso al webinar gratuito del 8 de abril
• Recordarte el día anterior al evento
• Contactarte si tienes preguntas sobre el webinar

Tus datos se almacenan de forma segura. No compartimos tu información con terceros. Puedes solicitar eliminar tus datos en cualquier momento.
```

**Step 6c: Pantalla de Agradecimiento**
   - **Título:** `Ya estás registrado.`
   - **Descripción:**
   ```
   Ya estás registrado.

   Tu acceso al webinar más tu PDF de regalo te llegarán por email en 5 minutos.

   📅 Webinar: 8 de abril a las 19:00 CET
   🔗 Acceso: Confirmación + vídeo de bienvenida

   Mientras tanto, puedes ver el video de explicación del webinar a continuación.

   Nos vemos en vivo y muchas gracias.
   ```
   - **Acción adicional:** "Ir al sitio web"
   - **Enlace:** `https://duendes.net/webinar/confirmacion`
   - **Llamada a la acción:** "Acceder"

### Step 7: Crear anuncios (3 creatives)
1. Click **+ Add Ad Creative**
2. Para cada una de las 3 creatives (ver archivo campaign spec):

**Creative 1: Urgencia + Prueba Social**
- Upload image: masajistas/fisioterapeutas trabajando
- Headline: `Masajistas y fisioterapeutas que automatizan YA`
- Primary Text: `8 de abril. 8 profesionales en vivo. 0€ de inversión. Solo 2 horas.`
- CTA Button: `Sign Up`
- Form: Selecciona tu Instant Form

**Creative 2: FOMO + Transformación**
- Upload image: Before/After (estresado vs relajado)
- Headline: `De 50 citas manuales a 0 administrativos`
- Primary Text: `Sin bots caros. Sin chatbots que asustan. Solo tu voz, tu IA, tu empresa.`
- CTA Button: `Learn More`
- Form: Selecciona tu Instant Form

**Creative 3: Resultado Específico**
- Upload image: Teléfono con calendario automático
- Headline: `¿Gastas 2 horas/día en admin?`
- Primary Text: `Descubre cómo otros lo automatizaron en 30 minutos. Webinar 8 de abril.`
- CTA Button: `Learn More`
- Form: Selecciona tu Instant Form

### Step 8: Revisar y lanzar
1. **Billing:** Asegúrate de que está configurado ✅
2. Click en **Review**
3. Verifica todos los datos
4. **Click PUBLISH** ✅

### Step 9: Verificación inmediata
1. Abre otra ventana en **ads.facebook.com**
2. Ve a **Active Campaigns**
3. Deberías ver tu campaña con estado **ACTIVE**

---

## Opción 2: Lanzamiento AUTOMATIZADO (n8n) — 5 minutos

*(Futura automatización — pendiente de implementar en n8n)*

1. Ve a **n8n.duendes.net**
2. Importa el workflow: `n8n-webinar-lead-automation.json`
3. Configura tus credenciales de Meta
4. Activa el workflow

---

## Monitoreo diario (CRÍTICO)

### 9:00 AM CET — Daily Check
Abre **Ads Manager** → **Campaigns** y revisa:

| Métrica | Objetivo | Acción si falla |
|---------|----------|-----------------|
| **Impressions** | 1.5k-2k/día | Si <500 = aumentar budget |
| **Clicks** | 30-50/día | Si <15 = cambiar creative |
| **Leads** | 8-10/día | Si <5 = revisar form |
| **CPL** | €0.10-0.12 | Si >€0.15 = pausar audience |
| **CTR** | 2.5%+ | Si <1.5% = probar siguiente creative |

### Si algo falla:
1. **CTR bajo (<1.5%)** → Prueba siguiente creative
2. **CPL alto (>€0.15)** → Pausa el ad set, revisa audience
3. **Pocos leads (<5/día)** → Check que Instant Form funciona
4. **Form no se abre** → Check cookie consent, verificar dominio

---

## Integración automática de leads

### Webhook de Meta → n8n
1. Una vez que la campaña esté ACTIVE
2. Ve a **Form Settings** en el ad
3. Busca **Webhook URL**
4. Pega: `https://n8n.duendes.net/webhook/webinar-lead`
5. Test webhook

### Qué pasa automáticamente:
```
Lead en Meta → Airtable (registro) → Email bienvenida
→ Recordatorio (7 de abr, 17:00) → Email recordatorio
```

---

## Checklist final

- [ ] Airtable: Base de webinar lista
- [ ] Meta Ads Manager: Abierto
- [ ] Presupuesto €100: Verificado en tu cuenta
- [ ] 3 creatives: Descargadas / listas
- [ ] Copy: Copypasted del archivo `meta-ads-wellness-april-2026.md`
- [ ] Instant Form: Creado con campos correctos
- [ ] Audiencia: Configurada (200k-500k people)
- [ ] Placements: Solo Feed (FB + IG)
- [ ] Budget: €100 total, 30 mar - 8 abr
- [ ] Landing page: https://duendes.net/webinar/confirmacion (testado)
- [ ] n8n webhook: Configurado (post-lanzamiento)
- [ ] Alarmas: Establecidas para CPL >€0.15

---

## Después del lanzamiento

### Día 1-2 (30-31 mar)
- Monitor: Impresiones >500, Clicks >10
- Espera: Primeros leads deberían llegar en 4-6 horas

### Día 3-5 (1-3 abr)
- Optimización: Si CTR <1.5%, cambia creative
- Escalado: Si CPL <€0.12, aumenta budget +20%

### Día 6-8 (4-6 abr)
- Recordatorios: Verificar que emails se envían
- Asistencia: Trackear quiénes se registran en página confirmación

### Día 9-10 (7-8 abr)
- Últimas 24h: Budget restante en max delivery
- Recordatorios finales: +1 email la mañana del webinar

---

## Contingency (Si algo va mal)

| Problema | Causa | Solución |
|----------|-------|----------|
| Campaña no se publica | Billing error | Verificar método de pago en Meta |
| No aparecen leads | Form URL incorrecta | Revisar webhook de Meta |
| Form no aparece | Cookie bloqueadas | Check GDPR/privacy en Meta |
| CPL >€0.20 | Audience demasiado amplia | Reducir a age 35-50 + interests específicos |
| 0 impresiones | Budget daily muy bajo | Aumentar a €10-15/día mínimo |

---

## Contacto para apoyo
- Meta Business ID: 179145749483952
- Ad Account: 4415681465377005
- n8n: https://n8n.duendes.net
- Airtable: Verificar que credenciales estén en `.claude/settings.local.json`
