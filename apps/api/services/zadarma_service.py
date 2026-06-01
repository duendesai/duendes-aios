"""
ZadarmaService — click-to-call vía API REST de Zadarma.

Documentación: https://zadarma.com/en/support/api/#api_request_callback
Endpoint: GET /v1/request/callback/?from={SIP}&to={NUMBER}&predicted=true

Cómo funciona:
1. Backend hace request firmado a Zadarma
2. Zadarma llama PRIMERO a tu SIP (Oscar) → tu softphone Zadarma suena
3. Cuando Oscar descuelga, Zadarma llama al prospect
4. Cuando el prospect descuelga, los conecta a los dos

`predicted=true` significa que la llamada al prospect SOLO se hace si Oscar ha
descolgado primero — evita "llamadas zombi" que asustan al prospect.

Auth: HMAC SHA1 sobre `path + sortedParams + md5(body)`.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.zadarma.com"


class ZadarmaError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ZadarmaService:
    """
    Click-to-call vía Zadarma REST API.

    Parameters
    ----------
    api_key, api_secret
        Credenciales de la API Zadarma (panel > integraciones).
    sip_username
        SIP login completo de la centralita (ej. '561989-100'). Se usa tal cual para
        /v1/webrtc/get_key/ y para inicializar el widget WebRTC en el frontend
        (donde el SIP login completo es OBLIGATORIO — si pasas solo '100' el widget
        responde 'integrationDisabled'). En cambio, para /v1/request/callback/ el
        parámetro `from` tiene patrón `^(\\+?[0-9]{7,15}|[0-9]{3,5})$` (OpenAPI
        oficial) que NO acepta guiones — si pasas '561989-100' Zadarma lo
        interpreta como número externo '561989100' y la llamada se va al limbo.
        Por eso el método `callback()` extrae solo la parte de extensión (después
        del último '-') para usar como `from`.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        sip_username: str,
        timeout: float = 15.0,
    ) -> None:
        if not api_key or not api_secret:
            raise ZadarmaError("Faltan ZADARMA_API_KEY o ZADARMA_API_SECRET en el .env raíz")
        if not sip_username:
            raise ZadarmaError("Falta ZADARMA_SIP_USERNAME en el .env raíz")
        self._api_key = api_key
        self._api_secret = api_secret
        # Normalizo: quito '+' y espacios. NO quito guiones: una extensión de
        # centralita usa el formato {pbx_id}-{ext}, p.ej. "561989-100", y el
        # guion es significativo para Zadarma.
        self._sip = sip_username.lstrip("+").replace(" ", "")
        self._timeout = timeout

    def _sign(self, method: str, params: dict[str, str]) -> str:
        """Firma según docs Zadarma: md5(sortedParams) → HMAC-SHA1(secret, method+params+md5).

        Más exactamente, la fórmula que usa la librería oficial:
            data_to_sign = method + paramsString + md5_hex(paramsString)
            signature   = base64(hmac_sha1_hex(secret, data_to_sign))
        donde paramsString = urlencode(sorted(params)).
        """
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params.items(), key=lambda kv: kv[0])
        )
        md5_hex = hashlib.md5(sorted_params.encode("utf-8")).hexdigest()
        data = f"{method}{sorted_params}{md5_hex}".encode("utf-8")
        signature_hex = hmac.new(
            self._api_secret.encode("utf-8"), data, hashlib.sha1
        ).hexdigest()
        import base64

        return base64.b64encode(signature_hex.encode("utf-8")).decode("utf-8")

    async def _request(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        signature = self._sign(method, params)
        headers = {
            "Authorization": f"{self._api_key}:{signature}",
        }
        # IMPORTANTE: la URL debe usar el mismo encoding que la firma — sin URL-encode.
        # Construimos manualmente para evitar que urlencode convierta '+' en '%2B'.
        params_string = "&".join(
            f"{k}={v}" for k, v in sorted(params.items(), key=lambda kv: kv[0])
        )
        url = f"{_BASE_URL}{method}?{params_string}" if params_string else f"{_BASE_URL}{method}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                logger.error("Zadarma %s → %s: %s", method, resp.status_code, body)
                raise ZadarmaError(
                    f"Zadarma {resp.status_code}: {body}",
                    status_code=resp.status_code,
                    body=body,
                )
            data = resp.json()
            if data.get("status") == "error":
                msg = data.get("message", "unknown error")
                logger.error("Zadarma error: %s", msg)
                raise ZadarmaError(f"Zadarma: {msg}", status_code=400, body=data)
            return data

    async def callback(
        self,
        *,
        to_number: str,
        predicted: bool = True,
    ) -> dict[str, Any]:
        """
        Inicia click-to-call: Zadarma llama primero a tu SIP, luego conecta al prospect.

        Parameters
        ----------
        to_number : str
            Número del prospect en formato internacional sin '+', ej. '34952123456'.
        predicted : bool
            Si True, Zadarma SOLO llama al prospect cuando tú has descolgado primero.
            Default: True (recomendado, evita robocalls fantasma).

        Returns
        -------
        dict con la respuesta normalizada: { status, from, to, time, ... }
        """
        # Normalizar: Zadarma quiere el número sin '+'
        to = to_number.lstrip("+").replace(" ", "").replace("-", "")

        # `from` debe ser número (7-15 dígitos) o extensión corta (3-5 dígitos)
        # según el regex oficial de la OpenAPI de Zadarma. Si el SIP configurado
        # viene en formato login-completo `pbxId-ext` (p.ej. '561989-100'),
        # extraemos solo la extensión (lo que va después del último guion):
        #   '561989-100' → '100'      ✓ válido para /v1/request/callback/
        #   '100'         → '100'      ✓ ya válido
        #   '34936942094' → '34936942094' ✓ número internacional (no extensión)
        # Sin esto, '561989-100' se desnormaliza a '561989100' y Zadarma lo
        # trata como un número externo de 9 dígitos en vez de la extensión PBX.
        from_value = self._sip.rsplit("-", 1)[-1] if "-" in self._sip else self._sip

        params = {
            "from": from_value,
            "to": to,
            "predicted": "true" if predicted else "false",
        }
        return await self._request("/v1/request/callback/", params)

    async def diagnose(self) -> dict[str, Any]:
        """
        Diagnóstico end-to-end del estado Zadarma desde el punto de vista del
        SDR. Llama a varios endpoints de Zadarma en paralelo y devuelve un
        resumen consolidado.

        Doc:
        - /v1/info/balance/ → saldo
        - /v1/pbx/internal/{ext}/status/ → si la extensión está online (registrada)
        - /v1/webrtc/ (GET) → lista de usuarios WebRTC creados
        - /v1/webrtc/domain/ (GET) → dominios autorizados para usar widget
        - /v1/sip/ → SIPs plano (líneas)
        """
        result: dict[str, Any] = {
            "configured_sip": self._sip,
            "interpretation_warning": (
                "Si configured_sip lleva guion (ej '561989-100'), Zadarma puede "
                "interpretarlo como número externo en /v1/request/callback/. "
                "Para callback, el formato correcto es solo el número de extensión "
                "(ej '100')."
            ),
        }

        async def _safe(label: str, method: str, params: dict[str, str] | None = None) -> None:
            try:
                result[label] = await self._request(method, params or {})
            except Exception as exc:  # noqa: BLE001
                result[label] = {"error": str(exc)}

        await _safe("balance", "/v1/info/balance/")
        await _safe("pbx_ext_100_status", "/v1/pbx/internal/100/status/")
        await _safe("pbx_ext_101_status", "/v1/pbx/internal/101/status/")
        await _safe("sip_899737_status", "/v1/sip/899737/status/")
        await _safe("webrtc_users", "/v1/webrtc/")
        await _safe("webrtc_domains", "/v1/webrtc/domain/")
        await _safe("sip_lines", "/v1/sip/")
        await _safe("pbx_redirection", "/v1/pbx/redirection/")
        # Lista de TODAS las extensiones PBX configuradas (revela si hay
        # más extensiones que las que asumimos):
        await _safe("pbx_all_internal", "/v1/pbx/internal/")

        return result

    async def get_webrtc_key(self, sip: str | None = None) -> dict[str, Any]:
        """
        Pide a Zadarma una clave temporal para inicializar el widget WebRTC
        embebido en el dialer.

        Doc: https://zadarma.com/en/support/api/#api_request_webrtc_get_key

        Parameters
        ----------
        sip : str | None
            SIP login o extensión de PBX completa (p.ej. '561989-100'). Si no se
            indica, usa el sip_username configurado del servicio.

        Returns
        -------
        dict { status, key, ...} — `key` es la clave temporal (válida ~72h)
        que se pasa al widget como primer argumento de `zadarmaWidgetFn`.
        """
        # /v1/webrtc/get_key/ usa el parámetro `sip`
        return await self._request(
            "/v1/webrtc/get_key/",
            {"sip": (sip or self._sip)},
        )
