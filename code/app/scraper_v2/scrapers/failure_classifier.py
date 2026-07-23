"""
FailureClassifier — diagnoses why a ScrapeResponse failed.

File: app/scraper_v2/scrapers/failure_classifier.py

Public API:
    from app.scraper_v2.scrapers.failure_classifier import classifier
    diag = classifier.classify(response)

The caller passes a ScrapeResponse. The classifier reads its fields
(error_type, error_message, navigation_ms, layers_attempted, layers_failed,
portal) and returns a FailureDiagnosis. No live Playwright Page is needed.

portal_name is read from response.portal — the scraper already sets this
field, so the caller doesn't have to pass it separately.

Failure causes grounded in actual Railway observations (v2.2, v2.3):

    IP_BLOCK       Myntra 481-byte body / 200ms nav — Railway IP range banned
    CAPTCHA        Amazon "api-services-support" page, Flipkart reCAPTCHA 403
    WAF_CHALLENGE  Amazon AWS WAF JS challenge (3506 bytes, ~240ms nav)
                   FIX-005 in generic_scraper handles this normally; classifier
                   fires only if it slips through
    FINGERPRINT    Myntra Chrome-UA-on-Firefox TLS mismatch (v2.2 FIX-001/002)
    RATE_LIMITED   HTTP 429 / "too many requests"
    CSS_STALE      Page healthy, selector layer failed — Flipkart class rotation
    HTML_STRUCTURE Page loaded but price element never rendered
    TIMEOUT        page.goto() exceeded timeout
    UNKNOWN        None of the above

Retry mechanisms (what engine.py uses to pick the next attempt):

    NEW_CONTEXT  Fresh BrowserContext + rotated UA + cleared cookies
    FIREFOX      Switch browser engine (TLS fingerprint bypass)
    NEW_PROCESS  Close + relaunch entire browser process
    CACHED_PAGE  Google Cache / Bing Cache — static HTML, zero bot detection
    SCRAPERAPI   ScraperAPI residential proxy
    WAIT_RETRY   Back off then retry same config (rate limit only)
    GIVE_UP      No retry will help

Logger uses f-strings only (DEV-006 from v1.0 changelog).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)


# ── Taxonomy ──────────────────────────────────────────────────────────────────

class FailureCause(str, Enum):
    IP_BLOCK       = "ip_block"
    CAPTCHA        = "captcha"
    WAF_CHALLENGE  = "waf_challenge"
    FINGERPRINT    = "fingerprint"
    RATE_LIMITED   = "rate_limited"
    CSS_STALE      = "css_stale"
    HTML_STRUCTURE = "html_structure"
    TIMEOUT        = "timeout"
    UNKNOWN        = "unknown"


class RetryMechanism(str, Enum):
    NEW_CONTEXT  = "new_context"
    FIREFOX      = "firefox"
    NEW_PROCESS  = "new_process"
    CACHED_PAGE  = "cached_page"
    SCRAPERAPI   = "scraperapi"
    WAIT_RETRY   = "wait_retry"
    GIVE_UP      = "give_up"


@dataclass
class FailureDiagnosis:
    cause:      FailureCause
    mechanism:  RetryMechanism
    confidence: float       # 0.0–1.0
    evidence:   list[str]   # logged at WARNING level on every diagnosis


# ── Signal strings ────────────────────────────────────────────────────────────
# Matched against response.error_message.lower().
# Values come from GenericScraper's actual error_message strings.

_WAF_SIGNALS        = ["awswaf", "awswafintegration", "waf challenge", "challenge page"]
_CAPTCHA_SIGNALS    = [
    "api-services-support@amazon.com",  # Amazon CAPTCHA page footer (v2.2)
    "enter the characters you see",
    "bot detection indicator",          # ScrapeBotDetectedError prefix in generic_scraper
    "captcha", "recaptcha", "robot check",
    "verify you are human", "unusual traffic",
]
_IP_BLOCK_SIGNALS   = [
    "access denied", "request could not be satisfied",  # CloudFront 403
    "your ip", "blocked", "sorry, you have been blocked",
]
_RATE_LIMIT_SIGNALS = ["429", "too many requests", "rate limit", "throttl", "retry-after"]
_FINGERPRINT_SIGNALS= ["headless", "automated", "webdriver", "bot detected", "tls", "fingerprint"]
_TIMEOUT_SIGNALS    = ["timed out", "timeout", "playwright timeout"]

# Navigation time below this = block/challenge page, not a real product page.
# Observed: Myntra IP block ~200ms, Amazon WAF challenge ~240ms.
# Real pages: Amazon 7–10s total, Flipkart ~3–4s (v2.0 portal test results).
_FAST_NAV_MS = 800


# ── Classifier ────────────────────────────────────────────────────────────────

class FailureClassifier:
    """
    Stateless — safe as a module-level singleton.
    Reads only ScrapeResponse fields. No browser or Page access.
    """

    def classify(self, response) -> FailureDiagnosis:
        """
        Args:
            response: A ScrapeResponse where success=False.
                      portal field is read internally — caller does not supply it.

        Returns:
            FailureDiagnosis with cause, mechanism, confidence, evidence.
        """
        from app.scraper_v2.models.scrape_result import ScrapeFailureReason

        portal         = getattr(response, "portal",           "") or ""
        error_type     = getattr(response, "error_type",       None)
        error_msg      = (getattr(response, "error_message",   None) or "").lower()
        nav_ms         = getattr(response, "navigation_ms",    None) or 0
        layers_tried   = getattr(response, "layers_attempted", None) or []
        layers_failed  = getattr(response, "layers_failed",    None) or []
        evidence: list[str] = []

        # ── 1. Timeout ────────────────────────────────────────────────────────
        if error_type == ScrapeFailureReason.TIMEOUT or self._hit(error_msg, _TIMEOUT_SIGNALS):
            evidence.append(f"error_type=TIMEOUT — error_message={error_msg!r:.120}")
            return self._build(FailureCause.TIMEOUT, RetryMechanism.NEW_CONTEXT,
                               0.95, evidence, portal)

        # ── 2. Fast navigation = block/challenge page returned immediately ────
        # Guard: only fires when layers_tried is empty or very short.
        # If all 6 layers ran, the page loaded fine regardless of nav_ms —
        # local machines nav to Amazon in ~500ms legitimately.
        # On Railway the WAF challenge page returns ~240ms AND only 0-1 layers run.
        if 0 < nav_ms < _FAST_NAV_MS and len(layers_tried) <= 1:
            if portal == "myntra":
                evidence.append(
                    f"nav_ms={nav_ms}ms + {len(layers_tried)} layer(s) tried on myntra — "
                    f"Railway IP block (v2.1 DEV-004 signature: ~200ms, 481 bytes)."
                )
                return self._build(FailureCause.IP_BLOCK, RetryMechanism.SCRAPERAPI,
                                   0.95, evidence, portal)
            if portal == "amazon":
                evidence.append(
                    f"nav_ms={nav_ms}ms + {len(layers_tried)} layer(s) tried on amazon — "
                    f"likely AWS WAF JS challenge page (v2.2 FIX-005 signature: ~240ms, 3506 bytes)."
                )
                return self._build(FailureCause.WAF_CHALLENGE, RetryMechanism.NEW_CONTEXT,
                                   0.85, evidence, portal)
            evidence.append(
                f"nav_ms={nav_ms}ms + {len(layers_tried)} layer(s) tried on portal={portal!r} — "
                f"likely IP block or immediate rejection."
            )
            return self._build(FailureCause.IP_BLOCK, RetryMechanism.SCRAPERAPI,
                               0.75, evidence, portal)

        # ── 3. Bot detection (ScrapeBotDetectedError fired in generic_scraper) ─
        if error_type == ScrapeFailureReason.BOT_DETECTED:
            if self._hit(error_msg, _CAPTCHA_SIGNALS):
                evidence.append(f"BOT_DETECTED + captcha signal — {error_msg!r:.120}")
                return self._build(FailureCause.CAPTCHA, RetryMechanism.SCRAPERAPI,
                                   0.95, evidence, portal)
            if self._hit(error_msg, _IP_BLOCK_SIGNALS):
                evidence.append(f"BOT_DETECTED + ip_block signal — {error_msg!r:.120}")
                return self._build(FailureCause.IP_BLOCK, RetryMechanism.SCRAPERAPI,
                                   0.90, evidence, portal)
            if self._hit(error_msg, _FINGERPRINT_SIGNALS):
                evidence.append(f"BOT_DETECTED + fingerprint signal — {error_msg!r:.120}")
                return self._build(FailureCause.FINGERPRINT, RetryMechanism.FIREFOX,
                                   0.85, evidence, portal)
            if self._hit(error_msg, _RATE_LIMIT_SIGNALS):
                evidence.append(f"BOT_DETECTED + rate_limit signal — {error_msg!r:.120}")
                return self._build(FailureCause.RATE_LIMITED, RetryMechanism.WAIT_RETRY,
                                   0.90, evidence, portal)
            # Unclassified bot detection — ScraperAPI is the safest escalation
            evidence.append(f"BOT_DETECTED — no sub-signal matched — {error_msg!r:.120}")
            return self._build(FailureCause.CAPTCHA, RetryMechanism.SCRAPERAPI,
                               0.65, evidence, portal)

        # ── 4. All extraction layers failed on a page that loaded normally ────
        if error_type == ScrapeFailureReason.ALL_LAYERS_FAILED:
            evidence.append(
                f"ALL_LAYERS_FAILED — "
                f"nav_ms={nav_ms} "
                f"layers_tried={layers_tried} "
                f"layers_failed={layers_failed}"
            )

            # If heuristic layer failed, there was no ₹ symbol anywhere on
            # the page — this is a bot-check / CAPTCHA page, not a real
            # product page with stale selectors.
            if "heuristic" in layers_failed:
                evidence.append(
                    f"heuristic layer failed — no ₹ symbol found anywhere on page. "
                    f"Page is almost certainly a bot-check/CAPTCHA page, not a "
                    f"real product page. Railway datacenter IP likely blocked."
                )
                return self._build(FailureCause.CAPTCHA, RetryMechanism.SCRAPERAPI,
                                   0.85, evidence, portal)

            # selector layer failed but heuristic passed → CSS class rotation
            # (₹ was on the page, just the CSS selectors couldn't find it)
            if "selector" in layers_failed:
                evidence.append(
                    f"selector layer in layers_failed (heuristic passed) — "
                    f"CSS classes likely rotated. Update portals.yaml price_selectors."
                )
                return self._build(FailureCause.CSS_STALE, RetryMechanism.SCRAPERAPI,
                                   0.80, evidence, portal)

            # Neither heuristic nor selector failed — structural layers missed
            evidence.append(
                f"selector/heuristic not in layers_failed — structural layers "
                f"(json_ld / semantic) failed. Possible JS hydration issue."
            )
            return self._build(FailureCause.HTML_STRUCTURE, RetryMechanism.NEW_CONTEXT,
                               0.75, evidence, portal)

        # ── 5. Freetext scan — untyped / unexpected errors ────────────────────
        for signals, cause, mechanism, conf in [
            (_WAF_SIGNALS,         FailureCause.WAF_CHALLENGE, RetryMechanism.NEW_CONTEXT, 0.80),
            (_CAPTCHA_SIGNALS,     FailureCause.CAPTCHA,       RetryMechanism.SCRAPERAPI,  0.80),
            (_RATE_LIMIT_SIGNALS,  FailureCause.RATE_LIMITED,  RetryMechanism.WAIT_RETRY,  0.80),
            (_IP_BLOCK_SIGNALS,    FailureCause.IP_BLOCK,      RetryMechanism.SCRAPERAPI,  0.75),
            (_FINGERPRINT_SIGNALS, FailureCause.FINGERPRINT,   RetryMechanism.FIREFOX,     0.70),
        ]:
            hit = self._hit(error_msg, signals)
            if hit:
                evidence.append(f"freetext match={hit!r} in error_message={error_msg!r:.120}")
                return self._build(cause, mechanism, conf, evidence, portal)

        # ── 6. Unknown ────────────────────────────────────────────────────────
        evidence.append(
            f"no signal matched — "
            f"error_type={error_type} nav_ms={nav_ms} "
            f"error_message={error_msg!r:.200}"
        )
        return self._build(FailureCause.UNKNOWN, RetryMechanism.NEW_CONTEXT,
                           0.30, evidence, portal)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _hit(self, text: str, signals: list[str]) -> Optional[str]:
        """Return first matching signal or None."""
        for s in signals:
            if s in text:
                return s
        return None

    def _build(
        self,
        cause: FailureCause,
        mechanism: RetryMechanism,
        confidence: float,
        evidence: list[str],
        portal: str,
    ) -> FailureDiagnosis:
        diag = FailureDiagnosis(
            cause=cause,
            mechanism=mechanism,
            confidence=confidence,
            evidence=evidence,
        )
        logger.warning(
            f"[FAILURE_DIAGNOSIS] "
            f"portal={portal} "
            f"cause={cause} "
            f"mechanism={mechanism} "
            f"confidence={confidence:.0%} "
            f"evidence={evidence!r:.400}"
        )
        return diag


# Module-level singleton
classifier = FailureClassifier()
