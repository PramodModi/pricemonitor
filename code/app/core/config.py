from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    scraper_api_key: str = ""
    log_level: str = "INFO"
    page_goto_timeout_ms: int = 30_000
    page_selector_timeout_ms: int = 10_000
    scrape_retry_limit: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()