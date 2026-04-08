'use client'

import { useParams } from 'next/navigation'
import { useState, useRef, useEffect } from 'react'
import { DEPT_MAP } from '@/lib/constants'
import type { DeptId, Message } from '@/lib/types'
import MessageBubble from '@/components/chat/message-bubble'
import MessageInput from '@/components/chat/message-input'

function generateId() {
  return Math.random().toString(36).slice(2, 9)
}

export default function ChatPage() {
  const params = useParams()
  const deptId = params.dept as DeptId
  const dept = DEPT_MAP[deptId]

  const [messages, setMessages] = useState<Message[]>([
    {
      id: generateId(),
      role: 'assistant',
      content: dept
        ? `Hola, soy **${dept.displayName}** — ${dept.description}. ¿En qué te puedo ayudar hoy?`
        : 'Hola, ¿en qué te puedo ayudar?',
      createdAt: new Date().toISOString(),
    },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(text: string) {
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text,
      createdAt: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    // Simulated response — replace with real API call
    setTimeout(() => {
      const assistantMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: `Recibido. Esto es una respuesta simulada de **${dept?.displayName ?? 'Agente'}**. El backend aún no está conectado.\n\nMensaje recibido: *"${text}"*`,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMsg])
      setIsLoading(false)
    }, 800)
  }

  if (!dept) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Departamento no encontrado: <code className="ml-2">{deptId}</code>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-card/50 shrink-0">
        <span className="text-2xl">{dept.icon}</span>
        <div>
          <h1 className="text-base font-semibold text-foreground">{dept.displayName}</h1>
          <p className="text-xs text-muted-foreground">{dept.description}</p>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          <span className="text-xs text-muted-foreground">Activo</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            deptIcon={dept.icon}
          />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <span className="text-xl">{dept.icon}</span>
            <span className="animate-pulse">Escribiendo...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-border bg-card/30 shrink-0">
        <MessageInput
          onSend={handleSend}
          disabled={isLoading}
          placeholder={`Mensaje a ${dept.displayName}...`}
        />
      </div>
    </div>
  )
}
