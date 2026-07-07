from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    anthropic_api_key: str = ""
    environment: str = "development"

    # Cold outreach / SDR (teams.duendes.net — power dialer)
    airtable_api_key: str = ""
    calcom_api_key: str = ""
    calcom_event_type_id: int = 4879655  # cal.com/duendes/consulta (30 min)
    zadarma_api_key: str = ""
    zadarma_api_secret: str = ""
    zadarma_sip_username: str = ""
    smartlead_api_key: str = ""
    groq_api_key: str = ""  # Whisper — transcripción de grabaciones de llamadas Zadarma
    admin_token: str = ""  # Auth para endpoints /admin/* — n8n lo manda en X-Admin-Token

    # CRM port toggle (piloto migración Airtable → Twenty, ver openspec/changes/crm)
    # - airtable      = default, comportamiento vivo (Airtable fuente de verdad)
    # - twenty        = Twenty puro (post ventana de seguridad)
    # - dual          = piloto: primary=Airtable, secondary=Twenty (espejo)
    # - dual_reversed = ventana de seguridad post-cutover: primary=Twenty, secondary=Airtable
    crm_backend: Literal["airtable", "twenty", "dual", "dual_reversed"] = "airtable"
    twenty_base_url: str = ""  # p.ej. https://crm.duendes.net
    twenty_api_key: str = ""  # PAT de Twenty (env TWENTY_API_KEY)

    class Config:
        env_file = "../../.env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
