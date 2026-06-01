'use client'

import { useEffect, useState } from 'react'
import { Clock, PhoneCall, PhoneOff, Calendar, RotateCcw, Phone, Mail, MailOpen, Snowflake } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import type { QueueMode } from '@/lib/sdr/api'
import type { Campaign } from '@/lib/sdr/types'

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
  onModeChange: (m: QueueMode) => void
  campaigns: Campaign[]
  activeCampaign: string
  onCampaignChange: (slug: string) => void
}

const MODES: { value: QueueMode; label: string; icon: typeof Mail; hint: string }[] = [
  {
    value: 'warm_opened',
    label: 'Abrieron',
    icon: MailOpen,
    hint: 'Recibieron y abrieron el email. Sort: apertura más antigua primero (la curiosidad se enfría).',
  },
  {
    value: 'warm_not_opened',
    label: 'Sin abrir',
    icon: Mail,
    hint: 'Recibieron el email pero aún no lo han abierto. Reserva para cuando se acaben los abiertos.',
  },
  {
    value: 'cold',
    label: 'Frías',
    icon: Snowflake,
    hint: 'Sin email programado — llamada en frío pura.',
  },
]

export function SessionHeader({
  totalQueue,
  onReset,
  onModeChange,
  campaigns,
  activeCampaign,
  onCampaignChange,
}: SessionHeaderProps) {
  const stats = useCallSessionStore((s) => s.stats)
  const mode = useCallSessionStore((s) => s.mode)
  const sessionStartedAt = useCallSessionStore((s) => s.sessionStartedAt)
  const conversion = useCallSessionStore((s) => s.getConversionRate())

  const [elapsedMs, setElapsedMs] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setElapsedMs(Date.now() - sessionStartedAt), 1000)
    return () => clearInterval(id)
  }, [sessionStartedAt])

  return (
    <header className="h-20 shrink-0 border-b border-border px-6 flex items-center justify-between bg-card gap-6">
      {/* Selector de campaña */}
      {campaigns.length > 0 && (
        <div className="flex items-center gap-2 shrink-0">
          <select
            value={activeCampaign}
            onChange={(e) => onCampaignChange(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-semibold text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-purple/40 cursor-pointer"
            title="Cambiar de campaña"
          >
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} ({c.count})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Toggle de modos — primera cosa que ves */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-muted border border-border shrink-0">
        {MODES.map(({ value, label, icon: Icon, hint }) => {
          const active = mode === value
          return (
            <button
              key={value}
              onClick={() => onModeChange(value)}
              title={hint}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                active
                  ? 'bg-brand-purple text-white shadow-sm'
                  : 'text-brand-dark/60 hover:text-brand-dark'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-8 flex-1">
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
