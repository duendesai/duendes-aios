'use client'

import { useMemo } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertTriangle,
  Clock,
  Phone,
  ChevronRight,
  MapPin,
  Sparkle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn, normalizePhoneEs } from '@/lib/utils'
import type { AgendaProspect, AgendaResponse } from '@/lib/sdr/types'

const TZ = 'Europe/Madrid'

interface AgendaTimelineProps {
  data: AgendaResponse
  selectedDay: Date | null
  onClearFilter: () => void
}

function fmtHour(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TZ,
  })
}

function fmtDayHeader(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('es-ES', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    timeZone: TZ,
  })
}

function dayKey(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

function isToday(iso: string): boolean {
  const today = new Date()
  const d = new Date(iso)
  return (
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  )
}

function relativeTime(iso: string): string {
  const now = Date.now()
  const target = new Date(iso).getTime()
  const diffMin = Math.round((target - now) / 60000)

  if (diffMin <= -60 * 24)
    return `Hace ${Math.round(-diffMin / (60 * 24))} días`
  if (diffMin <= -60) return `Hace ${Math.round(-diffMin / 60)}h`
  if (diffMin < 0) return `Hace ${-diffMin} min`
  if (diffMin < 60) return `En ${diffMin} min`
  if (diffMin < 60 * 24) return `En ${Math.round(diffMin / 60)}h`
  return `En ${Math.round(diffMin / (60 * 24))} días`
}

export function AgendaTimeline({
  data,
  selectedDay,
  onClearFilter,
}: AgendaTimelineProps) {
  const router = useRouter()

  // Combinamos todos los buckets y los agrupamos por día (si selectedDay, filtramos)
  const grouped = useMemo(() => {
    const all = [
      ...data.overdue,
      ...data.today,
      ...data.week,
      ...data.later,
    ]
    const filtered = selectedDay
      ? all.filter((p) => {
          const d = new Date(p.callback_at)
          return (
            d.getFullYear() === selectedDay.getFullYear() &&
            d.getMonth() === selectedDay.getMonth() &&
            d.getDate() === selectedDay.getDate()
          )
        })
      : all
    const groups = new Map<string, AgendaProspect[]>()
    for (const p of filtered) {
      const key = dayKey(p.callback_at)
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(p)
    }
    return Array.from(groups.entries()).sort((a, b) => {
      const da = new Date(a[1][0].callback_at).getTime()
      const db = new Date(b[1][0].callback_at).getTime()
      return da - db
    })
  }, [data, selectedDay])

  if (grouped.length === 0) {
    return (
      <Card className="p-12 text-center space-y-3">
        <Sparkle className="h-8 w-8 text-brand-purple/40 mx-auto" />
        <p className="font-display font-bold text-brand-dark">
          {selectedDay ? 'Día libre' : 'Agenda limpia'}
        </p>
        <p className="text-sm text-muted-foreground max-w-xs mx-auto">
          {selectedDay
            ? 'No hay callbacks programados este día.'
            : 'No tienes callbacks programados todavía. Cuando marques un prospecto como "Rellamar", aparecerá aquí.'}
        </p>
        {selectedDay && (
          <button
            onClick={onClearFilter}
            className="text-sm text-brand-purple-dark hover:underline"
          >
            Ver toda la agenda
          </button>
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {grouped.map(([key, items]) => {
        const firstIso = items[0].callback_at
        const today = isToday(firstIso)
        return (
          <section key={key}>
            <div className="flex items-baseline gap-3 mb-3">
              <h2 className="font-display text-lg font-bold text-brand-dark capitalize">
                {fmtDayHeader(firstIso)}
              </h2>
              {today && <Badge variant="cta">Hoy</Badge>}
              <span className="text-xs text-muted-foreground">
                {items.length} {items.length === 1 ? 'callback' : 'callbacks'}
              </span>
            </div>

            <div className="space-y-2">
              {items.map((p) => (
                <AgendaItem
                  key={p.id}
                  prospect={p}
                  onClick={() => router.push(`/sdr?prospect=${p.id}`)}
                />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function AgendaItem({
  prospect,
  onClick,
}: {
  prospect: AgendaProspect
  onClick: () => void
}) {
  const overdue = new Date(prospect.callback_at) < new Date()
  const phone = normalizePhoneEs(prospect.phone)

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 rounded-2xl border bg-card flex items-center gap-4 transition-all hover:shadow-sm group',
        overdue
          ? 'border-destructive/30 bg-destructive/[0.03] hover:border-destructive/50'
          : 'border-border hover:border-brand-purple/40'
      )}
    >
      {/* Hora grande */}
      <div className="text-center shrink-0 w-16">
        <div
          className={cn(
            'font-display font-bold text-2xl leading-none',
            overdue ? 'text-destructive' : 'text-brand-dark'
          )}
        >
          {fmtHour(prospect.callback_at)}
        </div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">
          {relativeTime(prospect.callback_at)}
        </div>
      </div>

      <div className="h-12 w-px bg-border shrink-0" />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <h3 className="font-semibold text-brand-dark truncate">
            {prospect.title}
          </h3>
          {overdue && (
            <Badge variant="destructive">
              <AlertTriangle className="h-3 w-3" />
              Vencido
            </Badge>
          )}
          {prospect.intentos > 1 && (
            <span className="text-[10px] font-mono text-muted-foreground">
              ×{prospect.intentos} intentos
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
          {phone && (
            <span className="flex items-center gap-1">
              <Phone className="h-3 w-3" /> {phone}
            </span>
          )}
          {prospect.city && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" /> {prospect.city}
            </span>
          )}
          {prospect.category_name && <span>· {prospect.category_name}</span>}
        </div>
        {prospect.callback_notas && (
          <p className="text-xs text-brand-dark/70 mt-1.5 italic line-clamp-1">
            <Clock className="inline h-3 w-3 mr-1" />
            {prospect.callback_notas}
          </p>
        )}
      </div>

      <ChevronRight className="h-5 w-5 text-muted-foreground shrink-0 group-hover:text-brand-purple-dark transition-colors" />
    </button>
  )
}
