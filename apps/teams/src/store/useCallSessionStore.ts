'use client'

import { create } from 'zustand'
import type { Campaign, Prospect } from '@/lib/sdr/types'
import type { QueueMode } from '@/lib/sdr/api'

export type CallState = 'idle' | 'in_call' | 'wrap_up'

const QUEUE_MODE_STORAGE_KEY = 'teams-sdr-queue-mode'
const QUEUE_CAMPAIGN_STORAGE_KEY = 'teams-sdr-campaign'

function loadInitialMode(): QueueMode {
  if (typeof window === 'undefined') return 'all'
  const saved = window.localStorage.getItem(QUEUE_MODE_STORAGE_KEY) as QueueMode | null
  return saved === 'warm' || saved === 'cold' || saved === 'all' ? saved : 'all'
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

  // Session metrics
  sessionStartedAt: number
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

  sessionStartedAt: Date.now(),
  stats: { called: 0, booked: 0, lost: 0, callback: 0, noContact: 0 },

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
    set((s) => ({
      callState: 'idle',
      callStartedAt: null,
      callDurationSec: 0,
      showBooking: false,
      stats: {
        called: s.stats.called + 1,
        booked: s.stats.booked + (outcome === 'booked' ? 1 : 0),
        lost: s.stats.lost + (outcome === 'lost' ? 1 : 0),
        callback: s.stats.callback + (outcome === 'callback' ? 1 : 0),
        noContact: s.stats.noContact + (outcome === 'no_contact' ? 1 : 0),
      },
    })),

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

  resetSession: () =>
    set({
      sessionStartedAt: Date.now(),
      stats: { called: 0, booked: 0, lost: 0, callback: 0, noContact: 0 },
      callState: 'idle',
      callStartedAt: null,
      callDurationSec: 0,
      showBooking: false,
    }),

  tickDuration: () => {
    const { callState, callStartedAt } = get()
    if (callState === 'in_call' && callStartedAt) {
      set({ callDurationSec: Math.floor((Date.now() - callStartedAt) / 1000) })
    }
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
