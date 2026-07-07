from functools import lru_cache

from supabase import create_client, Client

from config import get_settings
from services.airtable_multi import AirtableMultiClient
from services.calcom_service import CalcomService
from services.crm.airtable_adapter import AirtableCRMAdapter
from services.crm.dual_write import DualWriteCRMClient
from services.crm.port import CRMClient
from services.crm.twenty_adapter import TwentyCRMAdapter
from services.zadarma_service import ZadarmaService


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def get_airtable() -> AirtableMultiClient:
    return AirtableMultiClient(api_key=get_settings().airtable_api_key)


def _build_airtable_adapter() -> AirtableCRMAdapter:
    return AirtableCRMAdapter(get_airtable())


def _build_twenty_adapter() -> TwentyCRMAdapter:
    s = get_settings()
    return TwentyCRMAdapter(base_url=s.twenty_base_url, api_key=s.twenty_api_key)


@lru_cache
def get_crm() -> CRMClient:
    """Resuelve el adaptador `CRMClient` activo según `Settings.crm_backend`.

    - airtable      → `AirtableCRMAdapter` (default, flujo vivo intacto)
    - twenty        → `TwentyCRMAdapter`
    - dual          → `DualWriteCRMClient(primary=Airtable, secondary=Twenty)` (piloto)
    - dual_reversed → `DualWriteCRMClient(primary=Twenty, secondary=Airtable)` (post-cutover)

    Ver openspec/changes/crm/design.md §4.
    """
    backend = get_settings().crm_backend
    if backend == "airtable":
        return _build_airtable_adapter()
    if backend == "twenty":
        return _build_twenty_adapter()
    if backend == "dual":
        return DualWriteCRMClient(
            primary=_build_airtable_adapter(),
            secondary=_build_twenty_adapter(),
        )
    if backend == "dual_reversed":
        return DualWriteCRMClient(
            primary=_build_twenty_adapter(),
            secondary=_build_airtable_adapter(),
        )
    # Defensa: si llega un valor no esperado, caer al comportamiento vivo.
    return _build_airtable_adapter()


@lru_cache
def get_calcom() -> CalcomService:
    s = get_settings()
    return CalcomService(api_key=s.calcom_api_key, event_type_id=s.calcom_event_type_id)


@lru_cache
def get_zadarma() -> ZadarmaService:
    s = get_settings()
    return ZadarmaService(
        api_key=s.zadarma_api_key,
        api_secret=s.zadarma_api_secret,
        sip_username=s.zadarma_sip_username,
    )
