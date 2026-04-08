const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function sendMessage(
  dept: string,
  message: string,
  conversationId?: string
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dept, message, conversation_id: conversationId }),
  })
  if (!res.ok) throw new Error('API error')
  return res.json()
}

export function createWebSocket(dept: string): WebSocket {
  const wsBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(
    'http',
    'ws'
  )
  return new WebSocket(`${wsBase}/ws/chat/${dept}`)
}

export async function getProjects(status?: string): Promise<unknown> {
  const url = status
    ? `${API_BASE}/api/projects?status=${status}`
    : `${API_BASE}/api/projects`
  const res = await fetch(url)
  if (!res.ok) throw new Error('API error')
  return res.json()
}

export async function getDashboardFeed(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/dashboard/feed`)
  if (!res.ok) throw new Error('API error')
  return res.json()
}
