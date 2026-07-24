"""
ScraperEngine — the single public surface of scraper_v2.

File: app/scraper_v2/engine.py

Public API — this is all the caller ever sees:

    from app.scraper_v2.engine import ScraperEngine

    engine = ScraperEngine()
    response = engine.scrape(url)           # url is all the caller provides
    # response is a ScrapeResponse

The caller (today: scraper_worker.py, preview route in products.py)
passes only the URL. Everything else is resolved internally:

    URL → registry.get_config_for_domain() → PortalConfig
    PortalConfig.browser → which engine to launch (Chromium / Firefox)
    ScrapeResponse.error_type + navigation_ms → FailureDiagnosis → next attempt

Future callers (FastAPI handler, scraper_v3) use the same one-line interface.
When strategy changes (affiliate API, LLM extraction, scraper_v3), only
engine.py changes — no caller is touched.

─────────────────────────────────────────────────────────────────────────────
5-Attempt Retry Cascade
─────────────────────────────────────────────────────────────────────────────

Attempt 1  Chromium stealth, fresh BrowserContext, existing long-lived browser
           → covers the vast majority of successful scrapes

Attempt 2  New BrowserContext, rotated User-Agent, cleared cookies
           → handles transient WAF / rate-limit / session-state issues

Attempt 3  Firefox engine, new process
           → bypasses TLS fingerprint detection (Myntra fix — v2.2 FIX-001)
           → also changes all OS-level process signals

Attempt 4  Google Cache → Bing Cache (tried in order)
           → static HTML snapshot, zero bot detection, no JS required
           → same GenericScraper extraction layers run on the cached HTML

Attempt 5  ScraperAPI residential proxy (if SCRAPER_API_KEY configured)
           → residential IP, CAPTCHA solving, JS rendering
           → falls back to raw HTML heuristic if key not set

FailureDiagnosis from attempt N informs attempt N+1:
    IP_BLOCK   → jump straight to ScraperAPI (no point burning browser attempts)
    CAPTCHA    → jump straight to ScraperAPI
    FINGERPRINT→ jump to Firefox (attempt 3 logic at attempt 2)
    CSS_STALE  → ScraperAPI (gets the real price even when selectors are stale)
    WAF        → new context first (FIX-005 handles most; fresh context handles rest)
    TIMEOUT    → new context (may be a transient network hiccup)
    RATE_LIMIT → sleep _RATE_LIMIT_BACKOFF_S then retry same config

─────────────────────────────────────────────────────────────────────────────
Architecture notes
─────────────────────────────────────────────────────────────────────────────

scraper_v2 imports:
    app.scraper_v2.*   — all internal
    app.core.config    — only for scraper_api_key and timeout settings
                         (these live in scraper_v2/core/config.py via load_config())

scraper_v2 does NOT import:
    app.workers.*      — no coupling to worker layer
    app.repositories.* — no DB access (caller writes to DB)
    app.scrapers.*     — old scrapers never touched

Browser lifecycle:
    ScraperEngine owns one long-lived Chromium browser (self._browser).
    Firefox is opened and closed per-attempt (per-job) to avoid memory leaks —
    same pattern established in scraper_worker.py v2.1 FEAT-005.
    Caller must call engine.close() when done, or use as a context manager.

Logger: f-strings only (DEV-006 from v1.0 changelog).
Stealth: Stealth().apply_stealth_sync(page) — DEV-004 from v1.0 changelog.
Context split: Myntra / Firefox contexts never override UA (v2.2 FIX-001/002).
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Optional
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    sync_playwright,
    TimeoutError as PlaywrightTimeout,
)

from app.scraper_v2.core.config import settings
from app.scraper_v2.core.logging import get_logger
from app.scraper_v2.models.scrape_result import ScrapeFailureReason, ScrapeResponse
from app.scraper_v2.scrapers.failure_classifier import (
    FailureCause,
    RetryMechanism,
    classifier,
)
from app.scraper_v2.scrapers.generic_scraper import GenericScraper
from app.scraper_v2.scrapers.portal_config import PortalConfig
from app.scraper_v2.scrapers.registry import get_config_for_domain

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_ATTEMPTS = 5

# Delay between retry attempts — progressive, light.
# attempt 1→2: 2s, 2→3: 4s, 3→4: 6s, 4→5: 8s
# Each attempt uses a different mechanism so the delay just gives the
# previous session time to expire on the portal's side.
_RETRY_DELAY_BASE_S = 2   # seconds added per attempt number

# Rate-limit specific back-off (separate, much longer)
_RATE_LIMIT_BACKOFF_S = 15

# Real desktop UAs — rotated across attempts.
# Firefox UA is intentionally absent — Firefox attempts use Playwright's
# real Firefox UA (no override), matching the v2.2 FIX-001 fix.
_CHROMIUM_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.6261.128 Safari/537.36",
]

# Viewport / timezone personas — randomised for attempt 3 (new process)
_PERSONAS = [
    {"width": 1280, "height": 800,  "tz": "Asia/Kolkata"},
    {"width": 1920, "height": 1080, "tz": "Asia/Kolkata"},
    {"width": 1366, "height": 768,  "tz": "Asia/Kolkata"},
    {"width": 1440, "height": 900,  "tz": "Asia/Kolkata"},
]

# Cache URL templates for attempt 4
_CACHE_URLS = [
    "https://webcache.googleusercontent.com/search?q=cache:{url}",
    "https://cc.bingj.com/cache.aspx?url={url}",
]


# ── Engine ────────────────────────────────────────────────────────────────────

class ScraperEngine:
    """
    Public surface of scraper_v2.

    Caller interface:
        engine = ScraperEngine()
        response = engine.scrape(url)
        engine.close()

    Or as a context manager:
        with ScraperEngine() as engine:
            response = engine.scrape(url)

    The caller provides only the URL.
    Everything else (portal resolution, browser engine, retry strategy)
    is decided internally.
    """

    def __init__(self) -> None:
        self._pw       = sync_playwright().start()
        self._browser  = self._launch_chromium()
        self._scraper  = GenericScraper()

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape(self, url: str) -> ScrapeResponse:
        """
        Scrape a product URL through the 5-attempt retry cascade.

        Args:
            url: Any supported product URL (amazon.in, flipkart.com, myntra.com).
                 Portal is resolved internally from the domain.

        Returns:
            ScrapeResponse — success=True with product data, or
            success=False with error_type, error_message, and diagnostics.
            Never raises.
        """
        config = self._resolve_config(url)
        if config is None:
            return ScrapeResponse(
                job_id=str(uuid.uuid4()),
                success=False,
                portal="unknown",
                error_type=ScrapeFailureReason.ALL_LAYERS_FAILED,
                error_message=f"No portal config found for URL: {url!r:.200}",
            )

        job_id = str(uuid.uuid4())   # one ID for the full cascade

        logger.info(
            f"[ENGINE] scrape start — "
            f"portal={config.name} "
            f"job_id={job_id} "
            f"url={url!r:.200}"
        )

        last_response: Optional[ScrapeResponse] = None
        last_cause:    Optional[FailureCause]   = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            mechanism = self._pick_mechanism(attempt, last_cause, config)

            logger.info(
                f"[ATTEMPT] "
                f"attempt={attempt}/{_MAX_ATTEMPTS} "
                f"mechanism={mechanism} "
                f"portal={config.name} "
                f"prev_cause={last_cause}"
            )

            # Rate-limit back-off before retrying
            if last_cause == FailureCause.RATE_LIMITED:
                logger.info(
                    f"[ATTEMPT] rate-limited — "
                    f"sleeping {_RATE_LIMIT_BACKOFF_S}s before attempt={attempt}"
                )
                time.sleep(_RATE_LIMIT_BACKOFF_S)
            elif attempt > 1 and mechanism != RetryMechanism.GIVE_UP:
                # Progressive delay between real attempts — 2s, 4s, 6s, 8s.
                # Skip for GIVE_UP — no point waiting before immediately breaking.
                delay = _RETRY_DELAY_BASE_S * (attempt - 1)
                logger.info(
                    f"[ATTEMPT] progressive delay — "
                    f"sleeping {delay}s before attempt={attempt}"
                )
                time.sleep(delay)

            # ── Dispatch to the right attempt handler ─────────────────────────
            try:
                if mechanism == RetryMechanism.CACHED_PAGE:
                    response = self._attempt_cached_page(url, config, attempt, job_id)
                elif mechanism == RetryMechanism.SCRAPERAPI:
                    response = self._attempt_scraperapi(url, config, attempt, job_id)
                elif mechanism == RetryMechanism.GIVE_UP:
                    logger.error(
                        f"[ATTEMPT] give_up — no ScraperAPI key configured, "
                        f"cannot proceed further — portal={config.name}"
                    )
                    break
                else:
                    response = self._attempt_browser(url, config, attempt, mechanism, job_id)
            except Exception as exc:
                # Unexpected error inside an attempt — log, treat as unknown, continue
                logger.error(
                    f"[ATTEMPT] unhandled exception — "
                    f"attempt={attempt} "
                    f"mechanism={mechanism} "
                    f"portal={config.name} "
                    f"error={type(exc).__name__}: {exc}"
                )
                last_cause = FailureCause.UNKNOWN
                continue

            if response.success:
                logger.info(
                    f"[ENGINE] success — "
                    f"portal={config.name} "
                    f"attempt={attempt} "
                    f"mechanism={mechanism} "
                    f"price={response.current_price} "
                    f"method={response.extraction_method}"
                )
                return response

            # Failed — classify and decide next attempt
            last_response = response
            diag          = classifier.classify(response)
            last_cause    = diag.cause

            logger.warning(
                f"[ATTEMPT] failed — "
                f"attempt={attempt}/{_MAX_ATTEMPTS} "
                f"mechanism={mechanism} "
                f"cause={diag.cause} "
                f"portal={config.name}"
            )

            if attempt < _MAX_ATTEMPTS:
                next_mech = self._pick_mechanism(attempt + 1, last_cause, config)
                logger.info(
                    f"[ATTEMPT] escalating — "
                    f"{mechanism} → {next_mech} "
                    f"portal={config.name}"
                )

        logger.error(
            f"[ENGINE] all {_MAX_ATTEMPTS} attempts exhausted — "
            f"portal={config.name} "
            f"url={url!r:.200}"
        )
        return last_response or ScrapeResponse(
            job_id=job_id,
            success=False,
            portal=config.name,
            error_type=ScrapeFailureReason.ALL_LAYERS_FAILED,
            error_message=f"All {_MAX_ATTEMPTS} attempts exhausted",
        )

    def close(self) -> None:
        """Release the long-lived Chromium browser and Playwright instance."""
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── Mechanism picker ──────────────────────────────────────────────────────

    def _pick_mechanism(
        self,
        attempt: int,
        last_cause: Optional[FailureCause],
        config: PortalConfig,
    ) -> RetryMechanism:
        """
        Decide which mechanism to use for this attempt.

        Standard cascade:
            1 → NEW_CONTEXT  (same Chromium browser, fresh context)
            2 → NEW_CONTEXT  (rotated UA, cleared cookies)
            3 → FIREFOX      (new process, TLS fingerprint change)
            4 → CACHED_PAGE  (Google Cache → Bing Cache)
            5 → SCRAPERAPI   (or GIVE_UP if no key configured)

        Cause-aware fast-paths (applied before cascade):
            IP_BLOCK / CAPTCHA → SCRAPERAPI immediately (skip browser attempts)
            FINGERPRINT        → FIREFOX immediately
            WAF_CHALLENGE      → NEW_CONTEXT (fresh context resolves most WAF slippage)
        """
        # Fast-paths: causes where more browser attempts are pointless
        if last_cause in (FailureCause.IP_BLOCK, FailureCause.CAPTCHA):
            if self._has_scraperapi():
                logger.info(
                    f"[MECHANISM] cause={last_cause} + ScraperAPI key present "
                    f"→ jumping to scraperapi"
                )
                return RetryMechanism.SCRAPERAPI

        if last_cause == FailureCause.FINGERPRINT:
            logger.info(f"[MECHANISM] cause=fingerprint → jumping to firefox")
            return RetryMechanism.FIREFOX

        # Standard cascade
        # Amazon blocks archiving (noarchive meta tag) — Google Cache and Bing
        # Cache always return empty for Amazon URLs. Skip cached_page for amazon
        # and go straight to scraperapi at attempt 4.
        if config.name == "amazon":
            cascade = {
                1: RetryMechanism.NEW_CONTEXT,
                2: RetryMechanism.NEW_CONTEXT,
                3: RetryMechanism.FIREFOX,
                4: RetryMechanism.SCRAPERAPI if self._has_scraperapi() else RetryMechanism.GIVE_UP,
                5: RetryMechanism.SCRAPERAPI if self._has_scraperapi() else RetryMechanism.GIVE_UP,
            }
        else:
            cascade = {
                1: RetryMechanism.NEW_CONTEXT,
                2: RetryMechanism.NEW_CONTEXT,
                3: RetryMechanism.FIREFOX,
                4: RetryMechanism.CACHED_PAGE,
                5: RetryMechanism.SCRAPERAPI if self._has_scraperapi() else RetryMechanism.GIVE_UP,
            }
        return cascade.get(attempt, RetryMechanism.GIVE_UP)

    # ── Attempt 1 & 2: browser-based ─────────────────────────────────────────

    def _attempt_browser(
        self,
        url: str,
        config: PortalConfig,
        attempt: int,
        mechanism: RetryMechanism,
        job_id: str,
    ) -> ScrapeResponse:
        """
        Run one browser-based attempt.

        mechanism=NEW_CONTEXT  → use self._browser (long-lived Chromium)
        mechanism=FIREFOX      → open a short-lived Firefox process

        Context configuration follows v2.2 FIX-001/002:
            - Myntra or Firefox engine → NO user_agent override
              (Firefox TLS profile must match the Firefox UA)
            - Chromium + other portals → explicit Chrome UA + Sec-Fetch headers
        """
        use_firefox = (
            mechanism == RetryMechanism.FIREFOX
            or config.browser == "firefox"
        )
        persona = random.choice(_PERSONAS)

        logger.info(
            f"[BROWSER] "
            f"attempt={attempt} "
            f"portal={config.name} "
            f"engine={'firefox' if use_firefox else 'chromium'} "
            f"viewport={persona['width']}x{persona['height']}"
        )

        if use_firefox:
            # Short-lived Firefox browser — reuse self._pw (already started).
            # Do NOT call sync_playwright() again — FastAPI runs inside an
            # asyncio loop and a second sync_playwright() call crashes with
            # "Playwright Sync API inside the asyncio loop".
            browser = self._pw.firefox.launch(headless=True)
            try:
                ctx  = self._build_context(browser, config, persona, use_firefox=True)
                page = ctx.new_page()
                return self._scraper.scrape(
                    page=page, url=url, config=config,
                    job_id=job_id, attempt_number=attempt,
                )
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
        else:
            # Reuse the long-lived self._browser — just open a fresh context
            ctx = self._build_context(self._browser, config, persona, use_firefox=False)
            try:
                page = ctx.new_page()
                self._apply_stealth(page)
                return self._scraper.scrape(
                    page=page, url=url, config=config,
                    job_id=job_id, attempt_number=attempt,
                )
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass

    # ── Attempt 4: cached page ────────────────────────────────────────────────

    def _attempt_cached_page(
        self,
        url: str,
        config: PortalConfig,
        attempt: int,
        job_id: str,
    ) -> ScrapeResponse:
        """
        Try Google Cache then Bing Cache in order.
        Cached pages are static HTML — zero bot detection.
        GenericScraper's extraction layers run on the cached HTML normally.
        Original URL is passed to scraper so product_id extraction works.
        """
        for template in _CACHE_URLS:
            cache_url = template.format(url=quote_plus(url))
            logger.info(
                f"[CACHED_PAGE] "
                f"attempt={attempt} "
                f"portal={config.name} "
                f"cache_url={cache_url!r:.200}"
            )
            # Reuse self._pw — do NOT call sync_playwright() again inside asyncio loop
            browser = self._pw.chromium.launch(headless=True)
            try:
                ctx  = browser.new_context(
                    user_agent=random.choice(_CHROMIUM_USER_AGENTS),
                    locale="en-IN",
                )
                page = ctx.new_page()
                try:
                    page.goto(
                        cache_url,
                        timeout=30_000,
                        wait_until="domcontentloaded",
                    )
                except PlaywrightTimeout:
                    logger.warning(
                        f"[CACHED_PAGE] timeout — "
                        f"cache_url={cache_url!r:.200}"
                    )
                    browser.close()
                    continue

                body_len = 0
                try:
                    body_len = len(page.inner_text("body") or "")
                except Exception:
                    pass

                if body_len < 500:
                    logger.warning(
                        f"[CACHED_PAGE] empty body (len={body_len}) — "
                        f"cache miss or blocked"
                    )
                    browser.close()
                    continue

                response = self._scraper.scrape(
                    page=page,
                    url=url,           # original URL — product_id extraction
                    config=config,
                    job_id=job_id,
                    attempt_number=attempt,
                )
                if response.success:
                    logger.info(
                        f"[CACHED_PAGE] success — "
                        f"price={response.current_price} "
                        f"cache_url={cache_url!r:.200}"
                    )
                return response
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        return ScrapeResponse(
            job_id=job_id,
            success=False,
            portal=config.name,
            attempt_number=attempt,
            error_type=ScrapeFailureReason.ALL_LAYERS_FAILED,
            error_message="All cache sources returned empty or timed out",
        )

    # ── Attempt 5: ScraperAPI ─────────────────────────────────────────────────

    def _attempt_scraperapi(
        self,
        url: str,
        config: PortalConfig,
        attempt: int,
        job_id: str,
    ) -> ScrapeResponse:
        """
        Fetch rendered HTML via ScraperAPI (residential proxy, CAPTCHA solving),
        then feed it into GenericScraper via page.set_content().
        Same pattern as ScraperAPIFallback in LLD §11.4 — but uses
        scraper_v2's GenericScraper instead of the old platform-specific scrapers.

        Falls back to GIVE_UP response if SCRAPER_API_KEY is not set.
        """
        import requests

        api_key = self._scraperapi_key()
        if not api_key:
            logger.warning(
                f"[SCRAPERAPI] SCRAPER_API_KEY not set — "
                f"cannot attempt ScraperAPI fallback for portal={config.name}"
            )
            return ScrapeResponse(
                job_id=job_id,
                success=False,
                portal=config.name,
                attempt_number=attempt,
                error_type=ScrapeFailureReason.ALL_LAYERS_FAILED,
                error_message="ScraperAPI key not configured",
            )

        logger.info(
            f"[SCRAPERAPI] "
            f"attempt={attempt} "
            f"portal={config.name} "
            f"url={url!r:.200}"
        )

        # premium=true uses ScraperAPI's residential proxy pool with full
        # JS rendering — required for React SPAs like Myntra where price is
        # injected by JS after initial HTML load.
        # premium costs 10 credits per request vs 1 for standard.
        # Only enabled for portals that need it (Myntra confirmed, others TBD).
        use_premium = config.name in ("myntra",)

        try:
            params = {
                "api_key":      api_key,
                "url":          url,
                "render":       "true",
                "country_code": "in",
            }
            if use_premium:
                params["premium"] = "true"

            resp = requests.get(
                "http://api.scraperapi.com",
                params=params,
                timeout=120,  # premium requests take longer
            )
        except requests.RequestException as exc:
            logger.error(
                f"[SCRAPERAPI] request failed — "
                f"portal={config.name} "
                f"error={exc}"
            )
            return ScrapeResponse(
                job_id=job_id,
                success=False,
                portal=config.name,
                attempt_number=attempt,
                error_type=ScrapeFailureReason.TIMEOUT,
                error_message=f"ScraperAPI network error: {exc}",
            )

        logger.info(
            f"[SCRAPERAPI] response — "
            f"http_status={resp.status_code} "
            f"content_length={len(resp.text)}"
        )

        if resp.status_code != 200:
            return ScrapeResponse(
                job_id=job_id,
                success=False,
                portal=config.name,
                attempt_number=attempt,
                error_type=ScrapeFailureReason.BOT_DETECTED,
                error_message=f"ScraperAPI HTTP {resp.status_code}",
            )

        # Feed rendered HTML into GenericScraper via page.set_content()
        # Reuse self._pw — do NOT call sync_playwright() again inside asyncio loop
        browser = self._pw.chromium.launch(headless=True)
        try:
            ctx  = browser.new_context()
            page = ctx.new_page()
            page.set_content(resp.text, wait_until="domcontentloaded")
            return self._scraper.scrape(
                page=page,
                url=url,
                config=config,
                job_id=job_id,
                attempt_number=attempt,
            )
        finally:
            try:
                browser.close()
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_config(self, url: str) -> Optional[PortalConfig]:
        """Resolve PortalConfig from URL domain. Returns None on failure."""
        try:
            domain = urlparse(url).netloc.lstrip("www.")
            return get_config_for_domain(domain)
        except Exception as exc:
            logger.error(
                f"[ENGINE] portal config not found — "
                f"url={url!r:.200} "
                f"error={exc}"
            )
            return None

    def _build_context(
        self,
        browser: Browser,
        config: PortalConfig,
        persona: dict,
        use_firefox: bool,
    ) -> BrowserContext:
        """
        Build a BrowserContext following the v2.2 FIX-001/002 context split:

        Firefox / Myntra → no user_agent override (Firefox TLS ↔ Firefox UA must match)
        Chromium / other → explicit Chrome UA + timezone + Sec-Fetch headers
        """
        base = {
            "viewport":    {"width": persona["width"], "height": persona["height"]},
            "locale":      "en-IN",
            "timezone_id": persona["tz"],
        }
        if use_firefox or config.name == "myntra":
            # No UA override — Playwright uses the real Firefox UA
            return browser.new_context(**base)
        else:
            return browser.new_context(
                **base,
                user_agent=random.choice(_CHROMIUM_USER_AGENTS),
                extra_http_headers={
                    "Accept-Language":           "en-IN,en;q=0.9",
                    "Sec-Fetch-Dest":            "document",
                    "Sec-Fetch-Mode":            "navigate",
                    "Sec-Fetch-Site":            "none",
                    "Sec-Fetch-User":            "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

    def _apply_stealth(self, page) -> None:
        """
        Apply playwright-stealth. Uses Stealth().apply_stealth_sync(page)
        per DEV-004 (v1.0 changelog) — stealth_sync() was removed in v2.0.3.
        Silently skips if import fails (non-fatal).
        """
        try:
            from playwright_stealth import Stealth
            Stealth().apply_stealth_sync(page)
        except Exception as exc:
            logger.debug(f"[ENGINE] stealth apply skipped — {exc}")

    def _launch_chromium(self) -> Browser:
        return self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-http2",
            ],
        )

    def _has_scraperapi(self) -> bool:
        return bool(self._scraperapi_key())

    def _scraperapi_key(self) -> str:
        """
        Read ScraperAPI key.
        scraper_v2/core/config.py delegates to app.core.config when embedded
        in PriceMonitor (load_config() pattern from v2.0). Falls back to env var
        for standalone use (run_test.py).
        """
        # scraper_v2-internal config (load_config() in scraper_v2/core/config.py
        # already reads from app.core.config when available)
        try:
            from app.core.config import settings as app_settings
            return app_settings.scraper_api_key or ""
        except Exception:
            pass
        import os
        return os.getenv("SCRAPER_API_KEY", "")
