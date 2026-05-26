'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Phone,
  PhoneOff,
  Globe,
  MapPin,
  User,
  History,
  Star,
  CheckCircle2,
  Calendar as CalIcon,
  Sparkle,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, normalizePhoneEs } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import { dialProspect, ApiError } from '@/lib/sdr/api'
import type { DatosEnriquecidos } from '@/lib/sdr/types'

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

export function CallPanel() {
  const prospect = useCallSessionStore(
    (s) => s.activeProspect ?? s.getActiveProspect()
  )
  const loadingProspect = useCallSessionStore((s) => s.loadingProspect)
  const callState = useCallSessionStore((s) => s.callState)
  const callDurationSec = useCallSessionStore((s) => s.callDurationSec)
  const startCall = useCallSessionStore((s) => s.startCall)
  const endCall = useCallSessionStore((s) => s.endCall)
  const tickDuration = useCallSessionStore((s) => s.tickDuration)

  const [dialing, setDialing] = useState(false)

  // Timer
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  useEffect(() => {
    if (callState === 'in_call') {
      timerRef.current = setInterval(tickDuration, 1000)
      return () => {
        if (timerRef.current) clearInterval(timerRef.current)
      }
    }
  }, [callState, tickDuration])

  if (!prospect) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm bg-brand-cream/30">
        <div className="text-center space-y-2">
          <Phone className="h-8 w-8 text-muted-foreground/40 mx-auto" />
          <p>Selecciona un prospecto de la cola</p>
        </div>
      </div>
    )
  }

  const normalizedPhone = normalizePhoneEs(prospect.phone)
  const canCall = !!normalizedPhone && callState === 'idle' && !dialing

  async function handleCall() {
    if (!normalizedPhone || !prospect) return
    setDialing(true)
    try {
      await dialProspect({ prospect_id: prospect.id, phone: normalizedPhone })
      toast.success(
        <span>
          Tu teléfono Zadarma sonará en breve, descuélgalo. <strong>Cuando termines pulsa H o Esc.</strong>
        </span>,
        { duration: 6000 }
      )
      startCall()
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Error desconocido'
      toast.error(`Zadarma no pudo iniciar la llamada: ${msg}`)
    } finally {
      setDialing(false)
    }
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col h-full bg-brand-cream/40">
      <ScrollArea className="flex-1">
        <div className="p-6 max-w-3xl mx-auto space-y-5">
          {/* Header del prospecto */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 flex-1 min-w-0">
              <p className="tag-label text-brand-purple-dark">
                {prospect.category_name || 'Prospecto'}
              </p>
              <h1 className="font-display text-3xl font-bold text-brand-dark leading-tight">
                {prospect.title}
              </h1>
              <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                {prospect.city && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" />
                    {prospect.city}
                  </span>
                )}
                {prospect.website && (
                  <a
                    href={
                      prospect.website.startsWith('http')
                        ? prospect.website
                        : `https://${prospect.website}`
                    }
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 hover:text-brand-purple transition-colors"
                  >
                    <Globe className="h-3.5 w-3.5" />
                    {prospect.website
                      .replace(/^https?:\/\//, '')
                      .replace(/\/$/, '')}
                  </a>
                )}
              </div>
            </div>

            {/* CTA llamar */}
            <div className="shrink-0">
              {callState === 'in_call' ? (
                <Button
                  onClick={endCall}
                  variant="destructive"
                  size="lg"
                  className="gap-2"
                >
                  <PhoneOff className="h-5 w-5" />
                  Terminar · {fmtDuration(callDurationSec)}
                </Button>
              ) : callState === 'wrap_up' ? (
                <Badge variant="warning" className="text-xs px-3 py-1.5">
                  Registrando...
                </Badge>
              ) : (
                <Button
                  onClick={handleCall}
                  disabled={!canCall}
                  size="lg"
                  variant="cta"
                  data-call-button
                >
                  {dialing ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Phone className="h-5 w-5" />
                  )}
                  <span>
                    {dialing ? 'Llamando...' : normalizedPhone || 'Sin teléfono'}
                  </span>
                </Button>
              )}
            </div>
          </div>

          {/* Status + intentos */}
          <Card className="p-5 grid grid-cols-2 gap-5 text-sm">
            <Field label="Estado">
              <span className="font-semibold text-brand-dark">
                {prospect.estado || '—'}
              </span>
            </Field>
            <Field label="Lane">
              <span className="font-semibold text-brand-dark">
                {prospect.lane || '—'}
              </span>
            </Field>
            <Field label="Intentos previos">
              <span className="font-display font-bold text-brand-dark">
                {prospect.intentos}
              </span>
              {prospect.ultimo_intento && (
                <span className="text-xs text-muted-foreground ml-2">
                  · último {fmtDate(prospect.ultimo_intento)}
                </span>
              )}
            </Field>
            <Field label="Prioridad">
              <span className="font-semibold text-brand-dark">
                {prospect.prioridad || '—'}
              </span>
            </Field>
            {prospect.contacto_nombre && (
              <Field label="Contacto previo">
                <span className="flex items-center gap-1 text-brand-dark">
                  <User className="h-3.5 w-3.5" />
                  {prospect.contacto_nombre}
                </span>
              </Field>
            )}
            {prospect.callback_solicitado && (
              <Field label="Callback solicitado">
                <span className="text-warning-foreground font-semibold">
                  {fmtDate(prospect.callback_solicitado)}
                </span>
              </Field>
            )}
          </Card>

          {/* Notas previas */}
          {prospect.notas && (
            <Card className="p-5">
              <p className="tag-label text-brand-purple-dark mb-2">
                Notas previas
              </p>
              <p className="text-sm whitespace-pre-wrap text-brand-dark/85 leading-relaxed">
                {prospect.notas}
              </p>
            </Card>
          )}

          {/* Datos enriquecidos */}
          {prospect.datos_enriquecidos && (
            <EnrichedDataCard
              data={prospect.datos_enriquecidos}
              bookingOnline={prospect.booking_online}
              score={prospect.score}
              tamano={prospect.tamano}
            />
          )}

          {/* Historial */}
          {prospect.call_history && prospect.call_history.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <History className="h-3.5 w-3.5 text-brand-purple-dark" />
                <p className="tag-label text-brand-purple-dark">
                  Últimas {prospect.call_history.length} llamadas
                </p>
              </div>
              <ul className="space-y-3">
                {prospect.call_history.map((c) => (
                  <li
                    key={c.id}
                    className="text-sm border-l-2 border-brand-purple/30 pl-3"
                  >
                    <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                      <CalIcon className="h-3 w-3" />
                      {fmtDate(c.fecha)}
                      <span>·</span>
                      <Badge variant="outline">
                        {c.disposition || '—'}
                      </Badge>
                      {c.buying_signal && c.buying_signal !== 'N/A' && (
                        <Badge variant="secondary">{c.buying_signal}</Badge>
                      )}
                      {c.duracion_seg ? (
                        <span className="text-[10px]">
                          · {fmtDuration(c.duracion_seg)}
                        </span>
                      ) : null}
                    </div>
                    {c.notas && (
                      <p className="mt-1.5 text-brand-dark/80 text-sm whitespace-pre-wrap">
                        {c.notas}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {loadingProspect && (
            <div className="text-xs text-muted-foreground text-center">
              Cargando detalle…
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
        {label}
      </p>
      <div className="text-sm">{children}</div>
    </div>
  )
}

function EnrichedDataCard({
  data,
  bookingOnline,
  score,
  tamano,
}: {
  data: DatosEnriquecidos
  bookingOnline: boolean
  score: number | null
  tamano: string | null
}) {
  const resenas =
    data.resenas ??
    (typeof data.reviews_count === 'number' ? data.reviews_count : undefined)
  const rating = data.rating
  const redesRaw = Array.isArray(data.redes)
    ? data.redes
    : Array.isArray(data.redes_sociales)
    ? data.redes_sociales
    : []
  const servicios = Array.isArray(data.servicios) ? data.servicios : []
  // Acepta {places: {opening_hours_text}} también
  const places = (data.places as { opening_hours_text?: string } | undefined) || {}
  const horario = (data.horario as string | undefined) || places.opening_hours_text

  const chips: {
    label: string
    icon?: React.ReactNode
    tone: 'success' | 'neutral' | 'warning' | 'purple'
  }[] = []
  if (bookingOnline)
    chips.push({
      label: 'Reserva online',
      icon: <CheckCircle2 className="h-3 w-3" />,
      tone: 'success',
    })
  if (typeof resenas === 'number')
    chips.push({
      label: `${resenas} reseñas`,
      icon: <Star className="h-3 w-3" />,
      tone: 'neutral',
    })
  if (typeof rating === 'number')
    chips.push({
      label: `${rating.toFixed(1)}★`,
      tone: rating >= 4.3 ? 'success' : 'neutral',
    })
  if (tamano) chips.push({ label: `Tamaño: ${tamano}`, tone: 'neutral' })
  if (typeof score === 'number')
    chips.push({
      label: `Score ${score}`,
      tone: score >= 70 ? 'success' : score >= 40 ? 'neutral' : 'warning',
    })
  if (Array.isArray(redesRaw) && redesRaw.length > 0)
    chips.push({ label: `${redesRaw.length} redes`, tone: 'purple' })

  if (chips.length === 0 && !servicios.length && !horario) return null

  return (
    <Card className="p-5 border-brand-purple/30 bg-brand-purple/[0.04]">
      <div className="flex items-center gap-2 mb-3">
        <Sparkle className="h-3.5 w-3.5 text-brand-purple-dark" />
        <p className="tag-label text-brand-purple-dark">Inteligencia previa</p>
      </div>
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {chips.map((chip, i) => (
            <Badge
              key={i}
              variant={
                chip.tone === 'success'
                  ? 'success'
                  : chip.tone === 'warning'
                  ? 'warning'
                  : chip.tone === 'purple'
                  ? 'default'
                  : 'secondary'
              }
              className="gap-1"
            >
              {chip.icon}
              {chip.label}
            </Badge>
          ))}
        </div>
      )}
      {servicios.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1.5">
            Servicios detectados
          </p>
          <div className="flex flex-wrap gap-1">
            {servicios.slice(0, 10).map((s, i) => (
              <Badge key={i} variant="outline">
                {String(s)}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {horario && (
        <p className="text-xs text-brand-dark/70">
          <span className="font-bold text-brand-dark">Horario:</span>{' '}
          {String(horario)}
        </p>
      )}
      {redesRaw.length > 0 && (
        <p className="text-xs text-brand-dark/70 mt-1">
          <span className="font-bold text-brand-dark">Redes:</span>{' '}
          {redesRaw.map(String).join(', ')}
        </p>
      )}
    </Card>
  )
}

// re-export para futuras integraciones
export const callStateClass = cn
