'use client'

import { useEffect } from 'react'

type Handler = (e: KeyboardEvent) => void

/**
 * Hook que registra atajos de teclado a nivel global.
 * Ignora si el foco está en input/textarea/select o si hay un dialog abierto.
 */
export function useKeyboardShortcuts(map: Record<string, Handler>, enabled = true) {
  useEffect(() => {
    if (!enabled) return
    function handler(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (target?.isContentEditable) return

      const key = e.key === 'Escape' ? 'Escape' : e.key.toUpperCase()
      const fn = map[key] || map[e.key]
      if (fn) {
        e.preventDefault()
        fn(e)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [map, enabled])
}
