# Configuración Meta Ads - Clínicas Fisio/Osteo - COPIAR Y PEGAR

**Basado en:** Análisis campaña prueba (CTR 2.49%, CPL €0.13)  
**Target:** €0.13-0.15 CPL | 1000+ visitas | 150-200 leads  

---

## STEP-BY-STEP: CREAR CAMPAÑA EN MINI ADS MANAGER

### 1. CAMPAIGN SETUP

```
NOMBRE: Duendes_Webinar_Clinicas_Fase1_Abr26

OBJETIVO: Leads
ESPECIFICACIÓN: Lead Generation (Meta Form)

PRESUPUESTO:
- Type: Lifetime Budget
- Cantidad: €150
- Desde: 5 Abril 2026 00:00
- Hasta: 22 Abril 2026 23:59

TIPO OFERTA: Lowest Cost
(Meta optimiza automáticamente)
```

---

### 2. AD SET 1: PRIMARY TARGET

```
NOMBRE: Clinicas_Salud_ES_Intereses

PRESUPUESTO DIARIO: €10/día

CALENDARIO:
- Duración: 5 Abril - 22 Abril (18 días)
- Horario: Personalizado (ver abajo)

UBICACIÓN:
- País: Spain (todo el territorio)
- Localización específica: No (match nacional)

EDAD: 35-60

GÉNERO: All

IDIOMA: Spanish (es_ES)

DISPOSITIVOS:
- Desktop: ✓
- Mobile: ✓
- Tablet: ✓

SISTEMA OPERATIVO: All
```

#### TARGETING INMEDIATO (Intereses)

```
AGREGAR INTERESES (Exclude between groups con OR):

Interés Group 1 (Healthcare):
- Healthcare
- Medical Services
- Hospital

Interés Group 2 (Específicos):
- Physiotherapy / Fisioterapia
- Osteopathy / Osteopatía  
- Chiropractic / Quiropráctica
- Massage / Masaje

Interés Group 3 (Pequeño negocio):
- Small Business Owners
- Entrepreneurs
- Healthcare Professionals

LÓGICA: (Group1 OR Group2) AND Group3
= Personas con interés salud Y pequeño negocio
```

#### EXCLUSIONES

```
EXCLUIR INTERESES:
- Healthcare Students
- Medical Job Seekers
- Healthcare Equipment Sales
- Medical Device Reps

EXCLUIR EDAD: < 35 y > 65

EXCLUIR COMPORTAMIENTOS:
- Excluir: Personas que nunca compran online
```

#### PLACEMENTS (Automático recomendado)

```
PLACEMENTS: AUTOMÁTICO
- Facebook Feed ✓
- Instagram Feed ✓
- Instagram Stories ✓
- Audience Network ✓
- Facebook Reels ✗ (alto CPL)
- Instagram Reels ✗ (alto CPL)
- Messenger ✗ (baja intent)
```

#### SCHEDULE HORARIO

```
AJUSTAR PUJAS POR HORA (Lookahead Window):

Lunes-Viernes:
- 07:00-09:00 CET: +20% puja (morning goal-setters)
- 12:00-14:00 CET: -10% puja (lunch slump)
- 17:00-20:00 CET: +15% puja (evening professionals)
- 21:00-07:00 CET: -20% puja (sleep time)

Sábado:
- 10:00-14:00 CET: Normal puja
- Resto: Pausar

Domingo:
- Pausar completamente
```

---

### 3. LEAD FORM CONFIG (Meta Form - NO Landing externa)

```
USAR LEAD FORM: Sí

CAMPOS FORMULARIO:
1. First Name (Pre-populated: No)
2. Email Address (Required)
3. Company (Custom question)
4. Phone Number (Optional)

NOTA: Facebook auto-rellena First Name si está en perfil

NOMBRE FORM: webinar_clinicas_abril

BOTÓN CTA: "Reservar Plaza"

PRE-FORM TEXT:
"Acceso gratuito al webinar
30 minutos para automatizar tu clínica
Sin código, sin IT"

POST-FORM TEXT:
"¡Fantástico! Te enviaremos el link del webinar
+ la guía Red Flags a tu email en 2 minutos."
```

#### PRIVACY & COMPLIANCE

```
CHECKBOX POST-FORM:
"Sí, acepto recibir emails de Duendes"
(Pre-unchecked - GDPR compliant)

LINK PRIVACIDAD: https://duendes.net/privacidad
LINK TÉRMINOS: https://duendes.net/terminos
```

---

### 4. CREATIVES (3 variaciones)

#### CREATIVE 1: URGENCIA + SOCIAL PROOF

```
AD FORMAT: Single Image

IMAGE:
- Size: 1200 x 628px (landscape)
- Content: Portada PDF "Red Flags" con logo Duendes
- Text on image: "8 Abril | 17:00"
- Color: Amarillo (#fac802) + Gris
- File: NO más de 100KB

HEADLINE (campo de Meta, 27 chars max):
"Automatiza sin perder control"

PRIMARY TEXT (125 chars):
Clínicas como la tuya en España lo hacen.
Red Flags + Checklist GRATIS.
30 min de webinar = ahorrar €3k en malos proveedores

DESCRIPTION:
8 Abril | 100% Online | 30 minutos completos

¿Qué vas a aprender?
✓ Las 20 Red Flags de proveedores IA
✓ Checklist antes de firmar
✓ Cómo no equivocarte en la contratación

Automatiza sin IT:
✓ Buscar cita
✓ Confirmar cita
✓ Cancelar cita
✓ Nombrar servicios

Incluye: Guía Red Flags PDF + Checklist

CTA BUTTON: "Reservar plaza"
```

**Creative ID:** cc_urgencia_socialproof_v1

---

#### CREATIVE 2: FOMO + ESCASEZ

```
AD FORMAT: Single Image OR Video Thumbnail

IMAGE:
- Size: 1200 x 628px
- Background: Gradient (amarillo → gris oscuro)
- Text center: "20 RED FLAGS" (grande, bold)
- Icono: Checkmark rojo
- File: <100KB

HEADLINE (27 chars):
"¿Cuál es tu Red Flag?"

PRIMARY TEXT:
20 señales de alerta que DEBES conocer

Webinar GRATIS: 8 de Abril 17h
Plazas limitadas (máx. 50)

DESCRIPTION:
Óscar Graña revela las 20 Red Flags más comunes
en contratos de automatización.

Ideal para:
- Dueños de clínicas
- Managers sanitarios
- Propietarios sin IT

¿Te apuntas?
(Plazas limitadas: máx 50)

CTA BUTTON: "Apuntarse ahora"
```

**Creative ID:** cc_fomo_escasez_v2

---

#### CREATIVE 3: TRANSFORMATION + PROOF

```
AD FORMAT: Single Image (Before/After split)

IMAGE:
- Size: 1200 x 628px
- Left (Before): Dashboard desordenado, rojo ❌
- Right (After): Dashboard limpio, verde ✓
- Text overlay: "-8h admin | +20% confirmaciones"

HEADLINE (27 chars):
"De 10h de admin a 2h/semana"

PRIMARY TEXT:
Clínica Física & Rehab Barcelona automatizó en 15 días.

Resultado: -8h admin, +20% confirmaciones.

¿Tuya podría ser la próxima?

DESCRIPTION:
Caso real + Guía Red Flags + Checklist

Webinar: 8 de Abril | 17:00 CET

Incluye:
✓ Cómo configurar en 15 minutos
✓ 20 señales de alerta
✓ Checklist pre-firma

CTA BUTTON: "Ver cómo lo hace"
```

**Creative ID:** cc_transformation_proof_v3

---

### 5. CONVERSION TRACKING

```
PIXEL SEGUIMIENTO: Duendes_Conversion_Pixel
(ID: XXXXXXXXX)

EVENTO DE CONVERSIÓN: Lead

PUNTO DE CONVERSIÓN: Cuando usuario completa Meta form

META PIXEL FIRING CHECK:
1. Ir a Meta ADS Manager
2. Eventos → Lead Form Completions
3. Confirmar: (pixel fires on form submit)
```

---

### 6. A/B TESTING MINIMAL

```
CONFIGURACIÓN:
- Control: Creative 1 (Urgencia + Social Proof)
- Variant A: Creative 2 (FOMO)
- Variant B: Creative 3 (Transformation)
- Split: 50%-25%-25%

DURACIÓN: Minimum 3 días antes de pause

MÉTRICAS GANADORAS:
- Si CTR > 2.5% → Keep
- Si CPL < €0.15 → Keep  
- Si Email Open > 40% → Keep (trackear post)
```

---

### 7. BUDGET ALLOCATION

```
PRESUPUESTO TOTAL: €150

DISTRIBUCIÓN RECOMENDADA:
- Days 1-3 (learning phase): €30 (test creatives)
- Days 4-7 (optimize phase): €40 (best performer only)
- Days 8-18 (scale phase): €80 (winning creative 2x spend)

DAILY LIMITS:
- Mini: €5/día (si CPL > €0.20)
- Standard: €10/día (current)
- Max: €15/día (only if CPL < €0.13)

PAUSE RULES:
- Si CPL > €0.30 consecutivos 3 días → PAUSE, optimize copy
- Si leads = 50 → CLOSE ads (full capacity webinar)
```

---

### 8. MONITORING DIARIO (CMO/Growth)

```
DASHBOARD TO CHECK (Meta Ads Manager):

Metadatos por Ad Set:
- Impressions (meta: >300/día)
- Clicks (meta: >5/día)
- CTR (meta: >1.8%)
- Cost per Lead (meta: <€0.15)
- Leads (meta: >10/día)
- Leads Quality (meta: 0 invalid emails)

ALERTS (If triggered → Action):
- CTR < 1.2% Day 2 → Pause Creative 3, double Creative 1
- CPL > €0.25 Day 3 → Reduce age range (40-55), exclude <35
- Email bounce > 3% → Stop ads, check form data quality
- Leads = 50 → CLOSE ads immediately

DAILY ACTION CHECKLIST:
- [ ] Meta Ads Manager: Screenshot metrics
- [ ] Slack: Post screenshot #webinar-clinicas
- [ ] Airtable: Sync OK? New records appearing?
- [ ] Email: Test 1 email delivery (abre? clicks?)
- [ ] Frequency: ¿Gente viendo ad 2+ veces? (OK si <2.5x)
```

---

### 9. TROUBLESHOOTING

#### Problem: CPL too high (>€0.20)

**Quick Fix (Day 2):**
1. Pause Creative 3 (transformation)
2. Double budget allocation to Creative 1
3. Check: ¿Placements incluyen Audience Network? If yes → disable

**Medium Fix (Day 3+):**
1. Narrow age: 40-55 years only
2. Add: "Decision Makers" behavior
3. Exclude: "Healthcare Students"

---

#### Problem: Low CTR (<1.2%)

**Quick Fix:**
1. Check: ¿Form working? Test on mobile
2. Change CTA button color (Meta suggestion)
3. Edit headline (A/B test 2 headlines)

---

#### Problem: High bounce rate (>5%)

**Likely cause:** Form invalid → Check Airtable Zapier sync

1. Test: Submit form manually
2. Check Zapier logs: ¿Errores?
3. Re-authenticate: Airtable token expired?

---

## COPY-PASTE READY INPUTS

### Headline Variaciones (Test in rotation)

```
1. "Automatiza sin perder control"
2. "¿Cuál es tu Red Flag?"
3. "De 10h de admin a 2h/semana"
4. "Sin código. Sin IT. Sin sorpresas."
5. "Clínicas como la tuya lo hacen"
```

### Primary Text Variaciones

```
1. "Clínicas como la tuya en España lo hacen. Red Flags + Checklist GRATIS. 30 min de webinar = ahorrar €3k en malos proveedores"

2. "20 señales de alerta que DEBES conocer. Webinar GRATIS: 8 de Abril 17h. Plazas limitadas (máx. 50)"

3. "Caso real: Clínica Barcelona automatizó en 15 días. Resultado: -8h admin, +20% confirmaciones. ¿Tuya podría ser la próxima?"
```

### Description Variaciones

```
1. "8 Abril | 100% Online | 30 minutos"

2. "Óscar Graña revela las 20 Red Flags más comunes"

3. "Ideal para dueños, managers, propietarios sin IT"
```

---

## SIGUIENTE PASO

Cuando hayas creado todo esto en Meta Ads Manager:

1. **Screenshot** de campaign name + ad sets
2. **Share link** a CMO para final review
3. **Test conversión:** Submit 1 lead → check email delivery
4. **Slack notification** cuando ads vayan live
5. **Add date-time**: "Ads live: 5 Abril 10:00 AM UTC+1"

