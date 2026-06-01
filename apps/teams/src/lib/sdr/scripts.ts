/**
 * Scripts SDR de referencia, por campaña. Visibles en el panel derecho de /sdr.
 * El dialer muestra el guion de la campaña activa (selector de campañas).
 */

export interface ScriptSection {
  id: string
  title: string
  body: string
}

// ─── Fisios / genérico (campaña fisios-malaga) ──────────────────────────────
const FISIOS_SCRIPT: ScriptSection[] = [
  {
    id: 'apertura',
    title: 'Apertura (≤8 segundos)',
    body: `Hola, soy Oscar de Duendes — agencia de inteligencia artificial.
¿Hablo con el responsable?

✔ Filtra decisor vs gatekeeper antes que nada.
✔ NO hagas pitch en el primer turno.
✔ Si dice "¿de qué se trata?", contesta: "Es algo concreto que quiero comentarle al responsable. ¿Está disponible?"`,
  },
  {
    id: 'gatekeeper',
    title: 'Si gatekeeper (máx 4 turnos)',
    body: `1. Pedir horario del decisor + nombre.
2. "¿A qué hora suele estar disponible?"
3. Si no da paso: "Voy a probar más tarde, ¿quedamos en que llamo a las X?"
4. Registrar como "Rellamar" con la fecha sugerida.

NO insistir. NO pitch al gatekeeper. NO discutir.`,
  },
  {
    id: 'discovery',
    title: 'Discovery (≤90 segundos)',
    body: `Tras presentación, pide permiso: "¿Tienes 30 segundos para que te cuente por qué te llamo?"

Preguntas socráticas (según sector):
• Clínicas: "¿Cuántas llamadas perdéis al mes cuando estáis con un paciente?"
• Despachos: "¿Quién atiende cuando estás en juicio o reunión?"
• Talleres/oficios: "¿Pierdes encargos cuando tienes las manos sucias?"

Escucha el dolor verbatim. NO interrumpas.`,
  },
  {
    id: 'cierre',
    title: 'Cierre — agendar demo (señal de compra)',
    body: `Cuando hay señal real:

"Lo que te propongo es una llamada de 30 minutos con un agente nuestro: te montamos un demo personalizado para tu clínica/despacho/taller. ¿Te va bien el [día/hora]?"

→ Mira slots disponibles → propón dos huecos concretos.
→ Pide nombre completo + email + móvil de respaldo.
→ Repite email letra por letra: "alvaro punto garcia arroba clinica punto es".
→ Confirma "¿correcto?" antes de marcar Agendada.`,
  },
  {
    id: 'objeciones',
    title: 'Objeciones comunes',
    body: `🟡 "Mándame un email"
→ "Sin problema. ¿Me das tu email para mandarte un resumen?" Captura + despedida corta. NO reactivar pitch.

🟡 "Suena caro"
→ NO digas precio. "Cada agente se ajusta a tu volumen. Por eso te propongo la llamada de 15 minutos: vemos tu caso y te digo si tiene sentido para ti."

🟡 "¿Es legal? ¿De dónde sacáis mi número?"
→ "Es una llamada B2B comercial entre empresas, totalmente conforme a la LSSI. Si prefieres no recibir más, te paso a la lista interna ahora mismo." Si insiste → "No llamar" + Estado.

🟡 "Ya tenemos algo parecido"
→ "Perfecto, ¿qué uso le dais?" Escuchar. NO criticar al competidor.

🟡 "Esto es un robot, ¿verdad?"
→ "No, soy Oscar de Duendes, te llamo yo personalmente." (sonríe — se nota).`,
  },
  {
    id: 'precio',
    title: 'Precio (si pregunta directa)',
    body: `Piso a mencionar: "desde 79 euros al mes".

NO entrar en detalle de planes por teléfono. "Depende del volumen de llamadas y de los servicios que integremos. Por eso queremos hacer la demo: vemos tu caso real y te pasamos propuesta concreta después."`,
  },
  {
    id: 'cualificacion',
    title: 'Filtros rápidos de ICP',
    body: `✔ Tiene página web propia con teléfono visible
✔ Tamaño 1-5 personas (no grandes cadenas)
✔ Sector: clínica, despacho, taller, oficio, comercio pequeño
✔ Recibe llamadas como canal de captación
✔ Aún no automatiza recepción (o lo intentó mal)

Si NO encaja → No cualifica + motivo. Sin perder tiempo.`,
  },
]

// ─── Despachos de abogados (campaña despachos-madrid) ───────────────────────
// Fuente: modulos/sdr/templates/speech-cold-call-abogados.md
// Objetivo único: cerrar consulta inicial gratuita de 30 min por videollamada.
// Trato de USTED. No se venden precios ni diagnóstico por teléfono.
const DESPACHOS_SCRIPT: ScriptSection[] = [
  {
    id: 'mentalidad',
    title: 'Mentalidad (antes de marcar)',
    body: `No llamas a pedir una cita. Llamas porque has visto un problema que se repite en despachos como el suyo y quieres comprobar si también está aquí. Si está, hay conversación. Si no, no hay nada que vender y se dice con tranquilidad. No ruegas. No persigues. Diagnosticas.

Trato de USTED siempre.

Ten a la vista (2 min): nombre del socio director, especialidad del despacho, tamaño aproximado y de dónde sacaste el teléfono. No improvises el nombre.`,
  },
  {
    id: 'gatekeeper',
    title: 'Gatekeeper (recepción) · 20-30s',
    body: `"Buenos días. ¿Me pasa con el señor [apellido], por favor? Le llamo de Duendes, es sobre un tema de eficiencia operativa en el despacho. Soy Oscar Grana."

Si "¿de qué se trata?":
"Trabajo con despachos de abogados localizando tareas que les comen tiempo al equipo sin necesitar criterio jurídico. Quiero comentarle al señor [apellido] si lo que veo en despachos de su tamaño le pasa a ustedes o no. Dos minutos."

Si "está reunido / no está":
"Sin problema. ¿Cuándo suele ser buen momento para localizarle? Prefiero no dejar recado, es una conversación corta."`,
  },
  {
    id: 'apertura',
    title: 'Apertura con el decisor · 15-20s',
    body: `"Buenos días, señor [apellido]. Le llamo de Duendes, una consultora que implanta IA en despachos de abogados. Es una llamada comercial, se lo digo de entrada. Y le llamo por un motivo concreto: trabajo con despachos de entre cinco y treinta personas, y en casi todos hay dos o tres tareas que se llevan horas del socio cada semana sin necesitar su criterio jurídico. Si no es su caso, me lo dice y le dejo tranquilo. Y si en algún momento prefiere que no volvamos a llamarle, también. ¿Tiene treinta segundos?"

→ CALLAR. No rellenar el silencio.
• "Dígame / adelante" → diagnóstico.
• "No tengo tiempo" → objeciones.
• "¿Qué tareas?" → devuelve pregunta: "Precisamente eso quería preguntarle. ¿Me deja dos preguntas rápidas?"`,
  },
  {
    id: 'diagnostico',
    title: 'Diagnóstico SPIN · 2-2:30 min',
    body: `Una pregunta, callas y escuchas. Que el dolor lo diga ÉL.

S — Situación:
"Las consultas nuevas que entran, las de captación, ¿cómo las gestionan hoy? ¿Hay alguien dedicado a ese filtro o acaba recayendo en los socios?"

P — Problema:
"Cuando eso recae en usted, ¿cuánto tiempo calcula que le come a la semana en gestiones que no requieren su criterio?"

I — Implicación:
"Ese tiempo, ¿a qué se lo está quitando? ¿A trabajo de cliente, a traer asuntos nuevos, o se va en gestión interna?"

N — Need-payoff:
"Si esas tareas se pudieran resolver sin necesitar su atención directa, ¿qué haría usted con ese tiempo?"

→ CALLAR aunque el silencio se alargue.

Munición (si pide ejemplos): el cliente que llama a las 20:00 y si no le cogen llama al de al lado · la consulta del formulario web el domingo sin respuesta hasta el miércoles · horas clasificando correo y WhatsApps de estado · escritos repetitivos (divorcios, arrendamientos, extranjería) · recordatorios de plazos y vistas.`,
  },
  {
    id: 'cierre',
    title: 'Puente + cierre · 45-60s',
    body: `Puente:
"Lo que me describe es justo lo que veo en despachos de su perfil. El problema todavía no es tecnológico: es que nadie ha hecho el mapa de qué tareas concretas se pueden quitar de en medio y cuáles no merece la pena tocar. Eso es lo que hacemos en una conversación de treinta minutos, sin coste. No le propongo nada hasta tener ese mapa. Y si no veo encaje, se lo digo antes que nadie."

Cierre:
"¿Le encaja verlo así?"  → CALLAR.

Si sí, doble alternativa:
"¿Le viene mejor esta semana, por ejemplo el jueves por la mañana, o la que viene en torno al martes?"  (al elegir:) "¿A las 10 o a las 11?"

Confirmación:
"Le llega hoy mismo la convocatoria por correo con el enlace. Para aprovechar los treinta minutos, tenga a mano cuántas personas trabajan en el despacho y qué tareas les comen más tiempo. No es una presentación: le voy a hacer preguntas."

Salida digna (si "ahora no"):
"Lo entiendo. ¿Le parece que le llame dentro de un mes, o prefiere que no le moleste más?" (Si no → "Perfecto, lo respeto. Gracias por su tiempo." Sin tercera llamada.)`,
  },
  {
    id: 'objeciones',
    title: 'Objeciones (en USTED)',
    body: `Reconoce → reencuadra desde el diagnóstico → re-pregunta por los 30 min.

"No tengo tiempo."
→ "Lo entiendo. Deme veinte segundos para el motivo concreto y usted decide. ¿Me los da?"

"Mándeme un email."
→ "Encantado. Para no enviarle ruido: ¿qué le pesa más ahora, la atención a clientes, la carga administrativa o los escritos repetitivos?" (Luego:) "Le mando algo concreto y la semana que viene le llamo cinco minutos."

"Ya tenemos a alguien de informática."
→ "Tiene sentido. Lo nuestro es distinto: no damos soporte técnico, localizamos dónde el despacho pierde tiempo en tareas repetibles y lo dejamos resuelto con presupuesto cerrado. Es independiente de su informático."

"La IA no es para un despacho serio / es confidencial."
→ "Preocupación razonable. Hay cosas que se resuelven sin tocar un expediente: agenda, primera respuesta a consultas generales, recordatorios de plazos. ¿Tendría sentido media hora para ver si hay algo así?"

"¿Cuánto cuesta?"
→ "Le respondo con honestidad: no tengo precio estándar, depende del despacho. Por eso la primera conversación es sin coste. Si hay algo que justifique invertir, ahí le doy cifras; no antes."

"¿De dónde han sacado mi número?"
→ "Pregunta justa. Su despacho aparece en [web / Colegio / directorio]. Si prefiere que no volvamos a contactarle, lo retiro ahora mismo."

"No me interesa."
→ "Entendido. ¿Es que no le interesa la conversación, o que el problema que le he dicho no le pasa?" (Si no le pasa → "Tiene toda la razón. Gracias.")

"Ya estamos mirando algo de IA."
→ "Significa que hay interés. ¿Están mirando herramientas concretas o primero el mapa de qué tareas justifican la inversión? Muchos compran algo y no lo usan porque no encajaba. Eso evitamos en esos treinta minutos."`,
  },
  {
    id: 'prohibidas',
    title: 'Palabras prohibidas',
    body: `NO uses: transformar, optimizar, escalar, potenciar, revolucionar, disruptivo, solución innovadora, sinergia, transformación digital, partner, proactivo, GRATIS (gritado).

Di en su lugar: mejorar, sacar partido, quitar de en medio, dejar resuelto, que lo haga la máquina, sin coste, sin compromiso, poner en marcha, implantar.

Prueba final antes de cada frase: ¿esto lo diría un abogado de 50 años explicándole a un colega cómo trabaja? Si suena a consultora de PowerPoint o a startup, fuera.`,
  },
]

export const SCRIPTS_BY_CAMPAIGN: Record<string, ScriptSection[]> = {
  'fisios-malaga': FISIOS_SCRIPT,
  'despachos-madrid': DESPACHOS_SCRIPT,
}

export const DEFAULT_SCRIPT = FISIOS_SCRIPT

/** Devuelve el guion de la campaña activa, o el genérico si no hay específico. */
export function getScriptForCampaign(slug: string | undefined | null): ScriptSection[] {
  if (slug && SCRIPTS_BY_CAMPAIGN[slug]) return SCRIPTS_BY_CAMPAIGN[slug]
  return DEFAULT_SCRIPT
}

// Compatibilidad con imports antiguos.
export const SCRIPT_SECTIONS = DEFAULT_SCRIPT
