from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    supabase_url: str
    supabase_key: str
    database_url: str

    # Cache
    redis_url: str

    # AI
    anthropic_api_key: str

    # Discovery APIs
    channel3_api_key: str
    ebay_app_id: str = ""

    # Local / Reviews
    google_places_api_key: str
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ShopSmart/1.0"

    # Email
    resend_api_key: str = ""

    # App
    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
