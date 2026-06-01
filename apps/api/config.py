from pydantic_settings import BaseSettings
from functools import lru_cache


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

    class Config:
        env_file = "../../.env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
