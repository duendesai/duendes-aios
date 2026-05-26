'use client'

import { useState, useEffect, type FormEvent } from 'react'
import { Loader2, Save } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import { submitResult, ApiError } from '@/lib/sdr/api'
import {
  BUYING_SIGNAL_OPTIONS,
  CONTACTO_OPTIONS,
  DISPOSITION_OPTIONS,
  MOTIVO_FIN_OPTIONS,
  MOTIVO_PERDIDA_OPTIONS,
  NEGATIVE_DISPOSITIONS,
  OBJECIONES_OPTIONS,
} from '@/lib/sdr/enums'
import type {
  BuyingSignal,
  ContactoAlcanzado,
  Disposition,
  MotivoFin,
  MotivoPerdida,
  Objecion,
} from '@/lib/sdr/types'

export function CallForm() {
  const prospect = useCallSessionStore(
    (s) => s.activeProspect ?? s.getActiveProspect()
  )
  const callDurationSec = useCallSessionStore((s) => s.callDurationSec)
  const finishWrapUp = useCallSessionStore((s) => s.finishWrapUp)
  const nextProspect = useCallSessionStore((s) => s.nextProspect)
  const openBooking = useCallSessionStore((s) => s.openBooking)

  // Form state
  const [disposition, setDisposition] = useState<Disposition | ''>('')
  const [contacto, setContacto] = useState<ContactoAlcanzado | ''>('')
  const [contactoNombre, setContactoNombre] = useState('')
  const [buying, setBuying] = useState<BuyingSignal>('N/A')
  const [motivoFin, setMotivoFin] = useState<MotivoFin | ''>('')
  const [motivoPerdida, setMotivoPerdida] = useState<MotivoPerdida | ''>('')
  const [objeciones, setObjeciones] = useState<Set<Objecion>>(new Set())
  const [discovery, setDiscovery] = useState(false)
  const [notas, setNotas] = useState('')
  const [transcripcion, setTranscripcion] = useState('')
  const [callbackAt, setCallbackAt] = useState('')
  const [callbackNotas, setCallbackNotas] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset al cambiar prospecto
  useEffect(() => {
    setDisposition('')
    setContacto('')
    setContactoNombre(prospect?.contacto_nombre ?? '')
    setBuying('N/A')
    setMotivoFin('')
    setMotivoPerdida('')
    setObjeciones(new Set())
    setDiscovery(false)
    setNotas('')
    setTranscripcion('')
    setCallbackAt('')
    setCallbackNotas('')
    setError(null)
  }, [prospect?.id])

  if (!prospect) return null

  const needsMotivoPerdida =
    !!disposition &&
    NEGATIVE_DISPOSITIONS.includes(disposition as Disposition)
  const isCallback = disposition === 'Rellamar'
  const isAgendada = disposition === 'Agendada'

  function toggleObjecion(value: Objecion) {
    setObjeciones((prev) => {
      const next = new Set(prev)
      if (next.has(value)) next.delete(value)
      else next.add(value)
      return next
    })
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (!disposition) {
      setError('Selecciona qué pasó en la llamada.')
      return
    }
    if (isCallback && !callbackAt) {
      setError('Rellamar requiere fecha y hora del callback.')
      return
    }
    if (needsMotivoPerdida && !motivoPerdida) {
      setError(`Indica el motivo para "${disposition}".`)
      return
    }

    if (!prospect) return
    setSubmitting(true)
    try {
      const callbackIso = callbackAt
        ? new Date(callbackAt).toISOString()
        : undefined

      await submitResult({
        prospect_id: prospect.id,
        disposition: disposition as Disposition,
        contacto_alcanzado: (contacto || null) as ContactoAlcanzado | null,
        contacto_nombre: contactoNombre || null,
        buying_signal: buying,
        motivo_fin: motivoFin || undefined,
        motivo_perdida: needsMotivoPerdida ? (motivoPerdida as MotivoPerdida) : null,
        objeciones: Array.from(objeciones),
        discovery_completo: discovery,
        notas,
        transcripcion,
        duracion_seg: callDurationSec,
        callback_at: callbackIso ?? null,
        callback_notas: callbackNotas || null,
      })

      if (isAgendada) {
        toast.success('Llamada registrada. Vamos a agendar la demo.')
        openBooking()
      } else {
        const outcome = isCallback
          ? 'callback'
          : needsMotivoPerdida
          ? 'lost'
          : 'no_contact'
        finishWrapUp(outcome as 'callback' | 'lost' | 'no_contact')
        toast.success('Resultado guardado · siguiente prospecto')
        nextProspect()
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Error desconocido'
      setError(msg)
      toast.error(`No se pudo guardar: ${msg}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="p-6 border-brand-purple/30">
      <form onSubmit={onSubmit} className="space-y-5" data-call-form>
        <div className="flex items-baseline justify-between">
          <div>
            <p className="tag-label text-brand-purple-dark">
              Registrar llamada
            </p>
            <h2 className="font-display text-xl font-bold text-brand-dark mt-1">
              ¿Qué pasó?
            </h2>
          </div>
          <span className="text-xs text-muted-foreground">
            Duración:{' '}
            <span className="font-mono font-semibold text-brand-dark">
              {formatDur(callDurationSec)}
            </span>
          </span>
        </div>

        {/* Disposition */}
        <div className="space-y-2">
          <Label>Resultado *</Label>
          <div className="grid grid-cols-3 gap-1.5">
            {DISPOSITION_OPTIONS.map((opt, i) => {
              const selected = disposition === opt.value
              return (
                <button
                  key={opt.value}
                  type="button"
                  data-disposition={opt.value}
                  onClick={() => setDisposition(opt.value)}
                  className={cn(
                    'text-xs px-2.5 py-2 rounded-lg border transition-all text-left font-semibold',
                    selected
                      ? 'border-brand-purple bg-brand-purple/10 text-brand-purple-dark shadow-sm'
                      : 'border-border-strong text-brand-dark/60 bg-card hover:border-brand-purple/40 hover:text-brand-dark',
                    opt.tone === 'positive' &&
                      selected &&
                      'border-success bg-success/10 text-success',
                    opt.tone === 'negative' &&
                      selected &&
                      'border-destructive/60 bg-destructive/10 text-destructive',
                    opt.tone === 'warning' &&
                      selected &&
                      'border-warning/60 bg-warning/15 text-warning-foreground'
                  )}
                >
                  <span className="text-[9px] text-muted-foreground mr-1 font-mono">
                    {i + 1}
                  </span>
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Contacto + buying signal */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Quién contestó</Label>
            <SelectNative
              value={contacto}
              onChange={(v) => setContacto(v as ContactoAlcanzado | '')}
              placeholder="— Opcional —"
              options={CONTACTO_OPTIONS}
              allowEmpty
            />
          </div>
          <div className="space-y-2">
            <Label>Buying signal</Label>
            <SelectNative
              value={buying}
              onChange={(v) => setBuying(v as BuyingSignal)}
              options={BUYING_SIGNAL_OPTIONS}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Nombre del contacto (opcional)</Label>
          <Input
            value={contactoNombre}
            onChange={(e) => setContactoNombre(e.target.value)}
            placeholder="ej. María, la recepcionista"
          />
        </div>

        <div className="space-y-2">
          <Label>Motivo fin (técnico)</Label>
          <SelectNative
            value={motivoFin}
            onChange={(v) => setMotivoFin(v as MotivoFin | '')}
            placeholder="— No aplica —"
            options={MOTIVO_FIN_OPTIONS}
            allowEmpty
          />
        </div>

        {needsMotivoPerdida && (
          <div className="space-y-2 p-3 rounded-xl border border-destructive/30 bg-destructive/5">
            <Label className="text-destructive font-bold">
              Motivo de la pérdida *
            </Label>
            <SelectNative
              value={motivoPerdida}
              onChange={(v) => setMotivoPerdida(v as MotivoPerdida)}
              placeholder="— Selecciona —"
              options={MOTIVO_PERDIDA_OPTIONS}
            />
          </div>
        )}

        {isCallback && (
          <div className="space-y-3 p-3 rounded-xl border border-warning/30 bg-warning/5">
            <div className="space-y-2">
              <Label className="text-warning-foreground font-bold">
                Cuándo rellamar *
              </Label>
              <Input
                type="datetime-local"
                value={callbackAt}
                onChange={(e) => setCallbackAt(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Notas del callback</Label>
              <Input
                value={callbackNotas}
                onChange={(e) => setCallbackNotas(e.target.value)}
                placeholder="ej. Preguntar por Marta a las 16h"
              />
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label>Objeciones detectadas</Label>
          <div className="grid grid-cols-2 gap-1.5">
            {OBJECIONES_OPTIONS.map((o) => (
              <label
                key={o.value}
                className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent rounded-lg px-2 py-1.5"
              >
                <Checkbox
                  checked={objeciones.has(o.value)}
                  onCheckedChange={() => toggleObjecion(o.value)}
                />
                <span>{o.label}</span>
              </label>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={discovery}
            onCheckedChange={(v) => setDiscovery(v === true)}
          />
          <span className="text-brand-dark">
            Discovery completado · entendí el dolor real
          </span>
        </label>

        <Separator />

        <div className="space-y-2">
          <Label>Notas (contexto post-llamada)</Label>
          <Textarea
            value={notas}
            onChange={(e) => setNotas(e.target.value)}
            placeholder="Qué dolor mencionó, próximo paso, contexto..."
            rows={3}
          />
        </div>

        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground hover:text-brand-dark transition-colors">
            + Transcripción manual (opcional)
          </summary>
          <Textarea
            value={transcripcion}
            onChange={(e) => setTranscripcion(e.target.value)}
            placeholder="Transcripción literal de algo importante..."
            rows={4}
            className="mt-2"
          />
        </details>

        {error && (
          <div className="text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded-lg p-3">
            {error}
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-2">
          <p className="text-[11px] text-muted-foreground">
            Atajo:{' '}
            <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[10px] font-mono font-bold">
              S
            </kbd>{' '}
            para guardar
          </p>
          <Button type="submit" disabled={submitting} variant={isAgendada ? 'cta' : 'default'} size="lg">
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            <span>
              {submitting
                ? 'Guardando...'
                : isAgendada
                ? 'Guardar y agendar demo'
                : 'Guardar resultado'}
            </span>
          </Button>
        </div>
      </form>
    </Card>
  )
}

function SelectNative({
  value,
  onChange,
  placeholder,
  options,
  allowEmpty = false,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  options: { value: string; label: string }[]
  allowEmpty?: boolean
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-10 rounded-xl border border-border-strong bg-input px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
    >
      {(allowEmpty || !value) && placeholder && (
        <option value="">{placeholder}</option>
      )}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

function formatDur(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
