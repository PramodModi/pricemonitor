from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    scraper_api_key: str = ""
    log_level: str = "INFO"
    page_goto_timeout_ms: int = 30_000
    page_selector_timeout_ms: int = 10_000
    scrape_retry_limit: int = 3
    max_scraper_workers: int = 3
    scrape_timeout_seconds: int = 60
    worker_health_check_interval: int = 30
    queue_drain_timeout: int = 60
    email_retry_limit: int = 3
    email_from_address: str = "alerts@pricewatch.app"
    email_from_name: str = "Pricemonitor"
    email_reply_to: str = "no-reply@pricewatch.app"
    sendgrid_api_key: str = ""
    dashboard_url: str = "https://pricewatch.app/dashboard"
    amazon_affiliate_tag: str = ""
    flipkart_affiliate_id: str = ""
    secret_key: str = "pricemonitor"
    use_scraper_v2: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()