"""
Pre-extract hooks — portal-specific page interactions before extraction begins.

This is the ONLY file in scraper_v2 that contains portal-specific Python.
Everything else is driven by portals.yaml.

Adding a hook for a new portal:
    1. Write a function here: def my_hook(page: Page) -> None
    2. Register it in _HOOKS dict below
    3. Reference it in portals.yaml: pre_extract_hook: my_hook

Hook functions must:
    - Accept a Page argument and an optional url keyword argument
    - Return None
    - Never raise — swallow all exceptions (hook failure must not abort scrape)
    - Complete quickly — they run before extraction, blocking the worker
"""

from typing import Callable, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)


# ── Hook implementations ──────────────────────────────────────────────────────

def dismiss_flipkart_login(page: Page, url: Optional[str] = None) -> None:
    """
    Dismiss Flipkart's login popup if it appears.
    Tries multiple known close button selectors in order.
    Silently continues if popup is not present.
    """
    # Check quickly if a modal is present at all before trying selectors.
    # Flipkart shows the login modal inconsistently — most headless loads skip it.
    # Use a short initial probe (500ms) to avoid 2s × N selector timeouts when
    # no modal is present, which was causing ~10s of dead time per scrape.
    PROBE_MS = 500   # fast check per selector
    CLICK_WAIT_MS = 400

    close_selectors = [
        # Confirmed variants (check newest first)
        "[data-testid='login-popup-close']",
        "button[class*='_6o2Ww']",
        "button._2KpZ6l._2doB4z",
        "button[class*='_2doB4z']",
        "span._30XB9F",
    ]
    for selector in close_selectors:
        try:
            el = page.wait_for_selector(selector, timeout=PROBE_MS)
            if el:
                el.click()
                page.wait_for_timeout(CLICK_WAIT_MS)
                logger.debug(
                    f"[HOOK] dismiss_flipkart_login — dismissed via {selector!r}"
                )
                return
        except PlaywrightTimeout:
            continue
        except Exception as exc:
            logger.debug(f"[HOOK] dismiss_flipkart_login — selector {selector!r} error: {exc}")
            continue

    logger.debug("[HOOK] dismiss_flipkart_login — no popup found, continuing")


def simulate_amazon_human_behaviour(page: Page, url: Optional[str] = None) -> None:
    """
    Simulate light human behaviour on Amazon before extraction begins.

    Goal: reduce the probability that Amazon serves the bot-detection
    interstitial page. This hook does NOT click through any interstitial —
    if Amazon still shows one, bot detection fires and ScraperAPIFallback
    takes over (correct behaviour).

    Actions (all silent — never raises):
        1. Random mouse movement across the viewport.
        2. Smooth scroll down ~30 % of the page, then back up a little.
        3. Short random dwell pause (800–1400 ms).

    Args:
        page: Current Playwright Page (already navigated to product URL).
        url:  Unused — accepted for hook signature compatibility.
    """
    import random

    try:
        # 1. Random mouse movement — 3 gentle arcs across the viewport
        vw, vh = 1280, 800
        for _ in range(3):
            x = random.randint(200, vw - 200)
            y = random.randint(100, vh - 100)
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(80, 180))

        # 2. Scroll down ~30 % of page height, pause, scroll back up slightly
        page.evaluate("window.scrollBy(0, Math.floor(document.body.scrollHeight * 0.30))")
        page.wait_for_timeout(random.randint(300, 600))
        page.evaluate("window.scrollBy(0, -120)")

        # 3. Random dwell time
        page.wait_for_timeout(random.randint(800, 1400))

        logger.debug("[HOOK] simulate_amazon_human_behaviour — done")
    except Exception as exc:
        logger.debug(f"[HOOK] simulate_amazon_human_behaviour — {exc}")


def patch_myntra_headless(page: Page, url: Optional[str] = None) -> None:
    """
    Patch browser properties that Myntra uses to detect headless Chromium.

    Myntra performs TLS + JS fingerprinting and drops headless connections
    at the network level. This hook runs JS overrides on the already-loaded
    page to mask headless signals for subsequent XHR/fetch calls, and adds
    realistic interaction signals (mouse move, scroll) before extraction.

    Args:
        page: Current Playwright Page (already navigated).
        url:  Unused — accepted for hook signature compatibility.
    """
    import random

    try:
        # Patch JS properties that headless Chrome exposes
        page.evaluate("""() => {
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Spoof plugins (headless has 0)
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            // Spoof languages
            Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en']});
            // Remove headless from userAgent
            Object.defineProperty(navigator, 'userAgent', {
                get: () => navigator.userAgent.replace('Headless', '')
            });
        }""")

        # Gentle human-like interactions
        vw, vh = 1280, 800
        for _ in range(2):
            page.mouse.move(
                random.randint(300, vw - 300),
                random.randint(200, vh - 200)
            )
            page.wait_for_timeout(random.randint(60, 140))

        page.evaluate("window.scrollBy(0, Math.floor(document.body.scrollHeight * 0.25))")
        page.wait_for_timeout(random.randint(500, 900))

        logger.debug("[HOOK] patch_myntra_headless — done")
    except Exception as exc:
        logger.debug(f"[HOOK] patch_myntra_headless — {exc}")


# ── Registry ──────────────────────────────────────────────────────────────────

_HOOKS: dict[str, Callable] = {
    "dismiss_flipkart_login": dismiss_flipkart_login,
    "simulate_amazon_human_behaviour": simulate_amazon_human_behaviour,
    "patch_myntra_headless": patch_myntra_headless,
}


def run(hook_name: str, page: Page, url: Optional[str] = None) -> None:
    """
    Execute a named hook. Silently skips unknown hook names.
    All exceptions inside hook functions are caught and logged.
    Hook failure never aborts a scrape.

    Args:
        hook_name: Name registered in _HOOKS.
        page:      Current Playwright Page.
        url:       Original product URL — passed to hooks that need it
                   (e.g. simulate_amazon_human_behaviour).
    """
    fn = _HOOKS.get(hook_name)
    if fn is None:
        logger.warning(f"[HOOK] Unknown hook '{hook_name}' — skipping")
        return
    try:
        fn(page, url=url)
    except Exception as exc:
        logger.warning(f"[HOOK] Hook '{hook_name}' raised unexpectedly — {exc}")


def available_hooks() -> list[str]:
    """Return all registered hook names. Useful for config validation."""
    return list(_HOOKS.keys())
