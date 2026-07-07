"""
Modelos de dominio del puerto CRM (dataclasses frozen).

`Lead` es la entidad provider-agnostic del pipeline de demos. `LeadRef` es la
referencia opaca a un lead ya persistido. `LeadPatch` es un update parcial: los
campos `None` NO se tocan en el registro remoto (patch parcial, ver spec crm-port).

Los `Literal` de `Fuente`/`Sector`/`Estado` reutilizan las opciones REALES del
`singleSelect` de la tabla Airtable `Leads` (base appFIn3ntFb39vGXF, verificadas
2026-07-01 vía Metadata API). Reutilizarlas evita divergencia de vocabulario entre
proveedores. NO son exhaustivos como validación dura: los adaptadores aceptan `str`
en la práctica (Airtable con `typecast=True`, Twenty normalizando), pero el `Literal`
documenta el vocabulario canónico y da autocompletado/typing al caller.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal

# ── Vocabulario canónico (opciones reales del singleSelect Airtable Leads) ──────

Fuente = Literal[
    "Meta Ads",
    "Web",
    "Referido",
    "Outreach",
    "Otro",
    "webinar",
    "Fisios Málaga Mar26",
    "Google Maps Apify",
    "Outbound Lucía",
    "Inbound Claudia",
    "YouTube Ads",
]

Sector = Literal[
    "Clínica Dental",
    "Centro de Estética",
    "Peluquería / Barbería",
    "Bufete / Legal",
    "Gestoría",
    "Consultoría",
    "Fontanería",
    "Electricidad",
    "Reformas",
    "Comercio",
    "Otro",
    "Wellness",
    "Fisioterapia",
    "Salud",
]

Estado = Literal[
    "Reunión agendada",
    "Propuesta enviada",
    "Negociación",
    "Ganado",
    "Perdido",
    "Incorrecto",
    "Recordatorio Enviado",
    "Cancelado",
    "Reprogramado",
]

Provider = Literal["airtable", "twenty"]


@dataclass(frozen=True, slots=True)
class Lead:
    """Entidad de dominio de un lead/demo. Provider-agnostic.

    `email` es la clave de identidad primaria (idempotencia, ver spec crm-port).
    `cal_booking_id` es el guardia secundario de idempotencia (reenvío de webhook
    Cal.com). Los campos de tipo `str | None` son opcionales.
    """

    nombre: str
    email: str
    telefono: str | None = None
    empresa: str | None = None
    sector: str | None = None
    fuente: str | None = None
    estado: str | None = None
    fecha_reunion: str | None = None  # ISO-8601; Twenty lo normaliza a UTC canónico
    cal_booking_id: str | None = None
    notas: str | None = None


@dataclass(frozen=True, slots=True)
class LeadRef:
    """Referencia opaca a un lead persistido.

    `id` es el identificador nativo del proveedor (record id de Airtable, id de
    Person de Twenty). `provider` identifica el adaptador que lo emitió. `url` es
    el deeplink al registro (Airtable UI / Twenty UI).
    """

    id: str
    provider: Provider
    url: str | None = None


@dataclass(frozen=True, slots=True)
class LeadPatch:
    """Update parcial de un lead. Solo los campos NO `None` se escriben en remoto.

    Cualquier campo dejado en `None` (su default) se OMITE del payload remoto, de
    forma que conserva su valor previo (ver spec crm-port: patch parcial).
    """

    nombre: str | None = None
    email: str | None = None
    telefono: str | None = None
    empresa: str | None = None
    sector: str | None = None
    fuente: str | None = None
    estado: str | None = None
    fecha_reunion: str | None = None
    cal_booking_id: str | None = None
    notas: str | None = None

    def changed_fields(self) -> dict[str, str]:
        """Devuelve solo los campos con valor (no `None`), como dict de dominio.

        Base para que cada adaptador traduzca a su payload remoto omitiendo los
        campos ausentes (patch parcial).
        """
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if getattr(self, f.name) is not None
        }
