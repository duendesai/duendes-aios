'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  AlertTriangle,
  Calendar,
  Clock,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MiniWeekCalendar } from '@/components/agenda/MiniWeekCalendar'
import { AgendaTimeline } from '@/components/agenda/AgendaTimeline'
import { fetchAgenda, ApiError } from '@/lib/sdr/api'
import type { AgendaResponse } from '@/lib/sdr/types'

function getMondayOf(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1))
  d.setHours(0, 0, 0, 0)
  return d
}

export default function AgendaPage() {
  const [data, setData] = useState<AgendaResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [weekStart, setWeekStart] = useState<Date>(() => getMondayOf(new Date()))
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    try {
      const d = await fetchAgenda(60)
      setData(d)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Error de red'
      toast.error(`No se pudo cargar la agenda: ${msg}`)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Auto-refresh cada 60s para que aparezcan los callbacks que vencen
  useEffect(() => {
    const id = setInterval(() => load(true), 60_000)
    return () => clearInterval(id)
  }, [load])

  const allCallbacks = useMemo(() => {
    if (!data) return []
    return [...data.overdue, ...data.today, ...data.week, ...data.later]
  }, [data])

  return (
    <div className="h-full flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <header className="h-16 shrink-0 border-b border-border px-6 flex items-center justify-between bg-card">
        <div>
          <p className="tag-label text-brand-purple-dark">Agenda</p>
          <h1 className="font-display font-bold text-brand-dark text-base leading-tight mt-0.5">
            Próximos callbacks
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <div className="flex items-center gap-4 text-sm mr-2">
              {data.totals.overdue > 0 && (
                <Stat
                  icon={<AlertTriangle className="h-4 w-4 text-destructive" />}
                  label="Vencidos"
                  value={data.totals.overdue}
                  tone="destructive"
                />
              )}
              <Stat
                icon={<Clock className="h-4 w-4 text-brand-yellow-hover" />}
                label="Hoy"
                value={data.totals.today}
                tone="cta"
              />
              <Stat
                icon={<Calendar className="h-4 w-4 text-brand-purple" />}
                label="7 días"
                value={data.totals.week}
              />
              <Stat label="Total" value={data.totals.all} tone="muted" />
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => load(true)}
            disabled={refreshing}
            title="Recargar"
          >
            <RefreshCw
              className={refreshing ? 'animate-spin h-4 w-4' : 'h-4 w-4'}
            />
          </Button>
        </div>
      </header>

      {/* Layout 2 columnas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Izquierda: mini calendario */}
        <aside className="w-80 shrink-0 border-r border-border bg-card p-4 overflow-y-auto">
          <MiniWeekCalendar
            weekStart={weekStart}
            selectedDay={selectedDay}
            onSelectDay={setSelectedDay}
            onWeekChange={setWeekStart}
            callbacks={allCallbacks}
          />

          {selectedDay && (
            <div className="mt-4 p-3 rounded-xl bg-brand-purple/10 border border-brand-purple/20 text-xs space-y-2">
              <p className="font-semibold text-brand-purple-dark">
                Filtrando:{' '}
                {selectedDay.toLocaleDateString('es-ES', {
                  weekday: 'long',
                  day: '2-digit',
                  month: 'short',
                })}
              </p>
              <button
                onClick={() => setSelectedDay(null)}
                className="text-brand-purple-dark hover:underline"
              >
                Quitar filtro
              </button>
            </div>
          )}

          {/* Tip */}
          <div className="mt-6 p-3 rounded-xl bg-brand-cream border border-border text-xs text-muted-foreground space-y-1">
            <p className="font-semibold text-brand-dark">¿Cómo funciona?</p>
            <p>
              Cuando marques un prospecto como{' '}
              <span className="font-semibold">Rellamar</span> con fecha, aparecerá
              aquí. El prospecto vuelve a tu cola en{' '}
              <span className="font-semibold">/sdr</span> cuando llegue su hora.
            </p>
          </div>
        </aside>

        {/* Derecha: timeline */}
        <main className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-6 max-w-3xl mx-auto">
              {loading ? (
                <div className="py-20 text-center text-muted-foreground">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3 text-brand-purple" />
                  Cargando agenda...
                </div>
              ) : !data ? (
                <Card className="p-8 text-center text-sm text-muted-foreground">
                  No se pudo cargar la agenda.
                </Card>
              ) : (
                <AgendaTimeline
                  data={data}
                  selectedDay={selectedDay}
                  onClearFilter={() => setSelectedDay(null)}
                />
              )}
            </div>
          </ScrollArea>
        </main>
      </div>
    </div>
  )
}

function Stat({
  icon,
  label,
  value,
  tone,
}: {
  icon?: React.ReactNode
  label: string
  value: number
  tone?: 'destructive' | 'cta' | 'muted'
}) {
  if (value === 0 && tone !== 'cta') return null
  return (
    <div className="flex items-center gap-1.5">
      {icon}
      <div className="leading-tight">
        <div
          className={
            tone === 'destructive'
              ? 'font-display font-bold text-destructive text-base'
              : tone === 'cta'
              ? 'font-display font-bold text-brand-yellow-hover text-base'
              : tone === 'muted'
              ? 'font-display font-bold text-muted-foreground text-base'
              : 'font-display font-bold text-brand-dark text-base'
          }
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
