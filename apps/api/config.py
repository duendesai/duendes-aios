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
    calcom_event_type_id: int = 5693752  # cal.com/duendes/demo (30 min)
    zadarma_api_key: str = ""
    zadarma_api_secret: str = ""
    zadarma_sip_username: str = ""

    class Config:
        env_file = "../../.env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
