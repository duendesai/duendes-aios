'use client'

import { Bell, Moon } from 'lucide-react'
import { usePathname } from 'next/navigation'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/projects': 'Proyectos',
  '/documents': 'Documentos',
  '/agents': 'Agentes',
  '/connectors': 'Conectores',
  '/settings': 'Settings',
}

function getTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname]
  const chatMatch = pathname.match(/^\/chat\/(.+)$/)
  if (chatMatch) return `Chat — ${chatMatch[1].toUpperCase()}`
  return 'AIOS'
}

export default function Topbar() {
  const pathname = usePathname()
  const title = getTitle(pathname)

  return (
    <header className="h-12 flex items-center justify-between px-6 border-b border-border bg-card/50 shrink-0">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <div className="flex items-center gap-1">
        <button
          className="h-8 w-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          aria-label="Notificaciones"
        >
          <Bell className="h-4 w-4" />
        </button>
        <button
          className="h-8 w-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          aria-label="Modo oscuro activo"
        >
          <Moon className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
