# app/scraper_v2/affiliate/base.py
#
# Abstract base class for all marketplace affiliate API clients.
#
# Responsibilities owned HERE (not in subclasses):
#   - Retry loop with exponential backoff (max 3 attempts, 1s / 2s / 4s)
#   - Re-authentication on AffiliateTimeoutError or AffiliateAuthError (once per fetch())
#   - Rate-limit wait (30s flat) on AffiliateRateLimitError
#   - Immediate give-up on AffiliateNotFoundError (not retriable)
#   - All logging of attempt / backoff / re-auth / exhausted events
#
# Responsibilities owned by SUBCLASSES (abstract methods):
#   - platform_name  : string identifier ('flipkart', 'amazon')
#   - can_handle()   : True if this client supports the URL's platform
#   - extract_product_id() : pull marketplace ID from URL
#   - _authenticate(): validate/load credentials; raise AffiliateAuthError if missing
#   - _fetch()       : one HTTP call; return AffiliateResult or raise AffiliateError
#
# Adding a new marketplace (e.g. Myntra, Meesho):
#   1. Create app/scraper_v2/affiliate/myntra.py
#   2. Subclass BaseAffiliateClient
#   3. Implement the 5 abstract members above
#   4. Register the instance in __init__.py → AFFILIATE_CLIENTS list
#   Zero changes to base.py, engine.py, or any existing client.

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from app.scraper_v2.affiliate.exceptions import (
    AffiliateAuthError,
    AffiliateError,
    AffiliateNotFoundError,
    AffiliateRateLimitError,
    AffiliateTimeoutError,
)
from app.scraper_v2.affiliate.result import AffiliateResult

logger = logging.getLogger(__name__)

# ── Retry configuration ────────────────────────────────────────────────────── #
_MAX_RETRIES: int = 3
"""Maximum number of API call attempts per fetch() invocation."""

_BASE_DELAY_S: float = 1.0
"""
Base delay for exponential backoff.
Actual delay before attempt N+1 = _BASE_DELAY_S * 2^(N-1):
  attempt 1 → 2 : 1s
  attempt 2 → 3 : 2s
  (no delay after attempt 3 — already at the last attempt)
"""

_RATE_LIMIT_DELAY_S: float = 30.0
"""Flat wait after HTTP 429 before the next retry."""


class BaseAffiliateClient(ABC):
    """
    Abstract base class for marketplace affiliate API clients.

    Usage by ScraperEngine (attempt 0, before any Playwright is opened):

        for client in AFFILIATE_CLIENTS:
            if client.can_handle(url):
                result = client.fetch(url)
                if result is not None:
                    return _affiliate_result_to_scrape_response(result, url)
                break   # miss or exhausted — fall through to browser cascade

    fetch() never raises — all errors are caught internally and logged.
    It returns None when the product is not found or all retries are exhausted,
    signalling to the engine that the browser cascade should proceed.
    """

    def __init__(self) -> None:
        self._authenticated: bool = False
        """True after _authenticate() has succeeded at least once."""

        self._reauth_done: bool = False
        """
        Guards re-authentication to once per fetch() call.
        Reset to False at the start of every fetch() invocation so the
        re-auth path is available for the next independent product.
        """

    # ── Public interface — called by ScraperEngine ─────────────────────────── #

    def fetch(self, url: str) -> Optional[AffiliateResult]:
        """
        Main entry point called by ScraperEngine.

        Steps:
          1. Delegates URL routing to can_handle() — returns None if False.
          2. Extracts the marketplace product ID from the URL.
          3. Authenticates (once per process lifetime) if not yet done.
          4. Calls _call_with_retry() which runs _fetch() up to _MAX_RETRIES times.

        Returns:
            AffiliateResult on success.
            None on product-not-found, auth failure, or retries exhausted.
            Never raises.
        """
        if not self.can_handle(url):
            return None

        product_id = self.extract_product_id(url)
        if not product_id:
            logger.info(
                f"[AFFILIATE][{self.platform_name}] "
                f"could not extract product_id — url={url}"
            )
            return None

        # Initial authentication — once per process lifetime.
        if not self._authenticated:
            try:
                self._authenticate()
                self._authenticated = True
                logger.info(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"initial authentication successful"
                )
            except AffiliateAuthError as e:
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"initial authentication failed — {e} — skipping affiliate layer"
                )
                return None
            except Exception as e:
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"unexpected error during authentication — {e}"
                )
                return None

        # Reset re-auth guard for this fetch() call.
        self._reauth_done = False

        return self._call_with_retry(product_id, url)

    # ── Retry engine — inherited by all subclasses, never overridden ──────────── #

    def _call_with_retry(
        self, product_id: str, url: str
    ) -> Optional[AffiliateResult]:
        """
        Calls _fetch() up to _MAX_RETRIES times with exponential backoff.

        Error handling per exception type:

        AffiliateNotFoundError
            → Return None immediately. Product is absent from the feed;
              retrying will not help. Engine falls through to browser cascade.

        AffiliateTimeoutError
            → Re-authenticate once (session may have expired, or credentials
              may need refreshing). Then retry with backoff.
              If re-auth itself fails, return None — no point continuing.

        AffiliateAuthError
            → Same as AffiliateTimeoutError: re-auth once, then retry.
              If already re-authed this call, give up immediately to avoid
              hammering auth endpoints.

        AffiliateRateLimitError
            → Wait _RATE_LIMIT_DELAY_S (30s) flat. No re-auth. Then retry.
              The rate limit is a server-side throttle, not an auth issue.

        AffiliateError (base / catch-all)
            → Log and retry with exponential backoff. No re-auth.

        Exponential backoff delays (applied BEFORE the next attempt, not after
        the last one):
            attempt 1 → 2 : 1s
            attempt 2 → 3 : 2s

        Returns:
            AffiliateResult on success.
            None when all attempts are exhausted or a non-retriable error occurs.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"attempt={attempt}/{_MAX_RETRIES} product_id={product_id}"
                )
                result = self._fetch(product_id)
                logger.info(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"success — product_id={product_id} "
                    f"price={result.price} attempt={attempt}"
                )
                return result

            except AffiliateNotFoundError as e:
                # Not retriable — product is absent from the feed entirely.
                logger.info(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"product not in feed — product_id={product_id} — {e}"
                )
                return None

            except (AffiliateTimeoutError, AffiliateAuthError) as e:
                last_exc = e
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"{type(e).__name__} on attempt={attempt} — {e}"
                )
                if not self._reauth_done:
                    logger.info(
                        f"[AFFILIATE][{self.platform_name}] "
                        f"triggering re-authentication"
                    )
                    try:
                        self._authenticate()
                        self._authenticated = True
                        self._reauth_done = True
                        logger.info(
                            f"[AFFILIATE][{self.platform_name}] "
                            f"re-authentication successful"
                        )
                    except Exception as auth_exc:
                        # Re-auth itself failed — continuing is pointless.
                        logger.warning(
                            f"[AFFILIATE][{self.platform_name}] "
                            f"re-authentication failed — {auth_exc} — giving up"
                        )
                        return None
                else:
                    # Already re-authenticated this call and still failing.
                    logger.warning(
                        f"[AFFILIATE][{self.platform_name}] "
                        f"already re-authed this call — giving up"
                    )
                    return None

            except AffiliateRateLimitError as e:
                last_exc = e
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"rate limited on attempt={attempt} — "
                    f"waiting {_RATE_LIMIT_DELAY_S:.0f}s before retry"
                )
                time.sleep(_RATE_LIMIT_DELAY_S)

            except AffiliateError as e:
                # Generic affiliate error — retry with backoff.
                last_exc = e
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"error on attempt={attempt} — {e}"
                )

            except Exception as e:
                # Unexpected error (e.g. JSON parse failure) — retry with backoff.
                last_exc = e
                logger.warning(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"unexpected error on attempt={attempt} — {type(e).__name__}: {e}"
                )

            # ── Exponential backoff before next attempt ────────────────────── #
            # Skip delay after the final attempt — no next attempt to wait for.
            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_S * (2 ** (attempt - 1))  # 1s, 2s
                logger.info(
                    f"[AFFILIATE][{self.platform_name}] "
                    f"backoff delay={delay:.1f}s before attempt {attempt + 1}"
                )
                time.sleep(delay)

        logger.warning(
            f"[AFFILIATE][{self.platform_name}] "
            f"all {_MAX_RETRIES} attempts exhausted — "
            f"product_id={product_id} last_error={last_exc} — "
            f"falling through to browser cascade"
        )
        return None

    # ── Abstract interface — subclasses must implement all of these ────────── #

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Short lowercase platform identifier.
        Used in log lines and for routing logic.
        Examples: 'flipkart', 'amazon'
        """

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Return True if this client can handle the given URL's marketplace.
        Called by ScraperEngine before fetch() — must be fast (string check only).

        Examples:
            'flipkart.com' in url or 'dl.flipkart.com' in url  → FlipkartAffiliateClient
            'amazon.in' in url or 'amzn.in' in url             → AmazonAffiliateClient
        """

    @abstractmethod
    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the marketplace product identifier from the URL.

        Returns:
            The product ID string on success.
            None if the URL format is unrecognised (e.g. a category page,
            search result page, or short URL that hasn't been expanded).

        Must not make any network call — pure string parsing only.

        Examples:
            Flipkart: extract 'BCHDAH9QHFTH5GRZ' from ?pid= or /p/itm…
            Amazon:   extract 'B0CHX1W1XY' from /dp/{ASIN}
        """

    @abstractmethod
    def _authenticate(self) -> None:
        """
        Obtain or refresh API credentials.

        Called:
          - Once at process startup (before the first _fetch() call).
          - Again when AffiliateTimeoutError or AffiliateAuthError is raised
            during a retry cycle (at most once per fetch() invocation).

        For header-authenticated APIs (Flipkart):
            Validate that the required config keys are non-empty and store
            them in self._headers. No network call required.

        For token-exchange APIs (Amazon PA-API SigV4):
            Validate that Access Key + Secret Key exist in config. The actual
            SigV4 signature is computed per-request in _fetch(), not here.

        Raises:
            AffiliateAuthError if credentials are missing or invalid.
        """

    @abstractmethod
    def _fetch(self, product_id: str) -> AffiliateResult:
        """
        Execute one API call for the given product_id and return a result.

        This method is called by _call_with_retry() and must:
          - Make exactly one HTTP request.
          - Parse the response into an AffiliateResult.
          - Raise the appropriate AffiliateError subclass on failure.
          - Never catch AffiliateError subclasses — let them propagate to
            _call_with_retry() which owns retry/re-auth logic.

        Args:
            product_id: Marketplace product identifier (PID or ASIN).

        Returns:
            A populated AffiliateResult.

        Raises:
            AffiliateNotFoundError   — product absent from feed (HTTP 404 or
                                       empty productInfoList in response)
            AffiliateTimeoutError    — network timeout (requests.Timeout)
            AffiliateAuthError       — HTTP 401 or 403
            AffiliateRateLimitError  — HTTP 429
            AffiliateError           — any other API-level failure
        """
