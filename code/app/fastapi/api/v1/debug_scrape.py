"""
app/fastapi/api/v1/debug_scrape.py

Diagnostic endpoint for debugging scraper failures on Railway.
Protected by Bearer token (same SECRET_KEY as other internal endpoints).

POST /v1/internal/debug-scrape
{
    "url": "https://www.myntra.com/...",
    "browser": "firefox",          // optional — "chromium" | "firefox", default auto-detected from portals.yaml
    "context_options": {           // optional — passed directly to browser.new_context()
        "locale": "en-IN",
        "user_agent": "Mozilla/5.0 ..."
    },
    "wait_until": "domcontentloaded",  // optional — Playwright goto wait_until strategy
    "post_nav_wait_ms": 2000,          // optional — extra wait after navigation (ms)
    "html_chars": 5000                 // optional — how many chars of HTML to return (max 50000)
}

Response:
{
    "url_requested": "...",
    "url_final": "...",          // URL after all redirects
    "http_status": 200,          // HTTP status of the final response
    "response_headers": {...},   // response headers from the final response
    "page_title": "...",
    "html_length": 94832,        // total bytes in page.content()
    "html_head": "...",          // first html_chars chars
    "html_tail": "...",          // last 2000 chars (often where bot-block messages appear)
    "navigation_ms": 3241,
    "browser_used": "firefox",
    "context_options_used": {...},
    "error": null                // set if navigation itself threw
}
"""

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.fastapi.dependencies import verify_internal_token
from app.utils.logging import get_logger

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)
logger = get_logger(__name__)

_MAX_HTML_CHARS = 50_000
_DEFAULT_HTML_CHARS = 5_000
_DEFAULT_GOTO_TIMEOUT_MS = 30_000


# --------------------------------------------------------------------------- #
# Request / response schemas                                                  #
# --------------------------------------------------------------------------- #

class DebugScrapeRequest(BaseModel):
    url: str
    browser: Optional[str] = None           # "chromium" | "firefox" — None = auto from portals.yaml
    context_options: Optional[dict[str, Any]] = None   # passed to browser.new_context()
    wait_until: str = "domcontentloaded"
    post_nav_wait_ms: int = 0
    html_chars: int = _DEFAULT_HTML_CHARS
    goto_timeout_ms: int = _DEFAULT_GOTO_TIMEOUT_MS


class DebugScrapeResponse(BaseModel):
    url_requested: str
    url_final: Optional[str]
    http_status: Optional[int]
    response_headers: Optional[dict[str, str]]
    page_title: Optional[str]
    html_length: Optional[int]
    html_head: Optional[str]       # first html_chars chars
    html_tail: Optional[str]       # last 2000 chars — useful for catching end-of-page bot messages
    navigation_ms: Optional[int]
    browser_used: str
    context_options_used: dict[str, Any]
    error: Optional[str]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _resolve_browser(url: str, explicit: Optional[str]) -> str:
    """
    If caller didn't specify a browser, look up portals.yaml for the URL's domain.
    Falls back to chromium if domain not found or portals.yaml unavailable.
    """
    if explicit:
        return explicit.lower()

    try:
        from app.scraper_v2.scrapers.registry import get_portal_config
        config = get_portal_config(url)
        if config:
            return config.browser or "chromium"
    except Exception:
        pass

    # Cheap domain-based default as last resort
    if "myntra.com" in url:
        return "firefox"
    return "chromium"


def _default_context_options() -> dict[str, Any]:
    return {
        "locale": "en-IN",
        "viewport": {"width": 1280, "height": 900},
        "extra_http_headers": {
            "Accept-Language": "en-IN,en;q=0.9",
        },
    }


# --------------------------------------------------------------------------- #
# Endpoint                                                                    #
# --------------------------------------------------------------------------- #

@router.post(
    "/debug-scrape",
    response_model=DebugScrapeResponse,
    summary="Diagnostic: navigate to a URL and return raw page info",
)
def debug_scrape(body: DebugScrapeRequest) -> DebugScrapeResponse:
    """
    Launches a browser, navigates to the given URL, and returns:
    - Final URL after redirects
    - HTTP response status
    - Response headers
    - Page title
    - First N chars of HTML (html_head) and last 2000 chars (html_tail)
    - Navigation timing

    No extraction logic runs. This is a pure diagnostic tool to understand
    what a portal returns on Railway vs locally.

    Protected by Bearer token (SECRET_KEY).
    """
    html_chars = min(body.html_chars, _MAX_HTML_CHARS)
    browser_name = _resolve_browser(body.url, body.browser)

    # Merge caller-supplied context options over defaults
    ctx_opts = _default_context_options()
    if body.context_options:
        ctx_opts.update(body.context_options)

    logger.info(
        f"debug_scrape — starting — url={body.url} browser={browser_name} "
        f"wait_until={body.wait_until} post_nav_wait_ms={body.post_nav_wait_ms}"
    )

    url_final = None
    http_status = None
    response_headers = None
    page_title = None
    html_length = None
    html_head = None
    html_tail = None
    navigation_ms = None
    error_msg = None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            # Launch correct browser engine
            if browser_name == "firefox":
                browser = pw.firefox.launch(headless=True)
            else:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--disable-http2"],
                )

            context = browser.new_context(**ctx_opts)

            # Capture response from the final navigation (after redirects)
            final_response = None

            def on_response(response):
                nonlocal final_response
                # Track the last response that matches our target domain
                # (ignores sub-resource responses like images/JS)
                if body.url.split("/")[2] in response.url or response.url == body.url:
                    final_response = response

            page = context.new_page()
            page.on("response", on_response)

            t0 = time.monotonic()
            try:
                nav_response = page.goto(
                    body.url,
                    wait_until=body.wait_until,
                    timeout=body.goto_timeout_ms,
                )
            except Exception as nav_exc:
                # Navigation itself failed (timeout, connection refused, etc.)
                error_msg = f"page.goto() raised: {type(nav_exc).__name__}: {nav_exc}"
                logger.info(f"debug_scrape — navigation error — {error_msg}")
                context.close()
                browser.close()
                return DebugScrapeResponse(
                    url_requested=body.url,
                    url_final=None,
                    http_status=None,
                    response_headers=None,
                    page_title=None,
                    html_length=None,
                    html_head=None,
                    html_tail=None,
                    navigation_ms=None,
                    browser_used=browser_name,
                    context_options_used=ctx_opts,
                    error=error_msg,
                )

            navigation_ms = int((time.monotonic() - t0) * 1000)

            # Optional post-navigation wait (e.g. React hydration)
            if body.post_nav_wait_ms > 0:
                page.wait_for_timeout(body.post_nav_wait_ms)

            # Capture final URL and status from nav_response (the main frame response)
            if nav_response:
                http_status = nav_response.status
                try:
                    response_headers = dict(nav_response.headers)
                except Exception:
                    response_headers = {}
            else:
                http_status = None
                response_headers = {}

            url_final = page.url

            # Page title
            try:
                page_title = page.title()
            except Exception:
                page_title = None

            # Full HTML
            try:
                html = page.content()
                html_length = len(html)
                html_head = html[:html_chars]
                html_tail = html[-2000:] if html_length > html_chars + 2000 else None
            except Exception as html_exc:
                error_msg = f"page.content() raised: {html_exc}"

            context.close()
            browser.close()

    except Exception as exc:
        error_msg = f"Playwright setup error: {type(exc).__name__}: {exc}"
        logger.info(f"debug_scrape — playwright error — {error_msg}")

    logger.info(
        f"debug_scrape — done — url_final={url_final} http_status={http_status} "
        f"html_length={html_length} navigation_ms={navigation_ms} error={error_msg}"
    )

    return DebugScrapeResponse(
        url_requested=body.url,
        url_final=url_final,
        http_status=http_status,
        response_headers=response_headers,
        page_title=page_title,
        html_length=html_length,
        html_head=html_head,
        html_tail=html_tail,
        navigation_ms=navigation_ms,
        browser_used=browser_name,
        context_options_used=ctx_opts,
        error=error_msg,
    )
