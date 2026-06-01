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
  Mail,
  ChevronDown,
  Eye,
  MousePointerClick,
  Reply,
  XCircle,
  Search,
  ExternalLink,
  Copy,
  Download,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, normalizePhoneEs } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import { dialProspect, analyzeCall, ApiError } from '@/lib/sdr/api'
import type {
  AnalyzeResult,
  DatosEnriquecidos,
  EmailItem,
  EmailStatus,
  Prospect,
} from '@/lib/sdr/types'

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
      // Modelo callback API (probado, funciona).
      // El widget WebRTC outbound directo está bloqueado por la PBX
      // (envía INVITE → FAIL inmediato). En cambio el callback API hace:
      //   1) backend → POST /v1/request/callback/
      //   2) Zadarma llama PRIMERO a la extensión 100 (suena en el widget)
      //   3) cuando contestas, Zadarma marca al destino y une las dos patas
      //   4) la conversación queda grabada en la nube + visible en /v1/statistics/pbx/
      // Pre-requisito: la extensión 100 NO debe tener desvío externo activo
      // (si está activo, la pata entrante se la come ElevenLabs y nunca suena
      // en el widget).
      await dialProspect({
        prospect_id: prospect.id,
        phone: normalizedPhone,
      })

      toast.success(
        <span>
          Llamada iniciada. Acepta la llamada entrante en el widget.{' '}
          <strong>Pulsa H o Esc para colgar.</strong>
        </span>,
        { duration: 5000 }
      )
      startCall()
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
          ? err.message
          : 'Error desconocido'
      toast.error(`No pude iniciar la llamada: ${msg}`)
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

          {/* Investiga antes de llamar — quick links */}
          <QuickLinks prospect={prospect} />

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

          {/* Emails enviados */}
          {prospect.emails && prospect.emails.length > 0 && (
            <EmailsCard emails={prospect.emails} />
          )}

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

          {/* Análisis IA de la llamada (grabación → transcripción → resumen + email) */}
          <CallAnalysisCard prospect={prospect} />

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

function EmailsCard({ emails }: { emails: EmailItem[] }) {
  const [openId, setOpenId] = useState<string | null>(emails[0]?.id ?? null)

  const latest = emails[0]
  const daysAgo = latest?.fecha_envio
    ? Math.floor(
        (Date.now() - new Date(latest.fecha_envio).getTime()) / 86400000
      )
    : null

  return (
    <Card className="p-5 border-brand-yellow/40 bg-brand-yellow/[0.06]">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Mail className="h-3.5 w-3.5 text-brand-yellow-hover" />
          <p className="tag-label text-brand-yellow-hover">
            {emails.length === 1
              ? 'Email enviado'
              : `${emails.length} emails enviados`}
          </p>
        </div>
        {daysAgo !== null && (
          <Badge
            variant={daysAgo >= 2 && daysAgo <= 5 ? 'cta' : 'secondary'}
            className="text-[10px]"
          >
            D+{daysAgo} {daysAgo >= 2 && daysAgo <= 5 ? '· sweet spot' : ''}
          </Badge>
        )}
      </div>

      <p className="text-xs text-muted-foreground mb-3">
        Empieza la llamada con{' '}
        <span className="text-brand-dark font-semibold">
          “Te mandé un correo hace {daysAgo} {daysAgo === 1 ? 'día' : 'días'}{' '}
          sobre…”
        </span>{' '}
        — el prospecto lo reconoce.
      </p>

      <ul className="space-y-2">
        {emails.map((email) => {
          const isOpen = openId === email.id
          return (
            <li
              key={email.id}
              className="rounded-xl border border-border bg-card overflow-hidden"
            >
              <button
                onClick={() => setOpenId(isOpen ? null : email.id)}
                className={cn(
                  'w-full text-left p-3 flex items-center gap-3 transition-colors',
                  emailRowBg(email.status)
                )}
              >
                <EmailStatusIcon status={email.status} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <EmailStatusBadge status={email.status} />
                    {email.fecha_envio && (
                      <span className="text-[11px] text-muted-foreground">
                        {formatFecha(email.fecha_envio)}
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-semibold text-brand-dark truncate">
                    {email.asunto || '(sin asunto)'}
                  </div>
                  {email.destino && (
                    <div className="text-[11px] text-muted-foreground truncate">
                      → {email.destino}
                    </div>
                  )}
                </div>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 text-muted-foreground transition-transform',
                    isOpen && 'rotate-180'
                  )}
                />
              </button>
              {isOpen && (email.respuesta || email.cuerpo) && (
                <div className="border-t border-border bg-brand-cream/40 p-4 space-y-3">
                  {email.respuesta && (
                    <div className="rounded-lg border border-success/40 bg-success/[0.08] p-3">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <Reply className="h-3.5 w-3.5 text-success" />
                        <span className="text-[10px] uppercase tracking-wider font-bold text-success">
                          Respondió
                          {email.fecha_respuesta
                            ? ` · ${formatFecha(email.fecha_respuesta)}`
                            : ''}
                        </span>
                      </div>
                      <pre className="text-xs whitespace-pre-wrap font-sans text-brand-dark leading-relaxed">
                        {email.respuesta}
                      </pre>
                    </div>
                  )}
                  {email.cuerpo && (
                    <div>
                      {email.respuesta && (
                        <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-1">
                          Email que le enviamos
                        </p>
                      )}
                      <pre className="text-xs whitespace-pre-wrap font-sans text-brand-dark/90 leading-relaxed">
                        {email.cuerpo}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function EmailStatusBadge({ status }: { status: EmailStatus }) {
  const map: Record<EmailStatus, { label: string; cls: string }> = {
    sent: { label: 'Enviado · sin abrir', cls: 'bg-brand-dark/10 text-brand-dark/70' },
    opened: { label: 'Abierto ✓', cls: 'bg-brand-yellow/30 text-brand-dark border border-brand-yellow' },
    clicked: { label: 'Click en enlace', cls: 'bg-brand-purple/20 text-brand-purple-dark border border-brand-purple/40' },
    replied: { label: 'RESPONDIÓ', cls: 'bg-success/20 text-success border border-success/40 font-bold' },
    bounced: { label: 'Rebotado', cls: 'bg-destructive/15 text-destructive border border-destructive/40' },
    unsubscribed: { label: 'Unsubscribed', cls: 'bg-destructive/15 text-destructive border border-destructive/40' },
  }
  const cfg = map[status] || map.sent
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider font-bold',
        cfg.cls
      )}
    >
      {cfg.label}
    </span>
  )
}

function emailRowBg(status: EmailStatus): string {
  switch (status) {
    case 'replied':
      return 'bg-success/[0.06] hover:bg-success/10'
    case 'opened':
    case 'clicked':
      return 'bg-brand-yellow/[0.08] hover:bg-brand-yellow/15'
    case 'bounced':
    case 'unsubscribed':
      return 'bg-destructive/[0.04] hover:bg-destructive/10'
    default:
      return 'hover:bg-accent'
  }
}

function EmailStatusIcon({ status }: { status: EmailStatus }) {
  const cls = 'h-4 w-4 shrink-0'
  switch (status) {
    case 'replied':
      return <Reply className={cn(cls, 'text-success')} />
    case 'clicked':
      return <MousePointerClick className={cn(cls, 'text-brand-purple')} />
    case 'opened':
      return <Eye className={cn(cls, 'text-brand-yellow-hover')} />
    case 'bounced':
    case 'unsubscribed':
      return <XCircle className={cn(cls, 'text-destructive')} />
    case 'sent':
    default:
      return <Mail className={cn(cls, 'text-muted-foreground')} />
  }
}

function formatFecha(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Madrid',
    })
  } catch {
    return iso
  }
}

// re-export para futuras integraciones
export const callStateClass = cn

// ─── QuickLinks: investiga el negocio antes de descolgar ──────────────────────
function QuickLinks({ prospect }: { prospect: Prospect }) {
  const websiteUrl = prospect.website
    ? prospect.website.startsWith('http')
      ? prospect.website
      : `https://${prospect.website}`
    : null

  // Para Maps y Google: query con título + ciudad (siempre funciona)
  const searchQuery = encodeURIComponent(
    [prospect.title, prospect.city].filter(Boolean).join(' ')
  )
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${searchQuery}`
  const googleUrl = `https://www.google.com/search?q=${searchQuery}`

  const links = [
    websiteUrl && {
      href: websiteUrl,
      label: 'Web',
      sub: websiteUrl
        .replace(/^https?:\/\//, '')
        .replace(/\/$/, '')
        .slice(0, 32),
      icon: Globe,
    },
    {
      href: mapsUrl,
      label: 'Google Maps',
      sub: prospect.city || 'Buscar dirección',
      icon: MapPin,
    },
    {
      href: googleUrl,
      label: 'Buscar en Google',
      sub: 'Reseñas, redes, contexto',
      icon: Search,
    },
  ].filter(Boolean) as { href: string; label: string; sub: string; icon: typeof Globe }[]

  return (
    <div className="flex flex-wrap gap-2">
      {links.map((l) => {
        const Icon = l.icon
        return (
          <a
            key={l.label}
            href={l.href}
            target="_blank"
            rel="noreferrer"
            className="group flex items-center gap-2.5 px-3 py-2 rounded-xl border border-border-strong bg-card hover:border-brand-purple hover:bg-brand-purple/5 transition-all"
          >
            <Icon className="h-4 w-4 text-brand-purple-dark shrink-0" />
            <div className="text-left leading-tight">
              <div className="text-xs font-semibold text-brand-dark">{l.label}</div>
              <div className="text-[10px] text-muted-foreground truncate max-w-[180px]">
                {l.sub}
              </div>
            </div>
            <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity ml-1" />
          </a>
        )
      })}
    </div>
  )
}

// ─── Análisis IA de la llamada: grabación → transcripción → resumen + email ──
function CallAnalysisCard({ prospect }: { prospect: Prospect }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const lastCall = prospect.call_history?.[0]

  async function handleAnalyze() {
    if (!prospect.phone) return
    setLoading(true)
    setError(null)
    try {
      const r = await analyzeCall({
        prospect_id: prospect.id,
        phone: prospect.phone,
        prospect_name: prospect.title,
        disposition: lastCall?.disposition ?? undefined,
        call_record_id: lastCall?.id,
      })
      setResult(r)
      if (!r.ok) setError(r.reason || 'No se encontró la grabación de la llamada')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error al analizar la llamada')
    } finally {
      setLoading(false)
    }
  }

  const a = result?.analysis

  return (
    <Card className="p-5 border-brand-purple/30 bg-brand-purple/[0.04]">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Sparkle className="h-3.5 w-3.5 text-brand-purple-dark" />
          <p className="tag-label text-brand-purple-dark">Análisis de la llamada</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5"
          onClick={handleAnalyze}
          disabled={loading || !prospect.phone}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkle className="h-4 w-4" />
          )}
          {loading ? 'Analizando…' : 'Analizar'}
        </Button>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {a && (
        <div className="space-y-3 text-sm">
          {result?.recording_url && (
            <a
              href={result.recording_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-brand-purple-dark hover:underline"
            >
              <Download className="h-3.5 w-3.5" /> Descargar audio
              {result.seconds ? ` (${fmtDuration(result.seconds)})` : ''}
            </a>
          )}
          {a.resumen && (
            <div>
              <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-1">
                Resumen
              </p>
              <p className="text-brand-dark/90">{a.resumen}</p>
            </div>
          )}
          {a.proximos_pasos.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-1">
                Próximos pasos
              </p>
              <ul className="list-disc pl-4 space-y-0.5 text-brand-dark/90">
                {a.proximos_pasos.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {a.necesita_email && a.email_cuerpo && (
            <div className="rounded-lg border border-brand-yellow/40 bg-brand-yellow/[0.06] p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] uppercase tracking-wider font-bold text-brand-yellow-hover">
                  Email sugerido
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 gap-1"
                  onClick={() =>
                    navigator.clipboard.writeText(
                      `${a.email_asunto}\n\n${a.email_cuerpo}`
                    )
                  }
                >
                  <Copy className="h-3 w-3" /> Copiar
                </Button>
              </div>
              {a.email_asunto && (
                <p className="text-xs font-semibold text-brand-dark mb-1">
                  {a.email_asunto}
                </p>
              )}
              <p className="text-xs whitespace-pre-wrap text-brand-dark/85 leading-relaxed">
                {a.email_cuerpo}
              </p>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
