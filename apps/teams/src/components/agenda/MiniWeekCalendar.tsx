'use client'

import { useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { AgendaProspect } from '@/lib/sdr/types'

interface MiniWeekCalendarProps {
  /** Lunes de la semana visible (00:00 local) */
  weekStart: Date
  selectedDay: Date | null
  onSelectDay: (day: Date | null) => void
  onWeekChange: (newWeekStart: Date) => void
  callbacks: AgendaProspect[]
}

const WEEKDAY_LABELS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const TZ = 'Europe/Madrid'

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function isToday(d: Date): boolean {
  return sameDay(d, new Date())
}

function isOverdue(d: Date): boolean {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return d < today
}

export function MiniWeekCalendar({
  weekStart,
  selectedDay,
  onSelectDay,
  onWeekChange,
  callbacks,
}: MiniWeekCalendarProps) {
  const days = useMemo(() => {
    return Array.from({ length: 7 }).map((_, i) => {
      const d = new Date(weekStart)
      d.setDate(d.getDate() + i)
      d.setHours(0, 0, 0, 0)
      return d
    })
  }, [weekStart])

  // Cuenta de callbacks por día (key = YYYY-MM-DD local)
  const countsByDay = useMemo(() => {
    const map = new Map<string, number>()
    for (const c of callbacks) {
      const d = new Date(c.callback_at)
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      map.set(key, (map.get(key) || 0) + 1)
    }
    return map
  }, [callbacks])

  const monthLabel = useMemo(() => {
    const lastDay = days[6]
    if (days[0].getMonth() === lastDay.getMonth()) {
      return days[0].toLocaleDateString('es-ES', {
        month: 'long',
        year: 'numeric',
        timeZone: TZ,
      })
    }
    return `${days[0].toLocaleDateString('es-ES', {
      month: 'short',
    })} – ${lastDay.toLocaleDateString('es-ES', {
      month: 'short',
      year: 'numeric',
    })}`
  }, [days])

  function shiftWeek(delta: number) {
    const next = new Date(weekStart)
    next.setDate(next.getDate() + delta * 7)
    onWeekChange(next)
  }

  function goToday() {
    const today = new Date()
    const day = today.getDay()
    const monday = new Date(today)
    monday.setDate(today.getDate() - (day === 0 ? 6 : day - 1))
    monday.setHours(0, 0, 0, 0)
    onWeekChange(monday)
    onSelectDay(today)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-display font-bold text-brand-dark capitalize">
            {monthLabel}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
            Semana
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => shiftWeek(-1)}
            title="Semana anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={goToday}>
            Hoy
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => shiftWeek(1)}
            title="Semana siguiente"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1.5">
        {WEEKDAY_LABELS.map((l) => (
          <div
            key={l}
            className="text-center text-[10px] uppercase tracking-wider font-semibold text-muted-foreground"
          >
            {l}
          </div>
        ))}
        {days.map((d) => {
          const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
          const count = countsByDay.get(key) || 0
          const selected = selectedDay && sameDay(d, selectedDay)
          const today = isToday(d)
          const past = isOverdue(d)

          return (
            <button
              key={d.toISOString()}
              onClick={() => onSelectDay(selected ? null : d)}
              className={cn(
                'group relative h-12 rounded-lg flex flex-col items-center justify-center text-sm transition-all border',
                selected
                  ? 'bg-brand-purple text-white border-brand-purple shadow-sm'
                  : today
                  ? 'border-brand-yellow bg-brand-yellow/15 text-brand-dark hover:bg-brand-yellow/30'
                  : past
                  ? 'border-transparent text-brand-dark/40 hover:bg-accent'
                  : 'border-transparent text-brand-dark hover:bg-accent'
              )}
            >
              <span className="font-display font-bold leading-none">
                {d.getDate()}
              </span>
              {count > 0 && (
                <span
                  className={cn(
                    'mt-1 h-1.5 w-1.5 rounded-full',
                    selected
                      ? 'bg-white'
                      : count > 3
                      ? 'bg-destructive'
                      : 'bg-brand-purple'
                  )}
                  aria-label={`${count} callbacks`}
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
