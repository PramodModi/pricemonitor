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

class PreviewNotFoundError(PriceWatchError):
    """
    Raised when a preview_id does not resolve to a cached ProductSnapshot.
    Maps to HTTP 404 / PREVIEW_NOT_FOUND.
    """
    def __init__(self, preview_id: str) -> None:
        self.preview_id = preview_id
        super().__init__(f"Preview not found: {preview_id}")


class SubscriptionNotFoundError(PriceWatchError):
    """
    Raised when a subscription_id does not exist or does not belong to the
    requesting email. Maps to HTTP 404 / SUBSCRIPTION_NOT_FOUND.
    Intentionally non-distinguishing — avoids leaking subscription existence.
    """
    def __init__(self, subscription_id: str) -> None:
        self.subscription_id = subscription_id
        super().__init__(f"Subscription not found: {subscription_id}")