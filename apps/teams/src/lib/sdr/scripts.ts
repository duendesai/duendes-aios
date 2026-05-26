/**
 * Script SDR de referencia — adaptado del prompt v8 de Lucía (uso interno).
 * Visible en el panel derecho de /sdr para que Oscar lo consulte sin salir.
 */

export interface ScriptSection {
  id: string
  title: string
  body: string
}

export const SCRIPT_SECTIONS: ScriptSection[] = [
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
