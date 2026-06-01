'use client'

import { RefreshCw, MapPin, Inbox, Mail } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { useCallSessionStore } from '@/store/useCallSessionStore'

interface CallQueueProps {
  onReload: () => void
}

const ESTADO_BADGE: Record<
  string,
  { label: string; variant: 'secondary' | 'warning' | 'success' | 'destructive' | 'outline' | 'default' }
> = {
  Pendiente: { label: 'Nuevo', variant: 'secondary' },
  Rellamar: { label: 'Rellamar', variant: 'warning' },
  'No contesta': { label: 'No contestó', variant: 'warning' },
  Contestador: { label: 'Buzón', variant: 'warning' },
  Comunica: { label: 'Comunica', variant: 'warning' },
  Gatekeeper: { label: 'Gatekeeper', variant: 'warning' },
  'Info solicitada': { label: 'Info enviada', variant: 'outline' },
  'Interés cálido': { label: 'Cálido', variant: 'default' },
}

export function CallQueue({ onReload }: CallQueueProps) {
  const prospects = useCallSessionStore((s) => s.prospects)
  const activeId = useCallSessionStore((s) => s.activeId)
  const loadingQueue = useCallSessionStore((s) => s.loadingQueue)
  const queueError = useCallSessionStore((s) => s.queueError)
  const selectProspect = useCallSessionStore((s) => s.selectProspect)

  return (
    <div className="w-80 shrink-0 border-r border-border bg-card flex flex-col h-full">
      <div className="h-14 px-4 border-b border-border flex items-center justify-between">
        <div>
          <p className="tag-label text-brand-purple-dark">Cola</p>
          <p className="font-display font-bold text-brand-dark text-sm leading-tight">
            {prospects.length} prospectos
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onReload}
          disabled={loadingQueue}
          title="Recargar cola"
        >
          <RefreshCw className={cn('h-4 w-4', loadingQueue && 'animate-spin')} />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        {loadingQueue && prospects.length === 0 ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="h-20 rounded-xl bg-muted/40 animate-pulse"
              />
            ))}
          </div>
        ) : queueError ? (
          <div className="p-4 text-sm space-y-3">
            <p className="text-destructive">Error cargando la cola:</p>
            <p className="text-muted-foreground text-xs">{queueError}</p>
            <Button variant="outline" size="sm" onClick={onReload}>
              Reintentar
            </Button>
          </div>
        ) : prospects.length === 0 ? (
          <div className="p-8 text-center text-sm space-y-3">
            <Inbox className="h-8 w-8 text-muted-foreground mx-auto" />
            <p className="font-display font-bold text-brand-dark">Cola vacía</p>
            <p className="text-muted-foreground text-xs">
              No quedan prospectos pendientes. Buen trabajo.
            </p>
          </div>
        ) : (
          <ul className="p-2 space-y-1">
            {prospects.map((p) => {
              const isActive = p.id === activeId
              const badge = (p.estado && ESTADO_BADGE[p.estado]) || {
                label: p.estado || '—',
                variant: 'outline' as const,
              }
              return (
                <li key={p.id}>
                  <button
                    onClick={() => selectProspect(p.id)}
                    className={cn(
                      'w-full text-left p-3 rounded-xl transition-all block border',
                      isActive
                        ? 'bg-brand-purple/8 border-brand-purple/30 shadow-sm'
                        : 'border-transparent hover:bg-accent'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="font-semibold text-sm text-brand-dark line-clamp-2 flex-1 leading-tight">
                        {p.title}
                      </div>
                      <Badge variant={badge.variant} className="shrink-0">{badge.label}</Badge>
                    </div>
                    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1 truncate">
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{p.city || 'Sin ciudad'}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {p.last_email && p.last_email.days_ago !== null && (
                          <span
                            className={cn(
                              'inline-flex items-center gap-0.5 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded',
                              p.last_email.status === 'replied'
                                ? 'bg-success/20 text-success'
                                : p.last_email.status === 'opened' || p.last_email.status === 'clicked'
                                ? 'bg-brand-yellow/30 text-brand-dark'
                                : p.last_email.status === 'bounced' || p.last_email.status === 'unsubscribed'
                                ? 'bg-destructive/15 text-destructive'
                                : 'bg-muted text-muted-foreground'
                            )}
                            title={`Email enviado hace ${p.last_email.days_ago}d · ${p.last_email.status}`}
                          >
                            <Mail className="h-3 w-3" />
                            D+{p.last_email.days_ago}
                          </span>
                        )}
                        {p.intentos > 0 && (
                          <span className="font-mono text-[10px]" title="Intentos">
                            ×{p.intentos}
                          </span>
                        )}
                        {p.category_name && (
                          <span
                            className="truncate max-w-[90px] text-[10px]"
                            title={p.category_name}
                          >
                            {p.category_name}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </ScrollArea>
    </div>
  )
}
