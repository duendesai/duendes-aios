from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    anthropic_api_key: str = ""
    environment: str = "development"

    class Config:
        env_file = "../../.env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
