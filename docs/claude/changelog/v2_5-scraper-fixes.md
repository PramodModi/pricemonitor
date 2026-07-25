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

## [v2.5] — Cron Scraper Fixes & ScraperAPI Integration — July 2026

This phase resolves all blockers that prevented the GitHub Actions cron scraper
from running successfully. By the end of this phase, `scraped=17, failed=0` is
achieved for the first time — all 17 products across Amazon, Flipkart, and Myntra
scraped successfully in a single cron run.

The core bugs were: (1) the worker holding a `sync_playwright()` instance while
`ScraperEngine` tried to open its own, causing a crash on every job; (2) the
`_attempt_scraperapi()` and `_attempt_cached_page()` paths loading HTML via
`set_content()` then immediately discarding it by calling `page.goto()` inside
`GenericScraper.scrape()`; and (3) several `ScrapeFailureReason.UNKNOWN` references
to an enum value that never existed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `scraper_worker.py` | `run()` branched into `_run_v2()` / `_run_v1()` — v2 path holds no Playwright instance |
| `scraper_worker.py` | `_write_diagnostic()` `error_type.value` crash fixed |
| `engine.py` | `ScrapeFailureReason.UNKNOWN` replaced throughout (5 occurrences) |
| `engine.py` | `_attempt_scraperapi()` adds `premium=true` for Myntra |
| `engine.py` | Both pre-loaded HTML paths now pass `skip_navigation=True` |
| `generic_scraper.py` | `scrape()` gains `skip_navigation` parameter — skips `page.goto()` when HTML already loaded |
| `base.py` | Wrong import path in `_try_affiliate_api()` fixed |

---

### Fixes

#### FIX-001 — Playwright Double-Init Crash in GitHub Actions Cron
- **Affects:** `app/workers/scraper_worker.py`
- **Symptom:** Every scrape job failed immediately with:
  ```
  It looks like you are using Playwright Sync API inside the asyncio loop.
  Please use the Async API instead.
  ```
  `scraped=0, failed=0` — run manager saw zero results.
- **Root cause:** `ScraperWorker.run()` called `with sync_playwright() as pw:` to
  start Playwright, then `_process_job_v2()` opened `ScraperEngine()` which called
  `sync_playwright().start()` again inside the same thread. Two `sync_playwright()`
  calls in the same thread is not permitted.
- **Why not caught in preview:** The FastAPI preview route calls `ScraperEngine()`
  directly — it never goes through `ScraperWorker`. The double-init only occurs in
  the cron path via `WorkerManager → ScraperWorker`.
- **Why `ScraperEngine` cannot accept an external `pw`:** `scraper_v2` is designed
  to be fully self-contained and decoupled — future extraction as a standalone
  FastAPI service requires `ScraperEngine` to own its own Playwright lifecycle.
  Passing `pw` in from outside would violate this contract.
- **Fix:** `run()` now branches on `settings.use_scraper_v2`:
  - `_run_v2()` — `ScraperEngine` owns Playwright entirely. Worker holds no
    Playwright instance of its own. Calls `self._loop()` directly.
  - `_run_v1()` — Worker owns Playwright and a long-lived Chromium browser.
    Preserved intact for rollback (`USE_SCRAPER_V2=false`).
- **Files:** `app/workers/scraper_worker.py`

---

#### FIX-002 — `error_type.value` Crash in `_write_diagnostic()`
- **Affects:** `app/workers/scraper_worker.py`
- **Symptom:** Every job logged:
  ```
  Failed to write scrape diagnostic — error='str' object has no attribute 'value'
  ```
  No `scrape_diagnostics` rows written for any cron job.
- **Root cause:** `ScrapeFailureReason` is a plain class with string constants
  (not a Python `Enum`). `response.error_type` is already a plain string
  (`"timeout"`, `"blocked"`, `"failed"`). `_write_diagnostic()` called `.value`
  on it unconditionally, treating it as an enum.
- **Fix:** Changed to `hasattr` guard — same pattern already applied in `products.py`
  (v2.4 FIX-007):
  ```python
  error_type=(
      response.error_type.value
      if hasattr(response.error_type, "value")
      else response.error_type
  ),
  ```
- **Files:** `app/workers/scraper_worker.py`

---

#### FIX-003 — `ScrapeFailureReason.UNKNOWN` AttributeError
- **Affects:** `app/scraper_v2/engine.py`
- **Symptom:** ScraperAPI HTTP 500 response triggered:
  ```
  AttributeError: type object 'ScrapeFailureReason' has no attribute 'UNKNOWN'
  ```
  Crashed attempt 5 for Amazon products — all 5 attempts exhausted with an
  unhandled exception on the final attempt.
- **Root cause:** `ScrapeFailureReason` never defined an `UNKNOWN` constant.
  It was referenced in 5 places inside `engine.py` as if it were a valid value.
- **Fix:** All 5 occurrences replaced with semantically appropriate values:

  | Location | Was | Now | Rationale |
  |---|---|---|---|
  | Portal config not found | `UNKNOWN` | `ALL_LAYERS_FAILED` | No config = extraction cannot proceed |
  | All attempts exhausted fallback | `UNKNOWN` | `ALL_LAYERS_FAILED` | Cascade ran out of options |
  | ScraperAPI key not configured | `UNKNOWN` | `ALL_LAYERS_FAILED` | No key = extraction cannot proceed |
  | ScraperAPI network error | `UNKNOWN` | `TIMEOUT` | Network failure is semantically a timeout |
  | ScraperAPI HTTP non-200 | `UNKNOWN` | `BOT_DETECTED` | HTTP 500/403 from ScraperAPI = portal blocked |

- **Files:** `app/scraper_v2/engine.py`

---

#### FIX-004 — ScraperAPI HTML Discarded Before Extraction
- **Affects:** `app/scraper_v2/engine.py`, `app/scraper_v2/scrapers/generic_scraper.py`
- **Symptom:** ScraperAPI returned real product HTML (500KB–3MB, HTTP 200) but
  extraction still failed with `heuristic layer failed — no ₹ symbol`. Immediately
  after the `[SCRAPERAPI] response` log, the next line showed a fresh `[NAV]` with
  `nav_ms=150–370ms` and `raw_html length=481` — a bot-block page.
- **Root cause:** `_attempt_scraperapi()` loaded ScraperAPI HTML via
  `page.set_content(resp.text)` then called `self._scraper.scrape(page, url, ...)`.
  `GenericScraper.scrape()` always begins with `page.goto(url)` — navigating the
  page to the live product URL, which returns a bot-block page on GitHub Actions IPs,
  completely overwriting the ScraperAPI HTML before any extraction ran.
  The same bug existed in `_attempt_cached_page()` — the cached page HTML was
  navigated away from before extraction.
- **Fix — `generic_scraper.py`:** Added `skip_navigation: bool = False` parameter
  to `GenericScraper.scrape()`. When `True`, the entire `page.goto()` block is
  skipped. An `else` branch logs `skip_navigation=True (HTML pre-loaded by caller)`.
- **Fix — `engine.py`:** Both pre-loaded HTML callers now pass `skip_navigation=True`:
  - `_attempt_scraperapi()`: `skip_navigation=True`
  - `_attempt_cached_page()`: `skip_navigation=True`
  Browser attempt callers (`_attempt_browser()`) do not pass the parameter —
  they default to `False` and navigate normally.
- **Result:** After fix, ScraperAPI HTML is extracted correctly:
  - Myntra: JSON-LD hit — `price=598`, `price=17495` ✅
  - Flipkart: JSON-LD hit — `price=82900` ✅
  - Amazon: selector hit — `price=24662`, `price=30461` ✅
- **Files:** `app/scraper_v2/engine.py`, `app/scraper_v2/scrapers/generic_scraper.py`

---

#### FIX-005 — Wrong Import Path in `_try_affiliate_api()`
- **Affects:** `app/scraper_v2/scrapers/base.py`
- **Symptom:** When the `affiliate_api` layer was reached:
  ```
  [LAYER] portal=amazon layer=affiliate_api status=error error=No module named 'scraper_v2'
  ```
- **Root cause:** The import inside `_try_affiliate_api()` used:
  ```python
  from scraper_v2.core.config import settings   # wrong
  ```
  This works on a local machine where `scraper_v2` is on `sys.path` but fails on
  GitHub Actions where the correct path is `app.scraper_v2`.
- **Why not caught earlier:** The import is inside the function body, not at module
  level. Python only executes it when the function is called AND reaches the import
  line. `_try_affiliate_api()` always returned `None` at the credentials check
  (no `amazon_paapi_key` configured) before reaching the import — until this run
  when the code path changed.
- **Fix:**
  ```python
  from app.scraper_v2.core.config import settings   # correct
  ```
- **Files:** `app/scraper_v2/scrapers/base.py`

---

#### FIX-006 — ScraperAPI Key Missing on Railway for Preview Route
- **Affects:** Railway environment variables
- **Symptom:** Streamlit preview for Amazon returned 502:
  ```
  give_up — no ScraperAPI key configured, cannot proceed further — portal=amazon
  ```
- **Root cause:** `SCRAPER_API_KEY` was added to GitHub Actions secrets (for the
  cron path) but not to Railway environment variables (for the preview path).
  `ScraperEngine._has_scraperapi()` returned `False` — the CAPTCHA fast-path
  fell through to the standard cascade which exhausted all browser attempts before
  giving up.
- **Fix:** Added `SCRAPER_API_KEY` to Railway Variables. Railway redeployed
  automatically. Preview now succeeds for Amazon via ScraperAPI attempt 2.
- **Files:** Railway dashboard — no code change

---

#### FIX-007 — ScraperAPI `premium=true` for Myntra
- **Affects:** `app/scraper_v2/engine.py`
- **Change:** Added `premium=true` to ScraperAPI request params for Myntra.
  Myntra is a React SPA — standard ScraperAPI rendering does not always execute
  the full React lifecycle. Premium mode uses ScraperAPI's residential proxy pool
  with heavier JS rendering.
- **Note:** Premium costs 10 credits per request vs 1 for standard. Only enabled
  for Myntra (`config.name == "myntra"`).
- **Files:** `app/scraper_v2/engine.py`

---

### Deviations from Design

#### DEV-001 — Worker Does Not Hold Playwright in v2 Mode
- **Affects:** `app/workers/scraper_worker.py`
- **Original (v2.4):** `ScraperWorker.run()` always opened `sync_playwright()`
  and held a long-lived Chromium browser — inherited from v1 design.
- **Actual:** In v2 mode, the worker holds no Playwright instance. `ScraperEngine`
  opens and closes Playwright per job. `_run_v2()` simply calls `self._loop()`
  directly with no browser setup.
- **Reason:** `ScraperEngine` must own its own Playwright lifecycle for decoupling
  (v2.4 DEV-001). Two `sync_playwright()` instances in the same thread is not
  permitted. The worker cannot hold Playwright if the engine also holds it.
- **Trade-off:** Playwright opens and closes on every job (one `ScraperEngine` per
  job). Acceptable overhead for current volume (17 products, 6 runs/day).

#### DEV-002 — `skip_navigation` Parameter Added to `GenericScraper.scrape()`
- **Affects:** `app/scraper_v2/scrapers/generic_scraper.py`
- **Original:** `scrape()` always called `page.goto(url)` as its first action.
- **Actual:** `scrape()` accepts `skip_navigation: bool = False`. When `True`,
  the navigation block is skipped entirely — the caller is responsible for having
  loaded the page content before calling `scrape()`.
- **Reason:** Both the ScraperAPI path and the cached page path pre-load HTML
  before calling `scrape()`. Calling `page.goto()` inside `scrape()` would
  navigate away from the pre-loaded HTML to the live (bot-blocked) URL.
- **Callers that pass `skip_navigation=True`:** `_attempt_scraperapi()`,
  `_attempt_cached_page()`.
- **Callers that use default (`False`):** `_attempt_browser()` (attempts 1, 2, 3).

---

### Configuration Added

| Variable | Default | Used by | Description |
|---|---|---|---|
| `SCRAPER_API_KEY` | `""` | `ScraperEngine._attempt_scraperapi()` | Must now be set in **both** Railway Variables (preview path) and GitHub Actions secrets (cron path). Free tier: 1,000 credits/month. Premium requests (Myntra) cost 10 credits each. |

---

### Portal Status After v2.5 (GitHub Actions — July 2026)

| Portal | Result | Mechanism | Notes |
|---|---|---|---|
| Amazon (canonical `amazon.in/dp/`) | ✅ | ScraperAPI attempt 2 | GitHub Actions IPs blocked at AWS WAF — ScraperAPI residential proxy bypasses |
| Amazon (`amzn.in` short URLs) | ✅ | ScraperAPI or attempt 1 | Short URL redirects to canonical before scrape — works normally |
| Flipkart (direct product URLs) | ✅ | ScraperAPI attempt 2 | Chromium blocked on GitHub Actions; ScraperAPI succeeds |
| Flipkart (search result URLs) | ✅ | ScraperAPI attempt 2 | Extra search params cause Chromium to get bot page; ScraperAPI unaffected |
| Myntra | ✅ | ScraperAPI attempt 2 | IP blocked at network level; ScraperAPI premium mode succeeds |

**Final cron result: `scraped=17, failed=0, drops=0`** — all products scraped successfully.

---

### Files Modified

| File | Changes |
|---|---|
| `app/workers/scraper_worker.py` | `run()` branched into `_run_v2()` / `_run_v1()`; `_write_diagnostic()` `error_type.value` crash fixed |
| `app/scraper_v2/engine.py` | `ScrapeFailureReason.UNKNOWN` replaced (5 occurrences); `skip_navigation=True` added to `_attempt_scraperapi()` and `_attempt_cached_page()` calls; `premium=true` added to ScraperAPI params for Myntra; ScraperAPI timeout raised to 120s |
| `app/scraper_v2/scrapers/generic_scraper.py` | `skip_navigation: bool = False` parameter added to `scrape()`; navigation block wrapped in `if not skip_navigation:` |
| `app/scraper_v2/scrapers/base.py` | Wrong import `from scraper_v2.core.config` → `from app.scraper_v2.core.config` in `_try_affiliate_api()` |

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | `ScraperEngine` opens a new Playwright instance per job — long-lived instance would be more efficient. Acceptable for current volume. | `app/scraper_v2/engine.py` | Phase 3 performance tuning |
| DEF-002 | Amazon PA-API (Layer 6 `affiliate_api`) still a stub — credentials not configured | `app/scraper_v2/scrapers/base.py` | When PA-API access received |
| DEF-003 | Adaptive layer ordering (LayerStatsCache) still using default order — insufficient production diagnostic data | `app/scraper_v2/scrapers/layer_selector.py` | Automatic after 2+ months data |
| DEF-004 | Progressive retry delay + full 5-attempt cascade can take ~2 minutes on Railway. Preview will 504 on Railway's 30s request timeout if ScraperAPI is slow. | `app/scraper_v2/engine.py` | Add per-cascade wall-clock timeout guard |
| DEF-005 | Flipkart products subscribed via search result URLs carry extra params (`fm=`, `ssid=`, `otracker1=`) in `products.url`. These cause Chromium to get bot pages. ScraperAPI bypasses this but wastes credits. URL should be cleaned to canonical `/p/{id}` form at subscription time. | `app/services/url_validator.py` | Phase 3 |
| DEF-006 | ScraperAPI free tier is 1,000 credits/month. With 17 products × all blocked portals × 6 runs/day, credits may exhaust within days. Monitor usage on ScraperAPI dashboard. | ScraperAPI dashboard | Monitor |
| DEF-007 | `triggered_by` for preview scrapes is always `null` — email not available at preview step | `app/fastapi/api/v1/products.py` | Backfill on confirm step |

---

### Next Phase

| Item | Priority | Description |
|---|---|---|
| Monitor ScraperAPI credits | **Immediate** | Free tier (1,000/month) may exhaust quickly. Monitor dashboard and upgrade plan if needed. |
| Clean Flipkart search URLs | High | Strip search params from Flipkart URLs at subscription time — reduces ScraperAPI credit usage and improves reliability |
| Wall-clock timeout guard | High | Add a max cascade duration (~25s) so preview never 504s on Railway's 30s limit |
| LLM extraction layer | Medium | Layer 6b via Groq free API — handles CSS drift cases where ScraperAPI HTML loads but selectors miss |
| Price history chart | Low | Streamlit UI — price trend chart on product detail page |
| Redis PreviewCache | Low | Replace in-memory cache with Redis for multi-instance deployments |
| Auth | Low | User login / session management |

---

*Archive this file to `docs/changelog/v2.5-scraper-fixes.md` when Phase 3 begins.*
