'use client'

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Calendar, Loader2, ExternalLink, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { cn, normalizePhoneEs } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import { bookSlot, fetchSlots, ApiError } from '@/lib/sdr/api'
import type { Slot } from '@/lib/sdr/types'

const TZ = 'Europe/Madrid'

function fmtDay(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('es-ES', {
    weekday: 'long',
    day: '2-digit',
    month: 'short',
    timeZone: TZ,
  })
}

function fmtHour(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TZ,
  })
}

function dayKey(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: TZ,
  })
}

export function BookingPanel() {
  const prospect = useCallSessionStore(
    (s) => s.activeProspect ?? s.getActiveProspect()
  )
  const showBooking = useCallSessionStore((s) => s.showBooking)
  const closeBooking = useCallSessionStore((s) => s.closeBooking)
  const finishWrapUp = useCallSessionStore((s) => s.finishWrapUp)
  const nextProspect = useCallSessionStore((s) => s.nextProspect)
  const setBookingPending = useCallSessionStore((s) => s.setBookingPending)
  const bookingPending = useCallSessionStore((s) => s.bookingPending)

  const [slots, setSlots] = useState<Slot[]>([])
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [slotsError, setSlotsError] = useState<string | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)

  const [attendeeName, setAttendeeName] = useState('')
  const [attendeeEmail, setAttendeeEmail] = useState('')
  const [attendeePhone, setAttendeePhone] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    if (!showBooking || !prospect) return
    setSelectedSlot(null)
    setAttendeeName(prospect.contacto_nombre ?? '')
    setAttendeeEmail('')
    setAttendeePhone(normalizePhoneEs(prospect.phone) ?? '')
    setEmpresa(prospect.title ?? '')
    setNotes('')
    setSlotsError(null)
    setLoadingSlots(true)
    fetchSlots(7)
      .then((data) => setSlots(data.slots))
      .catch((err) => {
        const msg = err instanceof ApiError ? err.message : 'Error desconocido'
        setSlotsError(msg)
      })
      .finally(() => setLoadingSlots(false))
  }, [showBooking, prospect?.id])

  const slotsByDay = useMemo(() => {
    const groups = new Map<string, Slot[]>()
    for (const s of slots) {
      const key = dayKey(s.start)
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(s)
    }
    return Array.from(groups.entries()).sort((a, b) => {
      const da = new Date(a[1][0].start).getTime()
      const db = new Date(b[1][0].start).getTime()
      return da - db
    })
  }, [slots])

  if (!showBooking || !prospect) return null

  function handleSkip() {
    closeBooking()
    finishWrapUp('booked')
    toast.message('Booking saltado · llamada quedó como Agendada en Airtable')
    nextProspect()
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!selectedSlot) {
      toast.error('Selecciona un hueco primero')
      return
    }
    if (!attendeeEmail.trim()) {
      toast.error('Necesitamos el email del prospecto para enviar la invitación')
      return
    }

    if (!prospect) return
    setBookingPending(true)
    try {
      const booking = await bookSlot({
        prospect_id: prospect.id,
        slot_start: selectedSlot,
        attendee_name: attendeeName.trim() || 'Sin nombre',
        attendee_email: attendeeEmail.trim(),
        attendee_phone: attendeePhone.trim() || null,
        empresa: empresa.trim() || prospect.title,
        sector: prospect.category_name,
        notes: notes.trim() || null,
      })
      toast.success(
        <>
          Demo agendada · {empresa || prospect.title} · {fmtHour(booking.start)}
          {booking.meeting_url && (
            <a
              href={booking.meeting_url}
              target="_blank"
              rel="noreferrer"
              className="ml-2 underline text-xs"
            >
              abrir <ExternalLink className="inline h-3 w-3" />
            </a>
          )}
        </>
      )
      closeBooking()
      finishWrapUp('booked')
      nextProspect()
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Error desconocido'
      toast.error(`No se pudo agendar: ${msg}`)
    } finally {
      setBookingPending(false)
    }
  }

  return (
    <Card className="p-6 border-success/30 bg-success/[0.04]">
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="tag-label text-success">Demo agendada</p>
          <h2 className="font-display text-xl font-bold text-brand-dark mt-1">
            Elegir hueco en Cal.com
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Evento: Demo Gratuita · 30 min
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={handleSkip}>
          <X className="h-4 w-4 mr-1" /> Saltar
        </Button>
      </div>

      {loadingSlots ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-brand-purple" />
          Cargando huecos...
        </div>
      ) : slotsError ? (
        <div className="py-4 text-sm space-y-2">
          <p className="text-destructive">
            No se pudieron cargar los huecos: {slotsError}
          </p>
          <Button size="sm" variant="outline" onClick={handleSkip}>
            Saltar y avanzar
          </Button>
        </div>
      ) : slots.length === 0 ? (
        <div className="py-4 text-sm space-y-3">
          <p className="text-muted-foreground">
            No hay huecos disponibles en los próximos 7 días.
          </p>
          <Button size="sm" variant="outline" onClick={handleSkip}>
            Saltar y avanzar
          </Button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label>Elige hueco</Label>
            <div className="max-h-64 overflow-y-auto pr-1 space-y-3 rounded-xl border border-border bg-card p-3">
              {slotsByDay.map(([day, daySlots]) => (
                <div key={day}>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1.5 capitalize">
                    {fmtDay(daySlots[0].start)}
                  </p>
                  <div className="grid grid-cols-4 gap-1.5">
                    {daySlots.map((s) => {
                      const selected = selectedSlot === s.start
                      return (
                        <button
                          key={s.start}
                          type="button"
                          onClick={() => setSelectedSlot(s.start)}
                          className={cn(
                            'text-xs px-2 py-1.5 rounded-lg border font-semibold transition-all',
                            selected
                              ? 'border-success bg-success/15 text-success shadow-sm'
                              : 'border-border-strong text-brand-dark/70 hover:border-success/50 hover:text-brand-dark'
                          )}
                        >
                          {fmtHour(s.start)}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="att-name">Nombre completo</Label>
              <Input
                id="att-name"
                value={attendeeName}
                onChange={(e) => setAttendeeName(e.target.value)}
                placeholder="Nombre del decisor"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="att-email">Email *</Label>
              <Input
                id="att-email"
                type="email"
                value={attendeeEmail}
                onChange={(e) => setAttendeeEmail(e.target.value)}
                required
                placeholder="email@empresa.es"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="att-phone">Teléfono</Label>
              <Input
                id="att-phone"
                value={attendeePhone}
                onChange={(e) => setAttendeePhone(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="att-empresa">Empresa</Label>
              <Input
                id="att-empresa"
                value={empresa}
                onChange={(e) => setEmpresa(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="att-notes">Notas (opcional)</Label>
            <Input
              id="att-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Contexto que verás antes de la llamada"
            />
          </div>

          <div className="flex items-center justify-between gap-2 pt-2">
            <p className="text-[11px] text-muted-foreground">
              Crea booking en Cal.com + lead en CRM + actualiza Airtable.
            </p>
            <Button
              type="submit"
              variant="cta"
              size="lg"
              disabled={bookingPending || !selectedSlot || !attendeeEmail.trim()}
            >
              {bookingPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Calendar className="h-4 w-4" />
              )}
              <span>{bookingPending ? 'Agendando...' : 'Confirmar demo'}</span>
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}
