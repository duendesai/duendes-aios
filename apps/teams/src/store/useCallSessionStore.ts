'use client'

import { create } from 'zustand'
import type { Campaign, Prospect } from '@/lib/sdr/types'
import type { QueueMode } from '@/lib/sdr/api'

export type CallState = 'idle' | 'in_call' | 'wrap_up'

const QUEUE_MODE_STORAGE_KEY = 'teams-sdr-queue-mode'
const QUEUE_CAMPAIGN_STORAGE_KEY = 'teams-sdr-campaign'

function loadInitialMode(): QueueMode {
  if (typeof window === 'undefined') return 'warm_opened'
  const saved = window.localStorage.getItem(QUEUE_MODE_STORAGE_KEY) as QueueMode | null
  // Acepta solo los modos nuevos; valores antiguos ('warm', 'all') migran al default.
  if (saved === 'warm_opened' || saved === 'warm_not_opened' || saved === 'cold') {
    return saved
  }
  return 'warm_opened'
}

function loadInitialCampaign(): string {
  if (typeof window === 'undefined') return 'fisios-malaga'
  return window.localStorage.getItem(QUEUE_CAMPAIGN_STORAGE_KEY) || 'fisios-malaga'
}

interface SessionStats {
  called: number
  booked: number
  lost: number
  callback: number
  noContact: number
}

// ── Métricas DIARIAS ────────────────────────────────────────────────────────
// El bloque "Sesión SDR" (tiempo de trabajo + llamadas/agendadas/...) acumula
// durante el día natural y se reinicia solo al cambiar de día. Persistido en
// localStorage de este navegador (no por apertura del dialer).
const DAILY_STATE_STORAGE_KEY = 'teams-sdr-daily-state'

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate()
  ).padStart(2, '0')}`
}

function emptyStats(): SessionStats {
  return { called: 0, booked: 0, lost: 0, callback: 0, noContact: 0 }
}

interface DailyState {
  date: string
  stats: SessionStats
  workedSeconds: number
}

function loadDailyState(): DailyState {
  const today = todayKey()
  const fresh: DailyState = { date: today, stats: emptyStats(), workedSeconds: 0 }
  if (typeof window === 'undefined') return fresh
  try {
    const raw = window.localStorage.getItem(DAILY_STATE_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<DailyState>
      if (parsed.date === today && parsed.stats) {
        return {
          date: today,
          stats: { ...emptyStats(), ...parsed.stats },
          workedSeconds: parsed.workedSeconds || 0,
        }
      }
    }
  } catch {
    /* localStorage no disponible o corrupto → empezar limpio */
  }
  return fresh
}

function persistDailyState(
  date: string,
  stats: SessionStats,
  workedSeconds: number
): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      DAILY_STATE_STORAGE_KEY,
      JSON.stringify({ date, stats, workedSeconds })
    )
  } catch {
    /* ignore */
  }
}

const _initialDaily = loadDailyState()

interface CallSessionState {
  // Queue
  prospects: Prospect[]
  activeId: string | null
  loadingQueue: boolean
  queueError: string | null
  mode: QueueMode
  campaign: string
  campaigns: Campaign[]

  // Active prospect detail (con call_history)
  activeProspect: Prospect | null
  loadingProspect: boolean

  // Call lifecycle
  callState: CallState
  callStartedAt: number | null
  callDurationSec: number

  // Booking flow
  showBooking: boolean
  bookingPending: boolean

  // Session metrics (DIARIAS — persisten el día natural; ver loadDailyState)
  statsDate: string
  workedSeconds: number
  stats: SessionStats

  // Actions
  setQueue: (prospects: Prospect[]) => void
  setQueueLoading: (loading: boolean, error?: string | null) => void
  setMode: (m: QueueMode) => void
  setCampaign: (c: string) => void
  setCampaigns: (campaigns: Campaign[]) => void
  selectProspect: (id: string) => void
  setActiveProspect: (p: Prospect | null) => void
  setProspectLoading: (loading: boolean) => void
  startCall: () => void
  endCall: () => void
  finishWrapUp: (outcome: 'booked' | 'lost' | 'callback' | 'no_contact') => void
  openBooking: () => void
  closeBooking: () => void
  setBookingPending: (pending: boolean) => void
  nextProspect: () => void
  resetSession: () => void
  tickDuration: () => void
  tickWorked: () => void

  // Computed
  getActiveProspect: () => Prospect | null
  getConversionRate: () => number
}

export const useCallSessionStore = create<CallSessionState>((set, get) => ({
  prospects: [],
  activeId: null,
  loadingQueue: true,
  queueError: null,
  mode: loadInitialMode(),
  campaign: loadInitialCampaign(),
  campaigns: [],

  activeProspect: null,
  loadingProspect: false,

  callState: 'idle',
  callStartedAt: null,
  callDurationSec: 0,

  showBooking: false,
  bookingPending: false,

  statsDate: _initialDaily.date,
  workedSeconds: _initialDaily.workedSeconds,
  stats: _initialDaily.stats,

  setQueue: (prospects) =>
    set((s) => ({
      prospects,
      loadingQueue: false,
      queueError: null,
      activeId: prospects.length
        ? prospects.some((p) => p.id === s.activeId)
          ? s.activeId
          : prospects[0].id
        : null,
    })),

  setQueueLoading: (loading, error = null) => set({ loadingQueue: loading, queueError: error }),

  setMode: (m) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(QUEUE_MODE_STORAGE_KEY, m)
    }
    set({ mode: m })
  },

  setCampaign: (c) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(QUEUE_CAMPAIGN_STORAGE_KEY, c)
    }
    set({ campaign: c })
  },

  setCampaigns: (campaigns) => set({ campaigns }),

  selectProspect: (id) =>
    set({
      activeId: id,
      callState: 'idle',
      callStartedAt: null,
      callDurationSec: 0,
      showBooking: false,
      activeProspect: null,
    }),

  setActiveProspect: (p) => set({ activeProspect: p }),
  setProspectLoading: (loading) => set({ loadingProspect: loading }),

  startCall: () =>
    set({
      callState: 'in_call',
      callStartedAt: Date.now(),
      callDurationSec: 0,
    }),

  endCall: () => set({ callState: 'wrap_up' }),

  finishWrapUp: (outcome) =>
    set((s) => {
      const today = todayKey()
      // Si cambió el día desde la última actualización, parte de cero.
      const base = s.statsDate === today ? s.stats : emptyStats()
      const worked = s.statsDate === today ? s.workedSeconds : 0
      const stats: SessionStats = {
        called: base.called + 1,
        booked: base.booked + (outcome === 'booked' ? 1 : 0),
        lost: base.lost + (outcome === 'lost' ? 1 : 0),
        callback: base.callback + (outcome === 'callback' ? 1 : 0),
        noContact: base.noContact + (outcome === 'no_contact' ? 1 : 0),
      }
      persistDailyState(today, stats, worked)
      return {
        callState: 'idle',
        callStartedAt: null,
        callDurationSec: 0,
        showBooking: false,
        stats,
        statsDate: today,
        workedSeconds: worked,
      }
    }),

  openBooking: () => set({ showBooking: true }),
  closeBooking: () => set({ showBooking: false, bookingPending: false }),
  setBookingPending: (pending) => set({ bookingPending: pending }),

  nextProspect: () => {
    const { prospects, activeId } = get()
    if (!prospects.length) {
      set({ activeId: null, activeProspect: null, callState: 'idle' })
      return
    }
    const idx = prospects.findIndex((p) => p.id === activeId)
    // El prospecto que acabamos de procesar puede seguir en la cola hasta el próximo refresh.
    // Para evitar volver a llamar al mismo, lo quitamos de la cola local.
    const remaining = prospects.filter((p) => p.id !== activeId)
    const next = remaining[idx] || remaining[0] || null
    set({
      prospects: remaining,
      activeId: next?.id ?? null,
      activeProspect: null,
      callState: 'idle',
      callStartedAt: null,
      callDurationSec: 0,
      showBooking: false,
    })
  },

  resetSession: () => {
    const today = todayKey()
    persistDailyState(today, emptyStats(), 0)
    set({
      statsDate: today,
      workedSeconds: 0,
      stats: emptyStats(),
      callState: 'idle',
      callStartedAt: null,
      callDurationSec: 0,
      showBooking: false,
    })
  },

  tickDuration: () => {
    const { callState, callStartedAt } = get()
    if (callState === 'in_call' && callStartedAt) {
      set({ callDurationSec: Math.floor((Date.now() - callStartedAt) / 1000) })
    }
  },

  tickWorked: () => {
    const today = todayKey()
    const { statsDate, stats, workedSeconds } = get()
    if (statsDate !== today) {
      // Pasó la medianoche con el dialer abierto → reinicia el día.
      persistDailyState(today, emptyStats(), 0)
      set({ statsDate: today, stats: emptyStats(), workedSeconds: 0 })
      return
    }
    const next = workedSeconds + 1
    if (next % 5 === 0) persistDailyState(today, stats, next) // persistir cada 5s
    set({ workedSeconds: next })
  },

  getActiveProspect: () => {
    const { prospects, activeId } = get()
    return prospects.find((p) => p.id === activeId) ?? null
  },

  getConversionRate: () => {
    const { called, booked } = get().stats
    return called === 0 ? 0 : Math.round((booked / called) * 100)
  },
}))
