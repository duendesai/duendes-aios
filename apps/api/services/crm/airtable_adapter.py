"""
`AirtableCRMAdapter` — adaptador del puerto `CRMClient` que ENVUELVE
`AirtableMultiClient` (no lo reescribe) contra la base "Duendes CRM"
(`appFIn3ntFb39vGXF`, tabla `Leads`).

Preserva EXACTAMENTE el mapeo de campos y el `typecast=True` que hoy usa
`services.calls_service.book_demo_and_create_lead`, de forma que con
`CRM_BACKEND=airtable` (default) el registro escrito en Airtable es idéntico al
de antes del refactor (regresión cero, ver tasks 7.4).

Disciplina de idempotencia (D1, design §1): `create_lead` hace un pre-check con
`find_lead` (email y/o `cal_booking_id`) ANTES de crear. El pre-check vive aquí,
no solo en `DualWriteCRMClient`, para que el adaptador sea idempotente operando
en solitario (post-cutover con `CRM_BACKEND=airtable`).

Todos los errores nativos de Airtable (`AirtableError`) se re-lanzan como
`CRMError` (spec crm-port, manejo de errores uniforme).
"""
from __future__ import annotations

import logging

from services.airtable_multi import (
    BASE_CRM,
    TABLE_LEADS,
    AirtableError,
    AirtableMultiClient,
)
from services.crm.errors import CRMError
from services.crm.models import Lead, LeadPatch, LeadRef

logger = logging.getLogger(__name__)

# Mapeo dominio → nombre de campo Airtable en la tabla `Leads`. Es el MISMO
# vocabulario de columnas que hoy escribe `book_demo_and_create_lead`.
_FIELD_NOMBRE = "Nombre"
_FIELD_EMAIL = "Email"
_FIELD_TELEFONO = "Teléfono"
_FIELD_EMPRESA = "Empresa"
_FIELD_SECTOR = "Sector"
_FIELD_FUENTE = "Fuente"
_FIELD_ESTADO = "Estado"
_FIELD_FECHA = "Fecha reunión"
_FIELD_CAL_BOOKING = "Cal Booking ID"
_FIELD_NOTAS = "Notas"

# dominio Lead/LeadPatch attr → campo Airtable. Orden = orden de escritura.
_DOMAIN_TO_AIRTABLE: dict[str, str] = {
    "nombre": _FIELD_NOMBRE,
    "email": _FIELD_EMAIL,
    "telefono": _FIELD_TELEFONO,
    "empresa": _FIELD_EMPRESA,
    "sector": _FIELD_SECTOR,
    "fuente": _FIELD_FUENTE,
    "estado": _FIELD_ESTADO,
    "fecha_reunion": _FIELD_FECHA,
    "cal_booking_id": _FIELD_CAL_BOOKING,
    "notas": _FIELD_NOTAS,
}


def _escape_formula_value(value: str) -> str:
    """Escapa comillas dobles para interpolar en un `filterByFormula` de Airtable."""
    return value.replace('"', '\\"')


class AirtableCRMAdapter:
    """Adaptador Airtable del puerto `CRMClient`. Person = registro de `Leads`."""

    def __init__(
        self,
        client: AirtableMultiClient,
        *,
        base_id: str = BASE_CRM,
        table: str = TABLE_LEADS,
    ) -> None:
        self._client = client
        self._base_id = base_id
        self._table = table

    # ── Traducción dominio ↔ Airtable ─────────────────────────────────────────

    def _lead_to_fields(self, lead: Lead) -> dict[str, str]:
        """`Lead` → dict de campos Airtable, omitiendo los `None` (patch parcial)."""
        fields: dict[str, str] = {}
        for attr, column in _DOMAIN_TO_AIRTABLE.items():
            value = getattr(lead, attr)
            if value is not None:
                fields[column] = value
        return fields

    def _patch_to_fields(self, changes: LeadPatch) -> dict[str, str]:
        """`LeadPatch` → dict de campos Airtable con SOLO los campos no-`None`.

        Los campos ausentes se omiten del PATCH, de forma que conservan su valor
        previo en Airtable (spec crm-port: patch parcial).
        """
        changed = changes.changed_fields()
        return {
            _DOMAIN_TO_AIRTABLE[attr]: value
            for attr, value in changed.items()
            if attr in _DOMAIN_TO_AIRTABLE
        }

    def _record_to_lead(self, record: dict) -> Lead:
        f = record.get("fields", {})
        return Lead(
            nombre=f.get(_FIELD_NOMBRE) or "",
            email=f.get(_FIELD_EMAIL) or "",
            telefono=f.get(_FIELD_TELEFONO),
            empresa=f.get(_FIELD_EMPRESA),
            sector=f.get(_FIELD_SECTOR),
            fuente=f.get(_FIELD_FUENTE),
            estado=f.get(_FIELD_ESTADO),
            fecha_reunion=f.get(_FIELD_FECHA),
            cal_booking_id=f.get(_FIELD_CAL_BOOKING),
            notas=f.get(_FIELD_NOTAS),
        )

    def _record_to_ref(self, record: dict) -> LeadRef:
        record_id = record["id"]
        return LeadRef(
            id=record_id,
            provider="airtable",
            url=f"https://airtable.com/{self._base_id}/{self._table}/{record_id}",
        )

    # ── Puerto CRMClient ──────────────────────────────────────────────────────

    async def create_lead(self, lead: Lead) -> LeadRef:
        # Pre-check de idempotencia (D1): email y/o cal_booking_id. El pre-check es
        # best-effort: si la LECTURA falla (transitorio), no abortamos la creación
        # — "no se pudo verificar" se trata como "no existe" y se procede a crear.
        # La creación es la operación crítica; el dedup es best-effort. El error del
        # POST de creación (más abajo) SÍ propaga.
        try:
            existing = await self.find_lead(
                email=lead.email or None,
                cal_booking_id=lead.cal_booking_id or None,
            )
        except CRMError as exc:
            logger.warning(
                "Airtable create_lead pre-check find_lead falló (email=%s, "
                "cal_booking_id=%s): %s — se procede a crear sin dedup",
                lead.email,
                lead.cal_booking_id,
                exc,
            )
        else:
            if existing is not None:
                return existing

        fields = self._lead_to_fields(lead)
        try:
            # typecast=True idéntico al flujo vivo: el Sector llega del
            # category_name (texto libre) y puede no existir como opción.
            record = await self._client.create_record(
                self._base_id, self._table, fields, typecast=True
            )
        except AirtableError as exc:
            raise CRMError(
                f"Airtable create_lead falló: {exc}",
                status_code=exc.status_code,
                detail=exc.body,
            ) from exc
        return self._record_to_ref(record)

    async def update_lead(self, ref: LeadRef, changes: LeadPatch) -> LeadRef:
        fields = self._patch_to_fields(changes)
        if not fields:
            # Nada que actualizar: devolver la referencia tal cual.
            return ref
        try:
            record = await self._client.update_record(
                self._base_id, self._table, ref.id, fields, typecast=True
            )
        except AirtableError as exc:
            raise CRMError(
                f"Airtable update_lead falló: {exc}",
                status_code=exc.status_code,
                detail=exc.body,
            ) from exc
        return self._record_to_ref(record)

    async def get_lead(self, ref: LeadRef) -> Lead | None:
        try:
            record = await self._client.get_record(self._base_id, self._table, ref.id)
        except AirtableError as exc:
            if exc.status_code == 404:
                return None
            raise CRMError(
                f"Airtable get_lead falló: {exc}",
                status_code=exc.status_code,
                detail=exc.body,
            ) from exc
        return self._record_to_lead(record)

    async def find_lead(
        self,
        *,
        email: str | None = None,
        cal_booking_id: str | None = None,
    ) -> LeadRef | None:
        # Email es la clave primaria: se busca primero. Si no matchea, se cae al
        # guardia por cal_booking_id (design §1, D1).
        if email:
            ref = await self._find_by_formula(
                f'{{{_FIELD_EMAIL}}}="{_escape_formula_value(email)}"'
            )
            if ref is not None:
                return ref
        if cal_booking_id:
            ref = await self._find_by_formula(
                f'{{{_FIELD_CAL_BOOKING}}}="{_escape_formula_value(cal_booking_id)}"'
            )
            if ref is not None:
                return ref
        return None

    async def _find_by_formula(self, formula: str) -> LeadRef | None:
        try:
            records = await self._client.list_records(
                self._base_id,
                self._table,
                filter_formula=formula,
                max_records=1,
            )
        except AirtableError as exc:
            raise CRMError(
                f"Airtable find_lead falló: {exc}",
                status_code=exc.status_code,
                detail=exc.body,
            ) from exc
        if not records:
            return None
        return self._record_to_ref(records[0])
