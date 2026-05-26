from functools import lru_cache

from supabase import create_client, Client

from config import get_settings
from services.airtable_multi import AirtableMultiClient
from services.calcom_service import CalcomService
from services.zadarma_service import ZadarmaService


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def get_airtable() -> AirtableMultiClient:
    return AirtableMultiClient(api_key=get_settings().airtable_api_key)


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
