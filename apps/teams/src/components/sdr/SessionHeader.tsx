'use client'

import { useEffect, useState } from 'react'
import { Clock, PhoneCall, PhoneOff, Calendar, RotateCcw, Phone } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useCallSessionStore } from '@/store/useCallSessionStore'

function fmtElapsed(ms: number): string {
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

interface SessionHeaderProps {
  totalQueue: number
  onReset: () => void
}

export function SessionHeader({ totalQueue, onReset }: SessionHeaderProps) {
  const stats = useCallSessionStore((s) => s.stats)
  const sessionStartedAt = useCallSessionStore((s) => s.sessionStartedAt)
  const conversion = useCallSessionStore((s) => s.getConversionRate())

  const [elapsedMs, setElapsedMs] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setElapsedMs(Date.now() - sessionStartedAt), 1000)
    return () => clearInterval(id)
  }, [sessionStartedAt])

  return (
    <header className="h-16 shrink-0 border-b border-border px-6 flex items-center justify-between bg-card">
      <div className="flex items-center gap-8">
        <div>
          <p className="tag-label text-brand-purple-dark">Sesión SDR</p>
          <div className="font-display font-bold text-brand-dark text-base leading-tight mt-0.5">
            {fmtElapsed(elapsedMs)}
          </div>
        </div>

        <Divider />

        <Stat
          icon={<PhoneCall className="h-4 w-4 text-brand-dark/40" />}
          label="Llamadas"
          value={stats.called}
        />
        <Stat
          icon={<Calendar className="h-4 w-4 text-success" />}
          label="Agendadas"
          value={stats.booked}
          highlight="success"
        />
        <Stat
          icon={<PhoneOff className="h-4 w-4 text-warning" />}
          label="Sin contacto"
          value={stats.noContact}
        />
        <Stat
          icon={<PhoneOff className="h-4 w-4 text-destructive" />}
          label="Perdidas"
          value={stats.lost}
        />
        <Stat
          icon={<Clock className="h-4 w-4 text-brand-purple" />}
          label="Callback"
          value={stats.callback}
        />

        <Divider />

        <Stat label="Conversión" value={`${conversion}%`} highlight="purple" />
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <Phone className="h-4 w-4 text-brand-dark/40" />
          <span className="font-bold text-brand-dark">{totalQueue}</span>
          <span className="text-muted-foreground">en cola</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onReset}
          title="Reiniciar contadores de la sesión"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>
    </header>
  )
}

function Divider() {
  return <span className="h-8 w-px bg-border" />
}

function Stat({
  icon,
  label,
  value,
  highlight,
}: {
  icon?: React.ReactNode
  label: string
  value: number | string
  highlight?: 'success' | 'purple'
}) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <div className="text-sm leading-tight">
        <div
          className={`font-display font-bold text-base ${
            highlight === 'success'
              ? 'text-success'
              : highlight === 'purple'
              ? 'text-brand-purple-dark'
              : 'text-brand-dark'
          }`}
        >
          {value}
        </div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
      </div>
    </div>
  )
}
