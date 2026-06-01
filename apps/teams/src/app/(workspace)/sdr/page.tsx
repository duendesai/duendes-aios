'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import { CallQueue } from '@/components/sdr/CallQueue'
import { CallPanel } from '@/components/sdr/CallPanel'
import { CallForm } from '@/components/sdr/CallForm'
import { BookingPanel } from '@/components/sdr/BookingPanel'
import { ScriptReference } from '@/components/sdr/ScriptReference'
import { SessionHeader } from '@/components/sdr/SessionHeader'
import { ShortcutsHelp } from '@/components/sdr/ShortcutsHelp'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useCallSessionStore } from '@/store/useCallSessionStore'
import {
  fetchQueue,
  fetchProspect,
  fetchCampaigns,
  fetchWebrtcKey,
  ApiError,
  type QueueMode,
} from '@/lib/sdr/api'
import { useKeyboardShortcuts } from '@/lib/sdr/useKeyboardShortcuts'
import { DISPOSITION_OPTIONS } from '@/lib/sdr/enums'

export default function SdrPage() {
  const searchParams = useSearchParams()
  const requestedProspect = searchParams.get('prospect')
  const setQueue = useCallSessionStore((s) => s.setQueue)
  const setQueueLoading = useCallSessionStore((s) => s.setQueueLoading)
  const mode = useCallSessionStore((s) => s.mode)
  const setMode = useCallSessionStore((s) => s.setMode)
  const campaign = useCallSessionStore((s) => s.campaign)
  const setCampaign = useCallSessionStore((s) => s.setCampaign)
  const campaigns = useCallSessionStore((s) => s.campaigns)
  const setCampaigns = useCallSessionStore((s) => s.setCampaigns)
  const selectProspect = useCallSessionStore((s) => s.selectProspect)
  const activeId = useCallSessionStore((s) => s.activeId)
  const setActiveProspect = useCallSessionStore((s) => s.setActiveProspect)
  const setProspectLoading = useCallSessionStore((s) => s.setProspectLoading)
  const callState = useCallSessionStore((s) => s.callState)
  const startCall = useCallSessionStore((s) => s.startCall)
  const endCall = useCallSessionStore((s) => s.endCall)
  const nextProspect = useCallSessionStore((s) => s.nextProspect)
  const showBooking = useCallSessionStore((s) => s.showBooking)
  const resetSession = useCallSessionStore((s) => s.resetSession)
  const prospectsTotal = useCallSessionStore((s) => s.prospects.length)
  const activeProspect = useCallSessionStore((s) => s.activeProspect ?? s.getActiveProspect())

  const [helpOpen, setHelpOpen] = useState(false)

  // Cargar cola
  const loadQueue = useCallback(
    async (currentMode: QueueMode = mode, currentCampaign: string = campaign) => {
      setQueueLoading(true)
      try {
        const data = await fetchQueue(100, currentMode, currentCampaign)
        setQueue(data.prospects)
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : 'Error de red'
        setQueueLoading(false, msg)
        toast.error(`No se pudo cargar la cola: ${msg}`)
      }
    },
    [setQueue, setQueueLoading, mode, campaign]
  )

  // Cargar campañas disponibles al montar (alimenta el selector)
  useEffect(() => {
    fetchCampaigns()
      .then((data) => setCampaigns(data.campaigns))
      .catch(() => {
        /* sin campañas → el selector se oculta */
      })
  }, [setCampaigns])

  // Cargar el widget WebRTC oficial de Zadarma — UNA sola vez por sesión.
  // Esto registra la extensión PBX 561989-100 dentro del propio dialer:
  //   ✔ Llamadas pasan por la PBX (grabación automática + aparecen en /v1/statistics/pbx/)
  //   ✔ Callbacks del backend (POST /calls/zadarma/dial) suenan en el propio widget
  //   ✔ Botón "Analizar" funciona porque encuentra la grabación
  // El dominio teams.duendes.net está autorizado en my.zadarma.com → WebRTC.
  //
  // IMPORTANTE — Por qué SIP_LOGIN = '561989-100' (login COMPLETO):
  // El widget WebRTC de Zadarma EXIGE el login SIP completo (pbxId-ext). Si le
  // pasas solo '100' responde `integrationDisabled: wrong key or sip`. En cambio,
  // el endpoint /v1/request/callback/ del backend exige `from` corto (regex
  // `^(\+?[0-9]{7,15}|[0-9]{3,5})$` según OpenAPI oficial). Por eso el backend
  // tiene ZADARMA_SIP_USERNAME='561989-100' Y el método callback() extrae solo
  // '100' automáticamente antes de enviar — ver zadarma_service.py:callback().
  useEffect(() => {
    type WindowWithZadarma = Window & {
      __zadarmaWidgetLoaded?: boolean
      zadarmaWidgetFn?: (
        key: string,
        sip: string,
        shape: 'square' | 'rounded',
        lang: string,
        expanded: boolean,
        position: Record<string, string>
      ) => void
    }
    const w = window as WindowWithZadarma
    if (w.__zadarmaWidgetLoaded) return
    w.__zadarmaWidgetLoaded = true

    // SIP login COMPLETO (pbxId-ext). VERIFICADO en vivo 2026-06-01: el widget
    // rechaza '100' con `integrationDisabled: wrong key or sip` porque el backend
    // mintea la key para '561989-100' (get_webrtc_key usa el SIP completo) y key+sip
    // deben COINCIDIR. Con '561989-100' registra/conecta limpio. NO cambiar a '100'.
    const SIP_LOGIN = '561989-100'
    const LIB =
      'https://my.zadarma.com/webphoneWebRTCWidget/v9/js/loader-phone-lib.js?sub_v=1'
    const FN =
      'https://my.zadarma.com/webphoneWebRTCWidget/v9/js/loader-phone-fn.js?sub_v=1'

    function loadScript(src: string): Promise<void> {
      return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) {
          resolve()
          return
        }
        const s = document.createElement('script')
        s.src = src
        s.async = true
        s.onload = () => resolve()
        s.onerror = () => reject(new Error(`No pude cargar ${src}`))
        document.head.appendChild(s)
      })
    }

    async function init() {
      try {
        const { key } = await fetchWebrtcKey()
        await loadScript(LIB)
        await loadScript(FN)
        if (typeof w.zadarmaWidgetFn === 'function') {
          w.zadarmaWidgetFn(
            key,
            SIP_LOGIN,
            'square',
            'es',
            true,
            { right: '10px', top: '5px' }
          )
          // Estilo del widget: transparentar la caja gris exterior, dejar
          // visibles solo el input + botón verde (que tienen su propio fondo).
          if (!document.getElementById('zdrm-widget-style')) {
            const style = document.createElement('style')
            style.id = 'zdrm-widget-style'
            style.textContent = `
              .zdrm-phone,
              .zdrm-webphone-box {
                background: transparent !important;
                background-color: transparent !important;
                box-shadow: none !important;
                border: none !important;
                padding: 0 !important;
              }
            `
            document.head.appendChild(style)
          }
        } else {
          throw new Error('zadarmaWidgetFn no expuesto tras cargar los scripts')
        }
      } catch (err) {
        w.__zadarmaWidgetLoaded = false
        // eslint-disable-next-line no-console
        console.error('Widget Zadarma no inicializado:', err)
        toast.error('No pude cargar el teléfono web de Zadarma. Revisa la consola.')
      }
    }

    init()
  }, [])

  // Recarga cuando cambia el modo o la campaña
  useEffect(() => {
    loadQueue(mode, campaign)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, campaign])

  function handleModeChange(m: QueueMode) {
    if (m === mode) return
    setMode(m)
    // El useEffect recarga la cola
  }

  function handleCampaignChange(slug: string) {
    if (slug === campaign) return
    setCampaign(slug)
    // El useEffect recarga la cola
  }

  // Si llegamos con ?prospect=ID (desde Agenda), forzar selección incluso si no
  // está en la cola (lo carga el efecto que carga el detalle igualmente)
  useEffect(() => {
    if (requestedProspect) {
      selectProspect(requestedProspect)
    }
  }, [requestedProspect, selectProspect])

  // Cargar detalle del prospecto activo (incluye call_history)
  const detailReqId = useRef(0)
  useEffect(() => {
    if (!activeId) {
      setActiveProspect(null)
      return
    }
    detailReqId.current += 1
    const reqId = detailReqId.current
    setProspectLoading(true)
    fetchProspect(activeId)
      .then((p) => {
        if (detailReqId.current === reqId) {
          setActiveProspect(p)
        }
      })
      .catch((err) => {
        if (detailReqId.current === reqId) {
          const msg = err instanceof ApiError ? err.message : 'Error al cargar detalle'
          toast.error(msg)
        }
      })
      .finally(() => {
        if (detailReqId.current === reqId) {
          setProspectLoading(false)
        }
      })
  }, [activeId, setActiveProspect, setProspectLoading])

  // Atajos
  useKeyboardShortcuts({
    '?': () => setHelpOpen(true),
    C: () => {
      if (callState === 'idle' && activeProspect?.phone) {
        const btn = document.querySelector<HTMLButtonElement>('button[data-call-button]')
        btn?.click()
      }
    },
    H: () => {
      if (callState === 'in_call') endCall()
    },
    Escape: () => {
      if (callState === 'in_call') endCall()
    },
    N: () => {
      if (callState === 'in_call') {
        if (window.confirm('¿Saltar al siguiente sin guardar la llamada actual?')) {
          nextProspect()
        }
      } else {
        nextProspect()
      }
    },
    S: () => {
      if (callState === 'wrap_up') {
        const form = document.querySelector<HTMLFormElement>('form[data-call-form]')
        form?.requestSubmit()
      }
    },
    // Disposition rápida 1-9
    ...Object.fromEntries(
      DISPOSITION_OPTIONS.slice(0, 9).map((opt, i) => [
        String(i + 1),
        () => {
          if (callState !== 'wrap_up') return
          const btn = document.querySelector<HTMLButtonElement>(
            `button[data-disposition="${opt.value}"]`
          )
          btn?.click()
        },
      ])
    ),
  })

  return (
    <div className="h-full flex flex-col bg-background">
      <SessionHeader
        totalQueue={prospectsTotal}
        onReset={resetSession}
        onModeChange={handleModeChange}
        campaigns={campaigns}
        activeCampaign={campaign}
        onCampaignChange={handleCampaignChange}
      />

      <div className="flex-1 flex overflow-hidden">
        <CallQueue onReload={loadQueue} />

        <div className="flex-1 flex flex-col overflow-hidden">
          {callState === 'idle' && !showBooking && <CallPanel />}

          {callState === 'in_call' && <CallPanel />}

          {callState === 'wrap_up' && !showBooking && (
            <div className="flex-1 overflow-hidden flex">
              <div className="flex-1 overflow-hidden flex flex-col">
                <ScrollArea className="flex-1">
                  <div className="p-6 max-w-3xl mx-auto">
                    <CallPanelSummary />
                  </div>
                </ScrollArea>
              </div>
              <div className="w-[420px] shrink-0 border-l border-border bg-card/30 overflow-hidden flex flex-col">
                <ScrollArea className="flex-1">
                  <div className="p-4">
                    <CallForm />
                  </div>
                </ScrollArea>
              </div>
            </div>
          )}

          {showBooking && (
            <div className="flex-1 overflow-hidden flex">
              <div className="flex-1 overflow-hidden flex flex-col">
                <ScrollArea className="flex-1">
                  <div className="p-6 max-w-3xl mx-auto">
                    <CallPanelSummary />
                  </div>
                </ScrollArea>
              </div>
              <div className="w-[480px] shrink-0 border-l border-border bg-card/30 overflow-hidden flex flex-col">
                <ScrollArea className="flex-1">
                  <div className="p-4">
                    <BookingPanel />
                  </div>
                </ScrollArea>
              </div>
            </div>
          )}
        </div>

        <ScriptReference />
      </div>

      <ShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  )
}

/**
 * Versión compacta del CallPanel para mostrar a la izquierda durante wrap_up/booking.
 * Reutiliza CallPanel sin el botón Llamar.
 */
function CallPanelSummary() {
  return <CallPanel />
}
