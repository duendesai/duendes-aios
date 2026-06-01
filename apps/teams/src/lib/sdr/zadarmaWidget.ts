/**
 * Control del widget WebRTC de Zadarma embebido en el dialer.
 *
 * El widget expone su API en `window.zdrmWPhI.apiWidget`. PROBLEMA que resuelve
 * este módulo: el botón nativo de colgar del widget (`#zdrm-hangup`) viene con
 * `display:none` en el modo "square" que usamos, así que NO se puede colgar
 * desde la UI del widget — el único botón visible es el verde, que RE-MARCA.
 * Resultado: al no poder colgar, las llamadas a contestador/sin respuesta no se
 * podían cortar y, al pulsar el verde creyendo que colgaba, se re-llamaba en bucle.
 *
 * VERIFICADO en vivo (2026-06-01, ext 561989-100):
 *   - `apiWidget.cancel()` cuelga una saliente que está sonando:
 *       callState 'outgoing' → 'canceling' → 'canceled'.   ✔ (probado 3×)
 *   - El click programático a `#zdrm-hangup` NO cuelga (botón oculto, sin efecto).
 *   - Para una llamada YA conectada se usa la sesión SIP (`webCallSession.terminate()`)
 *     + `apiWidget.finishCall()` para la limpieza.
 */

type ZadarmaApiWidget = {
  callState?: string
  talking?: number
  cancel?: () => void
  finishCall?: () => void
}

type WindowWithZadarma = Window & {
  zdrmWPhI?: { apiWidget?: ZadarmaApiWidget }
  zdrmWebPhone?: { webCallSession?: { terminate?: () => void } }
}

/**
 * Cuelga la llamada activa del widget Zadarma (si la hay) y limpia el número del
 * input para que el botón verde del widget no la re-marque.
 *
 * Idempotente: si no hay llamada activa (`callState` vacío), no hace nada.
 */
export function hangupZadarmaWidget(): void {
  if (typeof window === 'undefined') return
  const w = window as WindowWithZadarma
  const api = w.zdrmWPhI?.apiWidget

  try {
    const state = api?.callState
    if (state === 'confirmed' || api?.talking) {
      // Llamada conectada → BYE sobre la sesión SIP + limpieza del widget.
      w.zdrmWebPhone?.webCallSession?.terminate?.()
      api?.finishCall?.()
    } else if (state) {
      // Saliente sonando / marcando / entrante → CANCEL (verificado en vivo).
      api?.cancel?.()
    }
  } catch {
    /* el widget puede no estar inicializado; ignorar */
  }

  // Limpiar el número del input: si queda "armado", el botón verde (lo único
  // visible, porque el rojo viene display:none) lo re-marca → bucle de llamadas.
  const input = document.getElementById(
    'zdrm-webphone-phonenumber-input'
  ) as HTMLInputElement | null
  if (input) {
    input.value = ''
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }
}
