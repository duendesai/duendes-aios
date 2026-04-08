'use client'

import { useRef, useState, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MessageInputProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function MessageInput({
  onSend,
  disabled = false,
  placeholder = 'Escribí tu mensaje... (Cmd+Enter para enviar)',
}: MessageInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSend() {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
    // Reset height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        className={cn(
          'flex-1 resize-none rounded-xl border border-border bg-card px-4 py-2.5 text-sm text-foreground',
          'placeholder:text-muted-foreground',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'min-h-[42px] max-h-[200px] leading-relaxed'
        )}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className={cn(
          'h-[42px] w-[42px] rounded-xl flex items-center justify-center transition-colors shrink-0',
          'bg-primary text-primary-foreground',
          'hover:bg-primary/90',
          'disabled:opacity-40 disabled:cursor-not-allowed'
        )}
        aria-label="Enviar mensaje"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
