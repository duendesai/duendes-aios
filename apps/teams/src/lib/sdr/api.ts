/**
 * Cliente HTTP del power dialer SDR.
 * Habla con `apps/api` (FastAPI) — router /calls.
 *
 * Autentica con el JWT de Supabase en el header `Authorization`.
 * El backend en v1 NO valida el token (acceso interno solo-Oscar) pero
 * se envía siempre por buena práctica y para preparar la migración.
 */

import { createClient } from '@/lib/supabase/client'
import type {
  AgendaResponse,
  AnalyzeResult,
  Booking,
  BookingPayload,
  CallResultPayload,
  CampaignsResponse,
  Prospect,
  QueueResponse,
  Slot,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const supabase = createClient()
    const {
      data: { session },
    } = await supabase.auth.getSession()
    return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}
  } catch {
    return {}
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const auth = await getAuthHeader()
  const res = await fetch(`${BASE_URL}/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...auth,
      ...(init.headers || {}),
    },
    cache: 'no-store',
  })
  const text = await res.text()
  const body = text ? safeJson(text) : null
  if (!res.ok) {
    const detail =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `${res.status} ${res.statusText}`
    throw new ApiError(detail, res.status, body)
  }
  return body as T
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.status = status
    this.body = body
    this.name = 'ApiError'
  }
}

export type QueueMode = 'warm_opened' | 'warm_not_opened' | 'cold'

export async function fetchQueue(
  maxRecords = 50,
  mode: QueueMode = 'warm_opened',
  campaign?: string | null
): Promise<QueueResponse> {
  const params = new URLSearchParams({ max_records: String(maxRecords), mode })
  if (campaign) params.set('campaign', campaign)
  return request<QueueResponse>(`/calls/queue?${params.toString()}`)
}

export async function fetchCampaigns(): Promise<CampaignsResponse> {
  return request<CampaignsResponse>('/calls/campaigns')
}

export async function fetchAgenda(
  daysAhead = 14,
  campaign?: string | null
): Promise<AgendaResponse> {
  const params = new URLSearchParams({ days_ahead: String(daysAhead) })
  if (campaign) params.set('campaign', campaign)
  return request<AgendaResponse>(`/calls/agenda?${params.toString()}`)
}

export async function fetchProspect(id: string): Promise<Prospect> {
  return request<Prospect>(`/calls/prospect/${encodeURIComponent(id)}`)
}

export async function submitResult(payload: CallResultPayload): Promise<{
  ok: boolean
  call_id: string
  partial?: boolean
}> {
  return request('/calls/result', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSlots(days = 7): Promise<{ slots: Slot[]; total: number }> {
  return request(`/calls/calcom/slots?days=${days}`)
}

export async function bookSlot(payload: BookingPayload): Promise<Booking> {
  return request('/calls/calcom/book', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function dialProspect(payload: {
  prospect_id: string
  phone: string
}): Promise<{ ok: boolean; zadarma: Record<string, unknown> }> {
  return request('/calls/zadarma/dial', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchWebrtcKey(): Promise<{ status: string; key: string }> {
  return request('/calls/webrtc/key')
}

export async function analyzeCall(payload: {
  prospect_id: string
  phone: string
  prospect_name?: string
  disposition?: string
  call_record_id?: string
}): Promise<AnalyzeResult> {
  return request('/calls/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
