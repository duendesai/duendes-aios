// Valores reales verificados desde Airtable (2026-05-18)

import type {
  BuyingSignal,
  ContactoAlcanzado,
  Disposition,
  MotivoFin,
  MotivoPerdida,
  Objecion,
} from './types'

export const DISPOSITION_OPTIONS: { value: Disposition; label: string; tone: 'neutral' | 'positive' | 'negative' | 'warning' }[] = [
  { value: 'Agendada', label: 'Agendada', tone: 'positive' },
  { value: 'No contesta', label: 'No contesta', tone: 'warning' },
  { value: 'Contestador', label: 'Contestador', tone: 'warning' },
  { value: 'Comunica', label: 'Comunica', tone: 'warning' },
  { value: 'Gatekeeper', label: 'Gatekeeper', tone: 'warning' },
  { value: 'Info solicitada', label: 'Info solicitada', tone: 'neutral' },
  { value: 'Interes calido', label: 'Interés cálido', tone: 'positive' },
  { value: 'Rellamar', label: 'Rellamar', tone: 'neutral' },
  { value: 'No interesa', label: 'No interesa', tone: 'negative' },
  { value: 'No interesa ahora', label: 'No interesa (ahora)', tone: 'negative' },
  { value: 'No cualifica', label: 'No cualifica', tone: 'negative' },
  { value: 'No llamar', label: 'No llamar (DNC)', tone: 'negative' },
  { value: 'Numero erroneo', label: 'Número erróneo', tone: 'negative' },
  { value: 'Numero inexistente', label: 'Número inexistente', tone: 'negative' },
  { value: 'Ilocalizable', label: 'Ilocalizable', tone: 'negative' },
]

export const CONTACTO_OPTIONS: { value: ContactoAlcanzado; label: string }[] = [
  { value: 'Propietario', label: 'Propietario / Decisor' },
  { value: 'Recepción', label: 'Recepción' },
  { value: 'Profesional', label: 'Profesional (no decisor)' },
  { value: 'Otro', label: 'Otro' },
  { value: 'Ninguno', label: 'Ninguno (no contestó)' },
]

export const BUYING_SIGNAL_OPTIONS: { value: BuyingSignal; label: string }[] = [
  { value: 'Senal real', label: 'Señal real (interés)' },
  { value: 'Curiosidad', label: 'Curiosidad' },
  { value: 'Cortesia', label: 'Cortesía' },
  { value: 'N/A', label: 'N/A' },
]

export const MOTIVO_PERDIDA_OPTIONS: { value: MotivoPerdida; label: string }[] = [
  { value: 'Precio', label: 'Precio' },
  { value: 'Tiempo', label: 'Tiempo' },
  { value: 'Ya tiene solución', label: 'Ya tiene solución' },
  { value: 'Desconfianza IA', label: 'Desconfianza IA' },
  { value: 'No ICP', label: 'No es ICP' },
  { value: 'Robinson/DNC', label: 'Robinson / DNC' },
  { value: 'RGPD/Origen datos', label: 'RGPD / origen datos' },
  { value: 'Amenaza denuncia', label: 'Amenaza denuncia' },
  { value: 'DNC explícito', label: 'DNC explícito' },
  { value: 'Ilocalizable', label: 'Ilocalizable' },
  { value: 'Otra', label: 'Otra' },
]

export const OBJECIONES_OPTIONS: { value: Objecion; label: string }[] = [
  { value: 'Precio', label: 'Precio' },
  { value: 'Tiempo', label: 'Tiempo' },
  { value: 'Ya tiene solucion', label: 'Ya tiene solución' },
  { value: 'Desconfianza IA', label: 'Desconfianza IA' },
  { value: 'No interesado, ya están bien como están', label: 'Ya están bien como están' },
  { value: 'Otra', label: 'Otra' },
]

export const MOTIVO_FIN_OPTIONS: { value: MotivoFin; label: string }[] = [
  { value: 'customer-ended-call', label: 'Cliente colgó' },
  { value: 'no-answer', label: 'No contestó' },
  { value: 'voicemail', label: 'Buzón de voz' },
  { value: 'busy', label: 'Comunicaba' },
  { value: 'failed', label: 'Fallo técnico' },
]

/**
 * Mapeo Disposition (Calls) → Estado (malaga).
 * En `malaga` el valor "Agendada" se llama "Demo agendada", el resto coincide.
 */
export const DISPOSITION_TO_ESTADO: Record<Disposition, string> = {
  Agendada: 'Demo agendada',
  Pendiente: 'Pendiente',
  'No contesta': 'No contesta',
  Contestador: 'Contestador',
  Comunica: 'Comunica',
  Gatekeeper: 'Gatekeeper',
  'Info solicitada': 'Info solicitada',
  Rellamar: 'Rellamar',
  'Interes calido': 'Interés cálido',
  'No interesa': 'No interesa',
  'Numero erroneo': 'Número erróneo',
  'Numero inexistente': 'Número inexistente',
  'No cualifica': 'No cualifica',
  Ilocalizable: 'Ilocalizable',
  'No llamar': 'No llamar',
  'No interesa ahora': 'No interesa ahora',
}

/**
 * Mapeo Disposition → outcome canonical.
 */
export const DISPOSITION_TO_OUTCOME: Record<Disposition, string> = {
  Agendada: 'demo_agendada',
  'No interesa': 'no_interesa',
  'No interesa ahora': 'no_interesa',
  'No cualifica': 'no_interesa',
  'No llamar': 'no_llamar',
  Rellamar: 'callback',
  'Info solicitada': 'callback',
  'Interes calido': 'callback',
  'No contesta': 'no_contesta',
  Contestador: 'no_contesta',
  Comunica: 'no_contesta',
  Gatekeeper: 'no_contesta',
  Ilocalizable: 'no_contesta',
  'Numero erroneo': 'no_llamar',
  'Numero inexistente': 'no_llamar',
  Pendiente: 'no_contesta',
}

export const NEGATIVE_DISPOSITIONS: Disposition[] = [
  'No interesa',
  'No interesa ahora',
  'No cualifica',
  'No llamar',
  'Numero erroneo',
  'Numero inexistente',
  'Ilocalizable',
]
