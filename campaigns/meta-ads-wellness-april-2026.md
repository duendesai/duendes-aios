# Meta Ads Campaign — Wellness Professionals (Simple Health Services)
**Fecha:** 30 de marzo - 8 de abril, 2026
**Budget:** €100
**Objetivo:** Generar leads para webinar del 8 de abril

---

## Copy Template (Reutilizable para todos los sectores)

### Título del anuncio
```
IA Real: Cómo automatizar tu empresa sin gastar una fortuna
```

### Descripción
```
En 8 días descubrirás cómo masajistas, fisioterapeutas y otros profesionales de salud están automatizando su recepción, citas y recordatorios con IA.

Sin inversión en "bots caros". Sin perder el toque personal.

Acceso gratuito al webinar del 8 de abril a las 19:00.
```

### CTA primario
```
Registrarme al webinar gratis
```

### Landing page (post-form)
```
https://duendes.net/webinar/confirmacion
```

---

## Segmentación de Audiencia

### Tabla de Intereses por Sector

| Sector | Edad | Intereses principales | Intereses secundarios | Excluir |
|--------|------|----------------------|----------------------|---------|
| **Masaje/Bienestar** | 30-55 | Wellness, Natural Health, Massage Therapy, Small Business Owners | Entrepreneurship, Digital Marketing | Complex Medical |
| **Fisioterapia** | 30-55 | Physiotherapy, Physical Therapy, Health & Fitness | Sports, Wellness | Complex Medical |
| **Quiropráctica** | 30-55 | Chiropractic, Pain Management, Holistic Health | Wellness, Alternative Medicine | Complex Medical |
| **Kinesiología** | 30-55 | Sports Science, Health & Fitness, Rehabilitation | Wellness, Movement | Complex Medical |
| **Osteopatía** | 30-55 | Osteopathy, Manual Therapy, Holistic Health | Wellness, Natural Health | Complex Medical |
| **Reiki/Energía** | 30-55 | Reiki, Energy Healing, Meditation, Wellness | Spirituality, Personal Development | Complex Medical |

### Exclusiones OBLIGATORIAS
- Psicólogos / Psiquiatras
- Médicos / Especialistas
- Clínicas dentales
- Hospitales
- Farmacias
- Seguros de salud
- Cualquier perfil "complex medical"

---

## Creatives (3 variantes)

### Creative 1: Urgencia + Prueba Social
**Headline:** `Masajistas y fisioterapeutas que automatizan YA`
**Body:** `8 de abril. 8 profesionales en vivo. 0€ de inversión. Solo 2 horas.`
**Visual:** Collage de 3-4 masajistas/fisioterapeutas al trabajo + logo Duendes
**CTA:** Registrarme

### Creative 2: FOMO + Transformación
**Headline:** `De 50 citas manuales a 0 administrativos`
**Body:** `Sin bots caros. Sin chatbots que asustan. Solo tu voz, tu IA, tu empresa.`
**Visual:** Before/After: masajista estresado | masajista relajado con teléfono
**CTA:** Ver cómo funciona

### Creative 3: Resultado Específico
**Headline:** `¿Gastas 2 horas/día en admin?`
**Body:** `Descubre cómo otros lo automatizaron en 30 minutos. Webinar 8 de abril.`
**Visual:** Teléfono con calendario, notificaciones de citas automáticas
**CTA:** Quiero verlo en vivo

---

## Configuración de Meta (Instant Forms)

### Campos del formulario
```
1. Nombre (Requerido)
2. Email (Requerido)
3. Teléfono (Requerido)
4. Tipo de negocio (Dropdown):
   - Masaje / Wellness
   - Fisioterapia
   - Quiropráctica
   - Kinesiología
   - Osteopatía
   - Reiki / Energía
5. ¿Cuántas citas/día haces? (Dropdown):
   - 1-5
   - 6-10
   - 11-20
   - 20+
```

### Configuración post-form
- **Página de confirmación:** https://duendes.net/webinar/confirmacion
- **Mensaje de confirmación (instant form):** "Perfecto. Acceso + recordatorio te llegan por email en 5 minutos."
- **Video de bienvenida:** Vimeo embed (NEXT_PUBLIC_WEBINAR_WELCOME_VIDEO_EMBED_URL)

---

## Budget y Scheduling

### Distribución diaria
```
Presupuesto total: €100
Días: 10 (30 mar - 8 abr)
Presupuesto diario: €10/día
```

### Horario de lanzamiento
- **Tiempo:** 24/7 (sin restricciones horarias)
- **Justificación:** Negocios pequeños revisan el móvil fuera de horario. Los masajistas/fisioterapeutas suelen buscar herramientas por la noche.

---

## KPIs y Umbrales de Alerta

### Métricas objetivo
| Métrica | Objetivo | Alerta |
|---------|----------|--------|
| **CPL (Costo por Lead)** | €0.10-0.12 | >€0.15 → pausar |
| **CTR (Click-Through Rate)** | 2.5%+ | <1.5% → cambiar creative |
| **CPC (Costo por Click)** | €0.08-0.10 | >€0.12 → ajustar targeting |
| **Conversion Rate (form)** | 25%+ | <15% → revisar form |
| **Impressions/día** | 1.5k-2k | <500 → aumentar budget |

### Revisión diaria (9:00 AM CET)
1. Check impresiones, clicks, leads
2. Si CPL >€0.15: pausar audience más cara
3. Si CTR <1.5%: probar siguiente creative
4. Si conversión <15%: revisar carga de form

---

## Integración con n8n

### Workflow automático (crear en n8n)
1. **Trigger:** Lead entra en Meta Instant Form
2. **Acción:** Guardar en Airtable (base de webinar)
3. **Acción:** Enviar email de bienvenida automático
4. **Acción:** Crear recordatorio para 1 día antes del webinar
5. **Acción:** Log de conversión en Airtable

---

## Checklist de lanzamiento

- [ ] Creatives: Subidas a Media Library de Meta
- [ ] Audiencia: Configurada en Meta Ads Manager
- [ ] Instant Form: Activo con campos correctos
- [ ] Página de confirmación: Verificada en producción
- [ ] Vimeo embed: Testado en confirmación
- [ ] n8n workflow: Importado y activo
- [ ] Airtable: Base de webinar lista para recibir leads
- [ ] Email automático: Configurado en n8n
- [ ] Budget: €100 asignado a la campaña
- [ ] Schedule: 30 mar - 8 abr

---

## Nota
Este copy es 100% reutilizable para otros sectores en futuros webinars. Solo cambia la **fecha del webinar** (actualmente: 8 de abril) y adapta los **ejemplos de profesionales** en copy y visuals.
