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
  Booking,
  BookingPayload,
  CallResultPayload,
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

export async function fetchQueue(maxRecords = 50): Promise<QueueResponse> {
  return request<QueueResponse>(`/calls/queue?max_records=${maxRecords}`)
}

export async function fetchAgenda(daysAhead = 14): Promise<AgendaResponse> {
  return request<AgendaResponse>(`/calls/agenda?days_ahead=${daysAhead}`)
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
