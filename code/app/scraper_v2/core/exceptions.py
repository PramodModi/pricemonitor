"""
Scraper-specific exceptions.

Completely independent of PriceMonitor's exception hierarchy.
When scraper_v2 replaces scrapers/, scraper_worker.py catches
these instead of the ones from app.core.exceptions.
"""


class ScraperException(Exception):
    """Base for all scraper exceptions."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"{reason} — url={url}")


class ScrapeBotDetectedError(ScraperException):
    """
    Bot detection triggered — CAPTCHA, 429, or challenge page.
    Worker should route to ScraperAPI fallback on this error.
    """


class ScrapeTimeoutError(ScraperException):
    """
    page.goto() or selector wait exceeded configured timeout.
    Transient — worker should retry with backoff.
    """


class ScrapeExtractionError(ScraperException):
    """
    Page loaded correctly but price/product-id could not be extracted
    after all layers were attempted.
    Worker should mark scrape_status='failed', move on.
    """


class ScrapeConfigError(ScraperException):
    """
    Portal config missing or invalid — portals.yaml misconfiguration.
    Should never happen in production; raised at startup if config is bad.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(url="", reason=reason)


class UnsupportedPlatformError(ScraperException):
    """
    Platform name has no entry in portals.yaml.
    Adding a new portal = add entry to portals.yaml, not code.
    """

    def __init__(self, platform: str) -> None:
        super().__init__(url="", reason=f"No portal config for platform '{platform}'")
