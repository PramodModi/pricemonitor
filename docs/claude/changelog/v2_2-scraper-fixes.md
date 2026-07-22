# PriceMonitor — Changelog

All notable changes to design documents and implementation are recorded here.
When a phase is complete, this file is archived to `changelog/` and a new one started.

Format:
- **FEAT** — new feature not in original docs
- **DEV** — deviation from original design
- **FIX** — bug fix during implementation
- **CFG** — new configuration added
- **DEF** — known issue deferred to future phase
- **OPS** — operational/deployment note

---

## [v2.2] — Scraper Fixes — July 2026

This phase fixes Myntra scraping on Railway (was failing silently since v2.1
cutover) and adds AWS WAF challenge handling for Amazon on Railway datacenter
IPs. A diagnostic debug endpoint is added for future scraper debugging.

---

### Summary of Changes

| Area | Change |
|---|---|
| `products.py` | Myntra uses Firefox context without Chrome UA override |
| `scraper_worker.py` | Myntra uses Firefox context without Chrome UA override; Amazon/Flipkart context enriched with `timezone_id` and `Sec-Fetch-*` headers |
| `generic_scraper.py` | AWS WAF challenge detection and wait added for Amazon |
| `base.py` | `_dig_jsonld_product` moved inside inner try/except to handle multi-block JSON-LD; `affiliate_api` import path fixed |
| `debug_scrape.py` | New internal diagnostic endpoint `POST /v1/internal/debug-scrape` |
| `main.py` | `debug_scrape` router registered |

---

### Fixes

#### FIX-001 — Myntra Chrome UA on Firefox Browser (Preview Route)
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** Myntra preview returned 502 on Railway — page loaded in ~200ms with 481 bytes (bot block)
- **Root cause:** `browser.new_context()` was passing `user_agent="Chrome/124.0.0.0"` to a Firefox browser instance. Myntra fingerprints the TLS profile against the UA string — a Firefox TLS handshake with a Chrome UA is a mismatch that triggers bot detection.
- **Fix:** Myntra context (`platform == "myntra"`) no longer overrides `user_agent`. Playwright's real Firefox UA is used. Amazon/Flipkart (`else` branch) keep the Chrome UA unchanged.
- **Confirmed:** Myntra preview working on Railway post-fix.

#### FIX-002 — Myntra Chrome UA on Firefox Browser (Scheduled Scraper)
- **Affects:** `app/workers/scraper_worker.py`
- **Symptom:** Same as FIX-001 but in the scheduled scraper path
- **Root cause:** Same — single `new_context()` call applied Chrome UA regardless of browser engine
- **Fix:** Same as FIX-001 — `platform == "myntra"` branch uses real Firefox UA; `else` branch (Amazon/Flipkart) unchanged.

#### FIX-003 — JSON-LD Multi-Block Parsing Aborts on First Block Exception
- **Affects:** `app/scraper_v2/scrapers/base.py` — `_try_structured_data()`
- **Symptom:** Myntra JSON-LD extraction failed silently — Myntra serves three JSON-LD blocks (Organization → Product → BreadcrumbList) and extraction returned None
- **Root cause:** `_dig_jsonld_product()` and subsequent code were **outside** the inner `try/except (json.JSONDecodeError, Exception)` block. Any exception on block 0 (Organization) caused the outer `except Exception: pass` to catch it and return None — without ever processing block 1 (Product).
- **Fix:** `_dig_jsonld_product()` and all post-parse logic moved inside the inner try/except. Each block is now independently isolated — an exception on one block `continue`s to the next.
- **Impact:** Amazon and Flipkart unaffected — Amazon skips JSON-LD entirely (`skip_layers`); Flipkart's Product block is the first block found and parses cleanly.

#### FIX-004 — affiliate_api Layer Wrong Import Path
- **Affects:** `app/scraper_v2/scrapers/base.py` — `_try_affiliate_api()`
- **Symptom:** `[LAYER] portal=amazon layer=affiliate_api status=error error=No module named 'scraper_v2'`
- **Root cause:** `from scraper_v2.core.config import settings` — missing `app.` prefix
- **Fix:** `from app.scraper_v2.core.config import settings`
- **Impact:** Stub returns None silently as intended. Layer error log eliminated.

#### FIX-005 — Amazon AWS WAF JS Challenge Not Waited For
- **Affects:** `app/scraper_v2/scrapers/generic_scraper.py`
- **Symptom:** Amazon preview returned 502 on Railway — `nav_ms=240`, all layers failed, `raw_html length=3506` (CAPTCHA/WAF page)
- **Root cause:** Railway datacenter IPs trigger an AWS WAF JS challenge before serving the real product page. The challenge page fires `domcontentloaded` immediately (~240ms). `page.goto()` returned on the challenge page. The WAF JS then runs `window.location.reload()` — a new navigation that `page.goto()` does not wait for. Extraction ran on the 3506-byte challenge page, found no price, failed.
- **Fix:** After `page.goto()` returns for Amazon, `page.content()` is checked for `"awswaf"` or `"AwsWafIntegration"`. If the WAF challenge is detected, `page.wait_for_load_state("load")` waits for the JS-driven reload to complete, followed by a 3000ms settle wait. Extraction then runs on the real product page.
- **Isolation:** Entire block is inside `if config.name == "amazon":` — Flipkart and Myntra are unaffected.
- **Local behaviour:** No WAF challenge on home IPs — the `if "awswaf" in page_content` check is false, block is skipped, scrape proceeds as before.
- **Confirmed:** Amazon preview working on Railway post-fix.

---

### Features

#### FEAT-001 — Debug Scrape Endpoint
- **Affects:** `app/fastapi/api/v1/debug_scrape.py` (new file), `app/fastapi/main.py`
- **Change:** New internal endpoint `POST /v1/internal/debug-scrape` for diagnosing scraper failures on Railway without a code deploy. Accepts a URL plus optional browser, context options, wait strategy, and post-nav wait. Returns HTTP status, final URL after redirects, response headers, page title, HTML length, first N chars of HTML, last 2000 chars of HTML, and navigation timing. Protected by Bearer token (same `SECRET_KEY` as other internal endpoints).
- **Use case:** Confirmed Myntra loads successfully on Railway (HTTP 200, 450KB HTML, JSON-LD present) — leading to discovery of the Chrome UA mismatch (FIX-001). Confirmed Amazon AWS WAF challenge page (FIX-005). Confirmed Flipkart reCAPTCHA during IP block episodes.
- **Token check:** Inlined directly in the file — no cross-package import dependency.

---

### Deviations from Design

#### DEV-001 — Browser Context Split by Platform, Not Browser Engine
- **Affects:** `app/fastapi/api/v1/products.py`, `app/workers/scraper_worker.py`
- **Original:** Single `browser.new_context()` call for all portals in the v2 path
- **Actual:** `if platform == "myntra"` branch uses Firefox-appropriate context (no UA override, Firefox-compatible headers); `else` branch (Amazon, Flipkart) uses Chrome UA + full Sec-Fetch headers + timezone
- **Reason:** UA mismatch between Firefox TLS profile and Chrome UA string triggers Myntra bot detection (FIX-001, FIX-002)

#### DEV-002 — Amazon WAF Handling in generic_scraper, Not portals.yaml
- **Original intent:** Portal-specific behaviour driven by `portals.yaml` config
- **Actual:** AWS WAF challenge detection and wait implemented in `generic_scraper.py` as Python logic, not a YAML config field
- **Reason:** The WAF challenge is a dynamic condition (present on Railway, absent locally) that requires reading `page.content()` and calling `wait_for_load_state()` — not expressible as a static YAML timeout value. `goto_wait_until: networkidle` was considered but risks timeout on Amazon pages with continuous background XHR.

---

### Root Cause Analysis — IP Block Episodes

During debugging, Railway's outbound IP was temporarily blocked by Amazon and Flipkart due to high request volume (multiple preview attempts + debug endpoint calls in short succession). Symptoms:

| Portal | Block symptom | Page size | Nav time |
|---|---|---|---|
| Amazon | AWS WAF CAPTCHA | 3,506 bytes | ~220ms |
| Flipkart | reCAPTCHA 403 | 1,455 bytes | ~800ms |
| Myntra | Silent block | 481 bytes | ~200ms |

**Resolution:** Railway redeployment assigns a new outbound IP — clean slate with no request history. Normal scheduled scraper operation (one request per product every 4 hours) is spaced out enough to avoid re-triggering blocks.

**Long-term fix:** `ScraperAPIFallback` with residential proxies (Zyte/ScrapeOps) — deferred to Phase 3.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Railway datacenter IPs periodically blocked by Amazon/Flipkart/Myntra under high request volume — residential proxy fallback not implemented | `app/scraper_v2/scrapers/base.py` | Phase 3 (ScraperAPIFallback) |
| DEF-002 | `[JSON-LD]` debug logging still in `base.py` — adds log noise in production | `app/scraper_v2/scrapers/base.py` | Remove when all portals confirmed stable |
| DEF-003 | `debug_scrape.py` endpoint does not apply `Stealth()` — results differ from actual scraper behaviour under bot detection | `app/fastapi/api/v1/debug_scrape.py` | Low priority — endpoint is a diagnostic tool |

---

### Files Modified

| File | Change |
|---|---|
| `app/fastapi/api/v1/products.py` | Myntra/non-Myntra context split — FIX-001, DEV-001 |
| `app/workers/scraper_worker.py` | Myntra/non-Myntra context split — FIX-002, DEV-001 |
| `app/scraper_v2/scrapers/generic_scraper.py` | Amazon WAF challenge detection and wait — FIX-005, DEV-002 |
| `app/scraper_v2/scrapers/base.py` | JSON-LD multi-block fix — FIX-003; import fix — FIX-004; debug logging added |

### Files Added

| File | Purpose |
|---|---|
| `app/fastapi/api/v1/debug_scrape.py` | Internal diagnostic endpoint for Railway scraper debugging |

---

*Archive this file to `docs/changelog/v2.2-scraper-fixes.md` when Phase 3 begins.*
