"""
Jerarquía de errores del puerto CRM.

Cada adaptador captura las excepciones nativas de su proveedor (Airtable,
httpx/GraphQL de Twenty) y las re-lanza como `CRMError`, de forma que el caller
maneja fallos sin conocer el adaptador activo (ver spec crm-port: manejo de
errores uniforme). `status_code` y `detail` quedan accesibles para el mapeo a
`HTTPException` en los routers.
"""
from __future__ import annotations

from typing import Any


class CRMError(Exception):
    """Error de dominio del puerto CRM.

    Traduce cualquier fallo de proveedor (HTTP 4xx/5xx, timeout, validación de
    esquema, GraphQL errors) a una excepción uniforme. `status_code` es el código
    HTTP del proveedor si aplica; `detail` es el cuerpo/mensaje original para debug.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail if detail is not None else message


class CRMNotFoundError(CRMError):
    """El lead referenciado no existe en el proveedor (404)."""


class CRMValidationError(CRMError):
    """El proveedor rechazó el payload por validación de esquema (422/400)."""


class CRMAuthError(CRMError):
    """Fallo de autenticación contra el proveedor (401/403)."""
