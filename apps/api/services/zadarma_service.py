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
        Tu SIP interno (la "extensión de la centralita"). Ej.: '098765' o '098765-100'.
        Zadarma llama a este SIP primero antes de marcar el número del prospect.
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
        # Normalizo: quito '+', espacios, guiones para que firma y URL coincidan
        self._sip = sip_username.lstrip("+").replace(" ", "").replace("-", "")
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
        params = {
            "from": self._sip,
            "to": to,
            "predicted": "true" if predicted else "false",
        }
        return await self._request("/v1/request/callback/", params)
