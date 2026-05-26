# Posicionamiento de Duendes — Vigente 2026-05-25

> **Este documento es la fuente de verdad** sobre el modelo de negocio, cliente target y oferta de Duendes.
> Sustituye a las definiciones que aparecen en `context/negocio.md`, `context/ofertas.md` y `context/clientes-ideales.md`, que se mantienen como histórico y como knowledge interno pero no reflejan la propuesta actual al mercado.

---

## 1. Qué es Duendes ahora

Duendes es una **consultora de implantación de IA para PYMEs medianas españolas**.

Diagnostica el negocio del cliente, identifica qué procesos puede absorber la IA y los implementa en la infraestructura del propio cliente con presupuesto cerrado. Mantiene el sistema si el cliente lo quiere, sin ataduras.

Lo que **NO** es:
- No es una agencia de agentes de voz IA. El agente de voz es una de las soluciones del catálogo, no la propuesta.
- No es una plataforma SaaS con planes públicos.
- No es una agencia de marketing digital con IA.
- No es una formación ni un curso.

---

## 2. Cliente objetivo

Empresario o titular de PYME mediana española, 4-30 empleados, 35-55 años.

Sectores en orden de prioridad para Fase 0:
1. **Despachos profesionales** (abogados, gestorías, asesorías) — recomendado como vertical único para los primeros 3 meses. Pendiente confirmación de Oscar.
2. Clínicas (dentales, fisioterapia, estética)
3. Oficios y servicios técnicos
4. Comercio y e-commerce

Características del cliente:
- Ha construido su negocio con años de esfuerzo.
- Ha visto pasar modas y ha pagado a proveedores que no entregaron.
- Sabe que necesita IA pero no sabe cuál ni por dónde empezar.
- Tiene tiempo limitado y responsabilidad sobre empleados.
- Decide solo o con socio (sin comités).
- Detecta el humo con rapidez.
- Valora la palabra dada por encima del contrato firmado.

Lo que **NO** es cliente:
- Autónomos de 1-5 empleados con budget de 100-300€/mes (ese era el cliente del modelo de producto agente de voz, no del nuevo modelo).
- Grandes empresas con departamento de IT propio.
- Startups que quieren producto self-service.

---

## 3. Modelo de oferta

```
1. CONSULTA INICIAL (gratuita, sin compromiso)
   30 minutos en videollamada
   Sin entregable, solo conversación
   Objetivo: identificar oportunidades y decidir si tiene sentido un diagnóstico

2. DIAGNÓSTICO (pago, presupuesto cerrado)
   Análisis profundo del negocio
   Entregable: informe escrito con plan priorizado por impacto
   El informe es propiedad del cliente
   Palanca de cierre: 100% del coste se descuenta si contrata implementación en 15 días

3. IMPLEMENTACIÓN (precio cerrado)
   Construcción del sistema en infraestructura del cliente
   Con sus credenciales, sus cuentas, su software
   Entregables: código, configuración, documentación, PDF de onboarding
   Dos modalidades de pago:
   - Pago único: sin permanencia
   - A plazos: 12 meses obligatorios
   El sistema es propiedad del cliente desde el día uno

4. ACOMPAÑAMIENTO MENSUAL (OPCIONAL, sin permanencia)
   Monitorización, actualizaciones, soporte, ajustes mensuales
   Baja libre con preaviso de 30 días
   Sin él, el sistema sigue funcionando pero sin SLA ni actualizaciones automáticas
   Excepción: si la implementación incluye servicios en infraestructura propia de Duendes
   (ejemplo: agentes de voz vía servidores Duendes), esa parte sí requiere cuota.

5. FORMACIÓN PRESENCIAL O REMOTA (OPCIONAL, upsell)
   Sesiones de formación para empleados del cliente
```

---

## 4. Rampa de precios

Rangos orientativos por fase de madurez. Los precios concretos se confirman tras la consulta inicial.

| Producto | Fase 0 (mes 1-3, sin casos) | Fase 1 (mes 4-9) | Fase 2 (mes 10+) |
|---|---|---|---|
| Consulta inicial | Gratis | Gratis | Gratis |
| Diagnóstico | 800-1.500€ | 1.500-2.500€ | 2.500-4.500€ |
| Implementación | 4.000-8.000€ | 8.000-15.000€ | 15.000-30.000€ |
| Cuota mensual | 400-700€ | 700-1.200€ | 1.200-2.500€ |
| Formación adicional | 500-1.000€/sesión | 800-1.500€/sesión | 1.500-3.000€/sesión |

Disclaimer: rangos estimados basados en mercado B2B español de consultoría tecnológica. Ajustar tras las primeras 10-15 conversaciones reales con prospectos.

**Precios nunca son públicos en la web durante Fase 0-1.** Se dan en propuesta cerrada tras la consulta.

---

## 5. Propiedad del sistema

Punto crítico que diferencia a Duendes de proveedores SaaS:

- El sistema implementado vive en **infraestructura del cliente**.
- Las APIs externas (OpenAI, Anthropic, etc.) las paga el cliente directamente con sus cuentas.
- El cliente recibe código, configuración y documentación completa.
- Si el cliente deja de pagar la cuota mensual, el sistema sigue funcionando.
- La cuota mensual es seguro de mantenimiento y evolución, no llave de encendido.

Excepción: cuando la implementación incluye servicios alojados en infraestructura propia de Duendes (típicamente agentes de voz que pasan por servidores Duendes), esa parte específica requiere la cuota para funcionar. Debe comunicarse explícitamente en la propuesta.

---

## 6. El agente de voz dentro del nuevo modelo

El producto "agente de voz IA" sigue siendo un activo importante de Duendes:
- Tecnología construida y operativa (ver `voice-agent/`).
- Knowledge bases sectoriales completos (ver `voice-agent/LUC.IA/`).
- Lucía como agente interno de prospección (ver `cold-outreach/`).

Cómo encaja en el nuevo posicionamiento:
- Es **una de las soluciones del catálogo**, no la propuesta principal.
- Se ofrece cuando el diagnóstico identifica el dolor de llamadas perdidas como prioritario.
- Los planes públicos (79€/129€/229€) descritos en `context/ofertas.md` corresponden al modelo de producto anterior y **no están vigentes en la web pública** (la web nueva no muestra precios).
- Los KBs siguen siendo válidos como recurso interno para implantar agentes de voz cuando aplica.

---

## 7. Tono y comunicación

**En la comunicación de Oscar con el AIOS (mi prosa con él):**
- Castellano funcional, neutro, profesional.
- Sin expresiones idiomáticas ni costumbristas ("manos al timón", "la madre del cordero", "no te vendo humo", "le damos una vuelta" en mi voz).
- Sin folklore. Sin frases hechas. Sin chistes ni guiños performativos.
- Las expresiones idiomáticas son territorio de Oscar, no mío.

**En el copy público de Duendes (web, outreach, propuestas):**
- Castellano peninsular pragmático.
- Primera persona del plural inclusivo cuando aplique ("tomemos", "hagamos", "podemos juntos").
- Muletillas peninsulares naturales permitidas ("mira", "fíjate", "te cuento rápido", "a ver"). Ver `voice-agent/LUC.IA/kb_brand_voice_duendes.md` para inventario completo.
- Cero anglicismos disfrazados ("transformar", "escalar", "optimizar", "potenciar", "revolucionar", "disruptivo").
- Cero urgencia falsa ("últimas plazas", "actúa ahora", "oferta limitada").
- Cero prueba social como manada ("1000 empresas ya...").
- Tono de empresario español hablando a otro empresario, no de coach motivacional.

**En todos los casos:**
- No hablamos del fundador en primera persona en la comunicación pública.
- No hay marca personal de Oscar (LinkedIn personal, YouTube, podcast). Decisión cerrada.
- La autoridad se construye con casos, contenido institucional y partnerships, no con exposición personal del fundador.

---

## 8. Estado del proyecto y próximos pasos

**Hecho (2026-05-25):**
- Web rediseñada y publicada en duendes.net con el nuevo posicionamiento.
- Blog eliminado con redirects 301.
- Bio del fundador fuera de la home.
- Customer journey estilo Morningside adaptado al castellano.

**Pendiente de decisión de Oscar:**
- Confirmar vertical único de Fase 0 (recomendación: despachos/gestorías).
- Confirmar ciudad/zona geográfica para empezar el outreach.
- Decidir qué hacer con páginas `/clinica`, `/oficina`, `/servicios`, `/comercio` (siguen con copy del modelo viejo).
- Decidir qué hacer con `/pricing` (precios del modelo viejo, sin enlace público pero URL accesible).
- Decidir qué hacer con `/webinar` y `/webinar/confirmacion` (webinar obsoleto de abril 2026).

**Pendiente de ejecución cuando Oscar dé GO:**
- Reescritura de la landing del vertical de Fase 0 con copy afilado.
- Script de cold calling diagnóstico para SDR.
- Informe sectorial gratuito como lead magnet del outreach.
- Plantilla de propuesta cerrada para implementación.
- Cláusula legal de propiedad del diagnóstico.

**Tarea de seguridad pendiente (no bloquea nada):**
- Rotar el GitHub Personal Access Token expuesto en `.git/config` del repo duendes-web.

---

## 9. Documentos relacionados (referencia rápida)

| Archivo | Estado | Comentario |
|---|---|---|
| `context/posicionamiento.md` | **VIGENTE** | Este documento. Fuente de verdad. |
| `context/negocio.md` | LEGADO | Describe el modelo de producto agente de voz. Útil como referencia histórica. |
| `context/clientes-ideales.md` | LEGADO | Describe cliente del modelo anterior (1-5 empleados, 200-500€/mes). |
| `context/ofertas.md` | LEGADO | Describe planes 79€/129€/229€ del modelo anterior. |
| `context/voz-tono.md` | VIGENTE | Sigue siendo válido en lo esencial. Complementar con la sección 7 de este documento. |
| `context/estrategia.md` | EN REVISIÓN | Estrategia de marzo 2026 enfocada al modelo anterior. Actualizar tras confirmar vertical Fase 0. |
| `context/competencia.md` | DESACTUALIZADO | Análisis basado en modelo anterior. Reescribir tras Fase 0. |
| `voice-agent/` | VÁLIDO | Knowledge interno y solución de catálogo. No es la propuesta principal. |
| `voice-agent/LUC.IA/kb_brand_voice_duendes.md` | VÁLIDO | Brand voice peninsular sigue siendo referencia. |
| `cold-outreach/` | VÁLIDO | Herramienta de prospección. |
| `duendes-web/` | VIGENTE | Web nueva publicada 2026-05-25. Rama backup: `pre-rebrand-2026-05-25`. |

---

## 10. Cómo trabajar con esto en futuras sesiones

Cuando una nueva sesión del AIOS arranque:

1. Leer `CLAUDE.md` raíz del proyecto.
2. Leer este documento (`context/posicionamiento.md`) ANTES que cualquier otro archivo de contexto.
3. Tratar `context/negocio.md`, `context/clientes-ideales.md` y `context/ofertas.md` como histórico (no como instrucciones operativas vigentes).
4. Consultar memoria Engram con `project: "duendes-aios"` para recuperar decisiones recientes.
5. Cuando se actualice este documento, marcar la fecha en el encabezado.

**Si Oscar pide cambios de posicionamiento estratégico**, actualizar primero este documento y luego cascada a los módulos afectados.
