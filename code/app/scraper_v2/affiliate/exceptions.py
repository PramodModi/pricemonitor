# app/scraper_v2/affiliate/exceptions.py
#
# Affiliate API exception hierarchy.
# Every concrete client raises only these types — BaseAffiliateClient._call_with_retry()
# routes its retry/re-auth/give-up logic entirely on these classes.


class AffiliateError(Exception):
    """
    Base class for all affiliate API errors.
    Caught as a generic fallback in _call_with_retry(); triggers retry with
    exponential backoff.
    """


class AffiliateAuthError(AffiliateError):
    """
    Credentials missing, invalid, or rejected (HTTP 401/403).
    Triggers a single re-authentication attempt before the next retry.
    Raised by:
      - _authenticate() when config keys are absent
      - _fetch() on HTTP 401 / 403 responses
    """


class AffiliateTimeoutError(AffiliateError):
    """
    Network request timed out (requests.Timeout).
    Triggers re-authentication once (session may have expired), then retry.
    Raised by:
      - _fetch() when requests.get() raises requests.Timeout
    """


class AffiliateNotFoundError(AffiliateError):
    """
    Product ID is not present in the affiliate feed.
    NOT retriable — _call_with_retry() returns None immediately and the
    ScraperEngine falls through to the browser cascade.
    Raised by:
      - _fetch() on HTTP 404
      - _parse() when the response body contains no product block
    """


class AffiliateRateLimitError(AffiliateError):
    """
    API rate limit hit (HTTP 429 or equivalent).
    _call_with_retry() waits _RATE_LIMIT_DELAY_S before the next retry.
    No re-authentication — rate limiting is not an auth problem.
    Raised by:
      - _fetch() on HTTP 429
    """
