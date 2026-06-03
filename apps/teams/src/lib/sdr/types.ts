// Types compartidos con apps/api/routers/calls.py
// Schemas reales verificados desde Airtable el 2026-05-18

export type Disposition =
  | 'Pendiente'
  | 'No contesta'
  | 'Contestador'
  | 'Comunica'
  | 'Gatekeeper'
  | 'Info solicitada'
  | 'Rellamar'
  | 'Interes calido'
  | 'Agendada'
  | 'No interesa'
  | 'Numero erroneo'
  | 'Numero inexistente'
  | 'No cualifica'
  | 'Ilocalizable'
  | 'No llamar'
  | 'No interesa ahora'

export type ContactoAlcanzado =
  | 'Propietario'
  | 'Recepción'
  | 'Profesional'
  | 'Otro'
  | 'Ninguno'

export type BuyingSignal = 'Cortesia' | 'Curiosidad' | 'Senal real' | 'N/A'

export type MotivoPerdida =
  | 'Precio'
  | 'Tiempo'
  | 'Ya tiene solución'
  | 'Desconfianza IA'
  | 'No ICP'
  | 'Otra'
  | 'Robinson/DNC'
  | 'RGPD/Origen datos'
  | 'Amenaza denuncia'
  | 'DNC explícito'
  | 'Ilocalizable'

export type Objecion =
  | 'Precio'
  | 'Tiempo'
  | 'Ya tiene solucion'
  | 'Desconfianza IA'
  | 'Otra'
  | 'No interesado, ya están bien como están'

export type MotivoFin =
  | 'customer-ended-call'
  | 'no-answer'
  | 'voicemail'
  | 'busy'
  | 'failed'

export interface DatosEnriquecidos {
  booking_online?: boolean
  resenas?: number
  rating?: number
  redes?: string[]
  tamano?: string
  servicios?: string[]
  horario?: string
  [k: string]: unknown
}

export interface Prospect {
  id: string
  title: string
  phone: string | null
  city: string | null
  category_name: string | null
  website: string | null
  estado: string | null
  lane: string | null
  intentos: number
  notas: string | null
  ultimo_intento: string | null
  proximo_intento: string | null
  contacto_nombre: string | null
  contacto_alcanzado: string | null
  motivo_perdida: string | null
  callback_solicitado: string | null
  callback_notas: string | null
  prioridad: string | null
  score: number | null
  tamano: string | null
  booking_online: boolean
  datos_enriquecidos: DatosEnriquecidos | null
  crm_url: string | null
  call_history?: CallHistoryItem[]
  emails?: EmailItem[]
  last_email?: LastEmailSummary | null
  email_count?: number
}

export interface CallHistoryItem {
  id: string
  fecha: string | null
  disposition: string | null
  buying_signal: string | null
  notas: string | null
  duracion_seg: number | null
}

export type EmailStatus =
  | 'sent'
  | 'opened'
  | 'clicked'
  | 'replied'
  | 'bounced'
  | 'unsubscribed'

export interface EmailItem {
  id: string
  email_id: string | null
  fecha_envio: string | null
  destino: string | null
  asunto: string | null
  cuerpo: string | null
  status: EmailStatus
  fecha_apertura: string | null
  fecha_respuesta: string | null
  respuesta: string | null
  campaign: string | null
}

export interface LastEmailSummary {
  asunto: string | null
  fecha_envio: string | null
  status: EmailStatus
  days_ago: number | null
}

export interface CallResultPayload {
  prospect_id: string
  disposition: Disposition
  contacto_alcanzado: ContactoAlcanzado | null
  buying_signal: BuyingSignal
  motivo_fin?: MotivoFin
  motivo_perdida?: MotivoPerdida | null
  objeciones?: Objecion[]
  discovery_completo?: boolean
  notas?: string
  transcripcion?: string
  duracion_seg?: number
  callback_at?: string | null
  callback_notas?: string | null
  contacto_nombre?: string | null
}

export interface Slot {
  start: string
  end: string
}

export interface BookingPayload {
  prospect_id: string
  slot_start: string
  attendee_name: string
  attendee_email: string
  attendee_phone?: string | null
  empresa?: string | null
  sector?: string | null
  notes?: string | null
}

export interface Booking {
  booking_id: string
  booking_uid: string
  meeting_url: string | null
  start: string
  end: string
  lead_id?: string | null
  crm_url?: string | null
}

export interface QueueResponse {
  prospects: Prospect[]
  total: number
  mode?: 'warm' | 'cold' | 'all'
  campaign?: string | null
}

export interface Campaign {
  id: string // slug, p.ej. 'despachos-madrid'
  label: string // nombre visible, p.ej. 'Despachos Madrid'
  count: number // prospectos activos (con teléfono, no excluidos)
}

export interface CallAnalysis {
  resumen: string
  puntos_clave: string[]
  proximos_pasos: string[]
  necesita_email: boolean
  email_asunto: string
  email_cuerpo: string
}

export interface AnalyzeResult {
  ok: boolean
  reason?: string
  recording_url?: string
  seconds?: number
  transcript?: string
  analysis?: CallAnalysis
}

export interface CampaignsResponse {
  campaigns: Campaign[]
}

export interface AgendaProspect extends Prospect {
  callback_at: string // ISO
}

export interface AgendaResponse {
  overdue: AgendaProspect[]
  today: AgendaProspect[]
  week: AgendaProspect[]
  later: AgendaProspect[]
  totals: {
    overdue: number
    today: number
    week: number
    later: number
    all: number
  }
}
