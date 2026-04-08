# Configuración Zapier - Meta Lead Form → Airtable → SendGrid Email

**Setup Time:** ~45 minutos  
**Costo:** Free tier Zapier (3 zaps gratis) + SendGrid free  
**Complejidad:** Media (no código)

---

## PREREQUISITOS ANTES DE EMPEZAR

### 1. SendGrid Setup

**Crear cuenta gratis:**
```
https://sendgrid.com/free
- Signup con email duendes
- Verificar dominio: duendes.net
- Generar API Key: https://app.sendgrid.com/settings/api_keys
```

**Verificar dominio (SPF/DKIM):**
```
1. Settings → Sender Authentication
2. Click "Authenticate Your Domain"
3. Seguir wizard (añadir records DNS)
4. Esperar 24h para propagación
5. Status debe mostrar: ✓ Verified (verde)
```

**Crear email template:**
```
Marketing → Email Template → Create Template
- Name: "Confirmacion_Webinar_Clinicas_v1"
- (COPIAR-PEGAR template abajo en "Email Templates")
```

### 2. Airtable Base Setup

**Crear tabla: `Registros_Webinar_Clinicas`**

Fields:
```
1. Name (Single line text) - from Meta form
2. Email (Email) - from Meta form
3. Empresa (Single line text) - from Meta form
4. Telefono (Phone number) - from Meta form
5. Fecha_Registro (Created time) - automático
6. Estado (Single select options:
   - Pendiente_Email
   - Confirmacion_Enviada
   - Email_Abierto
   - Asistencia_Confirmada
   - No_Interesado
   - Clocked_Out
   - Demo_Agendada
7. Fuente_Ad_Set (Single select options:
   - Clinicas_Salud_ES_Intereses
   - Clinicas_Salud_ES_LALs
   - Clinicas_Salud_ES_Retarget
8. Email_Enviado (Checkbox)
9. PDF_Abierto (Checkbox)
10. Asistencia_Confirmada (Single select: Sí/No/Pendiente)
11. Demo_Pagada_Generada (Checkbox)
12. Notas_SDR (Long text)
```

### 3. Calendly Setup

```
https://calendly.com/duendes/webinar-clinicas

Detalles:
- Event name: "Webinar Clinicas Duendes - 8 Abril"
- Date/Time: 8-9 Abril, 17:00 CET (30 min duration)
- Max participants: 50 (add booking limit)
- Auto-confirmation: ON
- Location: Zoom (add meeting link)
- Color: Yellow (#fac802)
```

**Obtener link público:**
```
Calendly dashboard → Copy short link:
https://calendly.com/duendes/webinar-clinicas
```

### 4. Zapier Account Setup

```
https://zapier.com/sign-up

Plan: FREE (3 zaps incluidos)
- Zap 1: Meta → Airtable
- Zap 2: Airtable → SendGrid
- Zap 3: Airtable → Slack
```

---

## ZAP 1: Meta Lead Form → Airtable

### Configuración paso a paso

**1. CREATE ZAP - TRIGGER**

```
1. Click "Create Zap"
2. Search trigger: "Meta Ads"
3. Select app: "Meta Ads"
4. Select event: "New Lead in Lead Form"
5. Click "Continue"
```

**2. AUTHENTICATE META ADS**

```
Click "Sign in with Meta"
- Seleccionar cuenta publicitaria: "Duendes - Clinicas"
- Scope: Lead Form, Ads, Campaigns
- Confirm permissions
```

**3. CONFIGURE TRIGGER**

```
Select Form: "webinar_clinicas_abril"
(dropdown filtra por account)

Click "Continue"
```

**4. TEST TRIGGER**

```
Click "Test trigger"
Zapier intentará traer un lead reciente
(Si no hay, submit manualmente en Meta form)

Resultado esperado:
- Full Name: "Nombre Prueba"
- Email: "test@example.com"
- Company: "Clínica Test"
- Phone: "+34 123 456 789"
```

---

**5. CREATE ACTION - AIRTABLE**

```
1. Click "Connect to an action..."
2. Search: "Airtable"
3. Select app: "Airtable"
4. Select action: "Create Record"
5. Click "Continue"
```

**6. AUTHENTICATE AIRTABLE**

```
Click "Sign in"
- Login con cuenta airtable@duendes.net
- Grant permissions
- Click "Allow"
```

**7. CONFIGURE AIRTABLE ACTION**

```
Base: "AIOS_Duendes" (select from dropdown)
Table: "Registros_Webinar_Clinicas"

FIELD MAPPING (Left = Meta Lead, Right = Airtable Field):

Full Name → Name
Email → Email
Company → Empresa
Phone → Telefono

CUSTOM FIELDS (hardcode):
- Estado → "Pendiente_Email"
- Fuente_Ad_Set → "Clinicas_Salud_ES_Intereses"
- Email_Enviado → FALSE (unchecked)

Click "Continue"
```

**8. TEST ACTION**

```
Click "Test action"
Resultado esperado:
- ✓ Record created in Airtable
- ID: recXXXXXXXXXXXXXX
- All fields populated

Si error: Check token Airtable (may have expired)
```

**9. NAME & TURN ON**

```
Zap Name: "Z1_Meta_Lead → Airtable"
Click "Publish"
Toggle switch: ON
```

---

## ZAP 2: Airtable (Email_Enviado=FALSE) → SendGrid

### Configuración paso a paso

**1. CREATE ZAP - TRIGGER**

```
1. Click "Create Zap"
2. Search: "Airtable"
3. Select event: "New Record in Table"
4. Click "Continue"
```

**2. CONFIGURE TRIGGER**

```
Authenticate: Airtable (already done in Zap1)

Base: "AIOS_Duendes"
Table: "Registros_Webinar_Clinicas"
View: (leave empty = all records)

Click "Continue"
```

**3. TEST TRIGGER**

```
Click "Test trigger"
(Debería mostrar el record que creamos en Zap1)
```

---

**4. CREATE ACTION - SENDGRID**

```
1. Click "Connect to an action..."
2. Search: "SendGrid"
3. Select: "SendGrid"
4. Select action: "Send Marketing Email"
   (O "Send Transactional Email" si prefieres)
5. Click "Continue"
```

**6. AUTHENTICATE SENDGRID**

```
Click "Sign in"
- Paste API Key (from SendGrid dashboard)
- Click "Test connection"
```

**7. CONFIGURE EMAIL ACTION**

```
FROM NAME: "Óscar Graña"
FROM EMAIL: "noreply@duendes.net"
  (Must be verified domain in SendGrid)

TO EMAIL: [Airtable] Email field
TO NAME: [Airtable] Name field

SUBJECT: "⏰ Tu plaza está confirmada - Webinar 8 de Abril {{Name}}"

EMAIL TEMPLATE: "Confirmacion_Webinar_Clinicas_v1"
(Select from dropdown)

DYNAMIC TEMPLATE DATA (pour variables):
```
{
  "name": "{{Name}}",
  "empresa": "{{Empresa}}",
  "link_webinar": "https://calendly.com/duendes/webinar-clinicas",
  "email_address": "{{Email}}"
}
```

REPLY-TO: "hola@duendes.net"

Click "Continue"
```

**8. TEST ACTION**

```
Click "Test action"
Resultado esperado:
- ✓ Email sent to test email
- Aparece en SendGrid Activity → Delivered

Check inbox (might be spam folder initially)
```

**9. ADD SECOND ACTION: UPDATE AIRTABLE**

```
1. Click "+ Add Action"
2. Search: "Airtable"
3. Select action: "Update Record"
4. Base: "AIOS_Duendes"
5. Table: "Registros_Webinar_Clinicas"

RECORD SELECTION:
Record ID: [Airtable] ID field (from Trigger)

FIELDS TO UPDATE:
- Email_Enviado → TRUE (checked)
- Estado → "Confirmacion_Enviada"

Click "Continue" → "Test" → "Continue"
```

**10. NAME & PUBLISH**

```
Zap Name: "Z2_Airtable → SendGrid Email"
Click "Publish"
Toggle: ON
```

---

## ZAP 3: Airtable → Slack Notification (Optional pero recomendado)

### Configuración paso a paso

**1. CREATE ZAP - TRIGGER**

```
1. Click "Create Zap"
2. Trigger: "Airtable"
3. Event: "New Record"
4. Base: "AIOS_Duendes"
5. Table: "Registros_Webinar_Clinicas"
```

**2. CREATE ACTION - SLACK**

```
1. Click "Connect to an action..."
2. Select: "Slack"
3. Select action: "Send Channel Message"
4. Click "Continue"
```

**3. AUTHENTICATE SLACK**

```
Click "Sign in"
- Select workspace: "Duendes"
- Authorize app
```

**4. CONFIGURE SLACK MESSAGE**

```
CHANNEL: #webinar-clinicas

MESSAGE:
🎉 NUEVO REGISTRO: {{Name}}
📧 {{Email}}
🏥 {{Empresa}}
📱 {{Telefono}}
Estado: {{Estado}}

¡Acción requerida si email no abre en 24h!
→ [Ver en Airtable](https://airtable.com/appXXX/tblXXX)
```

**5. TEST & PUBLISH**

```
Click "Test action"
Verify: Message appears in Slack #webinar-clinicas

Zap Name: "Z3_Airtable → Slack Notification"
Click "Publish" + Toggle ON
```

---

## EMAIL TEMPLATES (SendGrid)

### Template 1: Confirmación Webinar

```html
<!-- Email Body (SendGrid Dynamic Template) -->

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background-color: #fac802; padding: 20px; text-align: center; }
    .header h1 { color: white; margin: 0; }
    .content { background-color: #f9f9f9; padding: 20px; margin: 20px 0; }
    .cta-button { background-color: #fac802; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; }
    .footer { background-color: #333; color: white; padding: 15px; text-align: center; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>✅ Tu plaza está confirmada</h1>
    </div>

    <div class="content">
      <p>Hola {{name}},</p>
      
      <p><strong>¡Confirmado! 🎉</strong> Tu plaza está reservada para el webinar:</p>

      <h2>Detalles del Webinar</h2>
      <ul>
        <li><strong>📅 Fecha:</strong> 8 de Abril de 2026</li>
        <li><strong>⏱️ Hora:</strong> 17:00 CET (30 minutos)</li>
        <li><strong>📍 Formato:</strong> Online (enlace en calendario abajo)</li>
        <li><strong>Empresa:</strong> {{empresa}}</li>
      </ul>

      <h2>¿QUÉ VAS A APRENDER?</h2>
      <ul>
        <li>→ Las 20 Red Flags de proveedores IA</li>
        <li>→ Cómo no equivocarte en la contratación</li>
        <li>→ Checklist antes de firmar</li>
      </ul>

      <p style="text-align: center; margin: 30px 0;">
        <a href="https://calendly.com/duendes/webinar-clinicas" class="cta-button">
          Acceder al Webinar
        </a>
      </p>

      <h2>BONUS: Guía Red Flags PDF</h2>
      <p>Adjunto encontrarás la guía completa "Red Flags - Clinicas"</p>

      <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

      <p><strong>¿Dudas?</strong></p>
      <p>Puedes responder a este email o contactar directamente:</p>
      <ul>
        <li>📧 Email: hola@duendes.net</li>
        <li>📞 WhatsApp: +34 607 XXX XXX</li>
      </ul>

      <p>¡Te vemos el 8 de Abril! 🚀</p>
      <p><strong>Óscar Graña</strong><br>Fundador, Duendes</p>
    </div>

    <div class="footer">
      <p>Duendes - Agentes de Voz IA para Clínicas</p>
      <p><a href="https://duendes.net" style="color: white;">www.duendes.net</a></p>
      <p style="margin-top: 20px; font-size: 10px;">
        <a href="https://duendes.net/unsubscribe?email={{email_address}}" style="color: #ccc;">Desuscribirse</a>
      </p>
    </div>
  </div>
</body>
</html>
```

---

## PRUEBA COMPLETA DEL FLUJO

### Test Script (30 minutos)

```
1. Meta Lead Form submission:
   - Submit fake lead vía Meta ads dashboard
   - Name: "Ana García Test"
   - Email: test+airtable@gmail.com
   - Empresa: "Clínica Física Test"
   - Telefono: "+34 123 456 789"

2. Verificar Airtable (wait 60s):
   - Check table: "Registros_Webinar_Clinicas"
   - Nueva row debería aparecer
   - Estado: "Pendiente_Email"
   - Email_Enviado: FALSE

3. Verificar Zapier (wait 30s):
   - Zap history: "Z1_Meta_Lead → Airtable"
   - Status: ✓ SUCCESS
   - Click record para ver mappings

4. Verificar SendGrid (wait 60s):
   - SendGrid Activity → Type: "sent"
   - Email: test+airtable@gmail.com
   - Subject: "⏰ Tu plaza está confirmada..."

5. Check Test Email:
   - Inbox (or spam): Buscar email de noreply@duendes.net
   - Click "Acceder al Webinar" → debe ir a Calendly
   - Descarga PDF adjunto

6. Verificar Slack:
   - Channel #webinar-clinicas
   - Mensaje automático:
     🎉 NUEVO REGISTRO: Ana García Test
     (con datos)

7. Verificar Airtable se actualizó:
   - Email_Enviado: TRUE (checked)
   - Estado: "Confirmacion_Enviada"
```

### Si algo falla:

```
ERROR: Airtable no recibe datos
FIX: 
- Check Zapier token (Settings → Connected Accounts)
- Verify table name exacto (case-sensitive)
- Reauth Airtable en Zapier

ERROR: Email no llega
FIX:
- Check SendGrid domain verification (must be ✓ Verified)
- SendGrid Activity → buscar bounce/dropped
- Check spam folder
- Verify sender email authenticated en SendGrid

ERROR: Zapier zap no triggers
FIX:
- Check Zapier app status (Settings → Recent account checks)
- Re-test trigger manualmente
- Check error logs en history
```

---

## MONITORING POST-LAUNCH

### Daily Checklist (CMO / COO)

```
CADA MAÑANA:
- [ ] Zapier Dashboard: ¿Todos "On"?
- [ ] Zapier History: ¿Errors en últimas 24h?
- [ ] Airtable: ¿Nuevos registros? (Check "Fecha_Registro" en tabla)
- [ ] SendGrid Activity: ¿Emails delivered? ¿Bounces?
- [ ] Slack #webinar-clinicas: ¿Mensajes entrando?

ROJO ALERT (requiere acción inmediata):
- ❌ Zapier zap parado (Off)
- ❌ SendGrid: Domain verification failed
- ❌ Airtable: Token expired (histórico: Auth error)
- ❌ SendGrid: Email bouncing >3%
```

### Weekly Reports (Share with team)

```
SPREADSHEET TEMPLATE:
Week of: [date]

Metrics:
- Total Leads: X
- Emails Delivered: X
- Email Open Rate: X%
- Calendly Clicks: X
- Asistencia Confirmada: X

Issues Resolved:
- [Issue 1]
- [Issue 2]

Next Week Actions:
- [Action]
```

---

## COSTO TOTAL SETUP

| Herramienta | Plan | Costo/mes |
|-------------|------|-----------|
| Zapier | Free (3 zaps) | $0 |
| SendGrid | Free (100k emails) | $0 |
| Airtable | Pro | $15+ |
| Calendly | Pro | $15+ |
| **TOTAL** | | **~$30** |

(Asumiendo Airtable + Calendly ya contratados)

