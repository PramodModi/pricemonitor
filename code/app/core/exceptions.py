class PriceWatchError(Exception):
    pass


class InvalidURLError(PriceWatchError):
    def __init__(self, url: str, detail: str = "") -> None:
        self.url = url
        self.detail = detail
        super().__init__(f"Invalid product URL: {url}")


class UnsupportedPlatformError(PriceWatchError):
    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(f"Unsupported platform: {domain}")


class ScrapeError(PriceWatchError):
    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Scrape failed for {url}: {reason}")


class ScrapeBotDetectedError(ScrapeError):
    pass


class ScrapeTimeoutError(ScrapeError):
    pass