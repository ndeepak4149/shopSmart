from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    database_url: str = ""
    redis_url: str = ""

    anthropic_api_key: str

    channel3_api_key: str
    ebay_app_id: str = ""        # legacy field — kept for compatibility
    ebay_client_id: str = ""     # eBay OAuth client ID (same value as app_id)
    ebay_client_secret: str = "" # eBay OAuth client secret — required for Browse API
    serpapi_key: str = ""

    google_places_api_key: str
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ShopSmart/1.0"

    resend_api_key: str = ""
    frontend_url: str = ""       # your Vercel URL e.g. https://shopsmart.vercel.app

    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
