# Próximos pasos — Campaña Wellness (Después del lanzamiento)

**Estado:** Formulario configurado, workflow n8n listo, falta integración final

---

## ✅ Lo que ya está hecho

1. **Spec de campaña:** `campaigns/meta-ads-wellness-april-2026.md`
2. **Workflow n8n:** `workflows/n8n-webinar-lead-automation-UPDATED.json`
3. **Guía de lanzamiento:** `CAMPAIGN-LAUNCH.md`
4. **PDF RED FLAGS:** Guardado en `campaigns/RED FLAGS - duendes.pdf`

---

## 🔧 Pasos finales (hacerlos EN ESTE ORDEN)

### Paso 1: Hostear el PDF (15 min)
El PDF debe estar en una URL pública para que n8n lo descargue y lo adjunte.

**Opción A — Subir a Duendes.net (recomendado):**
```bash
scp /Users/oscargrana/duendes-aios/campaigns/'RED FLAGS - duendes.pdf' \
    usuario@duendes.net:/var/www/duendes.net/public/downloads/
```
Luego la URL será: `https://duendes.net/downloads/RED FLAGS - duendes.pdf`

**Opción B — Usar Google Drive:**
1. Sube el PDF a Google Drive
2. Comparte con "Acceso público"
3. Copia el link
4. Actualiza el workflow n8n con esa URL

**Una vez tengas la URL, edita el workflow n8n** (línea del attachment) y reemplaza:
```
"data": "file:///Users/oscargrana/duendes-aios/campaigns/RED FLAGS - duendes.pdf"
```
Por:
```
"data": "https://duendes.net/downloads/RED FLAGS - duendes.pdf"
```

---

### Paso 2: Configurar n8n Webhook (10 min)

1. Ve a **n8n.duendes.net**
2. Importa el workflow: `n8n-webinar-lead-automation-UPDATED.json`
3. Configura credenciales:
   - **Airtable:** Token + Base ID (ya tienes en `.claude/settings.local.json`)
   - **SendGrid:** API Key (necesitas obtenerla si no la tienes)

4. **CRÍTICO:** Copia el webhook URL que genera n8n:
   ```
   https://n8n.duendes.net/webhook/webinar-lead
   ```

5. Activa el workflow

---

### Paso 3: Conectar Meta a n8n Webhook (10 min)

Después de que publiques la campaña en Meta:

1. Ve a **Meta Ads Manager**
2. En tu campaña, ve a **Instant Form Settings**
3. Busca **Webhooks**
4. Click **+ Add Webhook**
5. Pega la URL del webhook de n8n:
   ```
   https://n8n.duendes.net/webhook/webinar-lead
   ```
6. **Test Webhook** (click en probar)
7. Si sale verde ✅ → Listo

---

### Paso 4: Verificar Airtable (5 min)

1. Abre tu tabla en Airtable
2. Verifica que existen estos campos:
   - ✅ Nombre
   - ✅ Email
   - ✅ Teléfono
   - ✅ Empresa
   - ✅ Fuente
   - ✅ Sector
   - ✅ Estado
   - ✅ Próximo seguimiento

Si falta alguno, créalo en Airtable (Type: Text, Email, Phone, etc.)

---

### Paso 5: Test Completo (15 min)

1. **Desde tu móvil**, abre Meta (Facebook o Instagram)
2. Busca tu anuncio
3. Rellena el formulario **CON DATOS REALES TUYOS**
4. Verifica:
   - [ ] Recibes email de bienvenida
   - [ ] Email tiene el PDF adjunto
   - [ ] Puedes ver el PDF
   - [ ] Un lead aparece en Airtable
   - [ ] El lead tiene `Fuente: webinar` y `Estado: Nuevo`

Si algo falla → revisa los logs de n8n para errores

---

## 📋 Checklist de lanzamiento FINAL

- [ ] Campaña en Meta: ACTIVA
- [ ] Presupuesto: €100, 30 mar - 8 abr
- [ ] Instant Form: Creado con campos correctos
- [ ] Descripción de privacidad: Rellenada en Meta
- [ ] Página de agradecimiento: Con texto correcto
- [ ] PDF: Alojado en URL pública
- [ ] n8n: Workflow importado y activo
- [ ] n8n: Credenciales configuradas (Airtable + SendGrid)
- [ ] Webhook: Conectado Meta → n8n
- [ ] Airtable: Tabla con campos correctos
- [ ] Test completo: Lead enviado y verificado

---

## 🎯 Métricas a monitorear (diario, 9 AM)

| Métrica | Objetivo | Acción si falla |
|---------|----------|-----------------|
| **Impresiones** | 1.5k-2k/día | Si <500 = aumentar budget |
| **Clicks** | 30-50/día | Si <15 = cambiar creative |
| **Leads capturados** | 8-10/día | Si <5 = revisar formulario |
| **CPL** | €0.10-0.12 | Si >€0.15 = pausar |
| **Email recibidos** | 100% of leads | Si <90% = revisar SendGrid |

---

## 🚨 Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| Lead no aparece en Airtable | Webhook desconectado | Verificar URL webhook en Meta |
| Email no llega | SendGrid misconfigured | Verificar API key + SPF/DKIM |
| Email sin PDF | URL del PDF inaccesible | Verificar que PDF está online y URL es correcta |
| CPL muy alto (>€0.15) | Audiencia demasiado amplia | Reducir edad a 35-50, remover intereses genéricos |
| No hay impresiones | Budget consumido | Aumentar budget o revisar placements |

---

## Próximas acciones después del webinar (8 de abril)

1. Enviar grabación a leads que no asistieron
2. Análisis de conversión: leads → asistentes → contratados
3. A/B test: diferentes copy para próximos webinars
4. Escalado: Si CPL <€0.10, aumentar a €200/semana

---

**Tiempo total para lanzamiento:** ~50 minutos
**Tiempo para estar 100% automático:** ~2 horas

Cualquier duda, revisa los logs de n8n (muestra exactamente dónde falló).
