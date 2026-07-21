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

## [v2.1] — Phase 2 Cutover — July 2026

This phase wires `scraper_v2` into production. The old `app/scrapers/` layer is
preserved untouched and can be restored via a single environment variable toggle.
Myntra is added as a supported portal. The `scrape_diagnostics` table is live.

---

### Summary of Changes

| Area | Change |
|---|---|
| `scraper_worker.py` | Branches on `USE_SCRAPER_V2` flag — routes to `GenericScraper` (v2) or old scrapers (v1) |
| `products.py` (preview route) | Same `USE_SCRAPER_V2` branch — preview now uses `GenericScraper` too |
| `url_validator.py` | Myntra added to supported platforms |
| `preview_card.py` | Myntra platform badge added |
| `product_card.py` | Myntra platform badge added |
| `portals.yaml` | `post_nav_wait_ms` field added for Flipkart and Myntra |
| `portal_config.py` | `post_nav_wait_ms` field added to `PortalConfig` dataclass |
| `generic_scraper.py` | `post_nav_wait_ms` wait applied after navigation |
| `config.py` | `use_scraper_v2: bool = True` added to `Settings` |
| `requirements.txt` | `pyyaml` added (required by `scraper_v2` for `portals.yaml` loading) |
| Alembic | Migration `<hash>_create_scrape_diagnostics.py` run against Supabase |
| Railway | Switched from Railpack to Docker build — `Dockerfile` added to `code/` |
| GitHub Actions | `playwright install firefox` added to `scraper.yml` |

---

### Features

#### FEAT-001 — scraper_v2 in Production with One-Flag Rollback
- **Affects:** `app/workers/scraper_worker.py`, `app/fastapi/api/v1/products.py`
- **Change:** Both the scheduled worker path and the preview route now use
  `GenericScraper` from `scraper_v2` when `USE_SCRAPER_V2=true`. Setting
  `USE_SCRAPER_V2=false` in Railway environment variables instantly reverts both
  paths to the original `AmazonScraper` / `FlipkartScraper` without a code deploy.
- **Implementation:** `settings.use_scraper_v2` flag in `app/core/config.py`

#### FEAT-002 — Myntra Added as Supported Portal
- **Affects:** `app/services/url_validator.py`, `streamlit_app/components/`
- **Change:** Myntra URLs now accepted, validated, and scraped. Platform badge
  renders correctly in preview and product cards.
- **URL pattern:** `myntra.com/{slug}/{product_id}/buy`
- **Browser:** Firefox (Chromium blocked by Myntra TLS fingerprinting)
- **Extraction:** JSON-LD Layer 2 — price, name, brand, image, availability confirmed

#### FEAT-003 — scrape_diagnostics Table Live
- **Affects:** `app/scraper_v2/diagnostics/`
- **Change:** Alembic migration run. Every scrape attempt now writes a row to
  `scrape_diagnostics` recording portal, worker_id, layers_attempted, layers_failed,
  extraction_method, nav_ms, extraction_ms, total_ms, success, error_type.
- **Migration:** `alembic/versions/<hash>_create_scrape_diagnostics.py`
- **Used by:** `LayerStatsCache` — adaptive layer ordering activates after 2+ months data

#### FEAT-004 — post_nav_wait_ms Per-Portal Wait
- **Affects:** `portals.yaml`, `portal_config.py`, `generic_scraper.py`
- **Change:** New `post_nav_wait_ms` field in `portals.yaml` adds a configurable
  wait after `page.goto()` before extraction begins. Applied to Flipkart (2000ms)
  to allow React hydration — without this wait JSON-LD was not present in the DOM
  on Railway's servers.
- **Configured:**
  - `flipkart: post_nav_wait_ms: 2000`
  - `myntra: post_nav_wait_ms: 2000`
- **Root cause:** Old `FlipkartScraper` had `page.wait_for_timeout(2000)` hardcoded
  after navigation. `GenericScraper` had no equivalent wait — this caused Flipkart
  scraping to fail on Railway (React not hydrated) even though it worked locally.

#### FEAT-005 — Firefox Worker Support in Production
- **Affects:** `app/workers/scraper_worker.py`
- **Change:** In v2 mode, `_process_job_v2()` reads `portal_config.browser` and
  opens a short-lived Firefox browser for portals that require it (Myntra).
  Chromium jobs continue using the persistent `self._browser`. Firefox browser
  is opened and closed per job to avoid memory leaks.

---

### Fixes

#### FIX-001 — Flipkart Scraping Regression on Railway
- **Symptom:** Flipkart scraping worked with old `FlipkartScraper` on Railway
  but failed with `GenericScraper` — all layers failed, nav_ms was correct (~800ms)
- **Root cause:** `GenericScraper` had no post-navigation wait. React hydration
  (which renders JSON-LD into the DOM) takes ~2s. Without the wait, all extraction
  layers ran on a partially hydrated page.
- **Fix:** `post_nav_wait_ms: 2000` in `portals.yaml` for Flipkart — see FEAT-004

#### FIX-002 — Platform Badge Shows Wrong Platform
- **Symptom:** Myntra products showed Flipkart badge in preview and product cards
- **Root cause:** `platform_label` / `platform_icon` used a binary `if/else`
  (`"amazon"` → Amazon India, anything else → Flipkart)
- **Fix:** Replaced with `PLATFORM_DISPLAY` dict in both `preview_card.py` and
  `product_card.py`. Unknown future portals fall back to `platform.title()`.

---

### Deviations from Design

#### DEV-001 — preview route calls GenericScraper directly, not via worker
- **Affects:** `app/fastapi/api/v1/products.py`
- **Original design intent:** Worker owns all scraping
- **Actual:** Preview route (`POST /v1/products/preview`) calls `GenericScraper`
  directly and synchronously — the HTTP request blocks until the scrape completes.
- **Reason:** Preview is synchronous by design (returns result immediately to user).
  The worker is async (queue-based, writes to DB). Routing preview through the
  worker would require a polling/callback mechanism that adds complexity for no benefit.
  This was true in v1 too — the deviation is the same, now using `GenericScraper`
  instead of `AmazonScraper`/`FlipkartScraper`.

#### DEV-002 — Dockerfile added for Railway instead of Railpack
- **Affects:** Railway deployment
- **Original:** Railpack auto-detected Python and built with pip
- **Actual:** `code/Dockerfile` uses `mcr.microsoft.com/playwright/python:v1.44.0-jammy`
  base image which includes all Playwright browsers and system dependencies pre-installed.
- **Reason:** Railpack's build/runtime separation did not persist browser binaries
  installed during build into the runtime container. Multiple approaches were
  attempted (custom build commands, `PLAYWRIGHT_BROWSERS_PATH`) before switching
  to Docker.

#### DEV-003 — playwright pinned to 1.44.0 in requirements.txt
- **Affects:** `requirements.txt`
- **Original:** `playwright` unpinned
- **Actual:** `playwright==1.44.0`
- **Reason:** Must match the version in the Docker base image
  (`mcr.microsoft.com/playwright/python:v1.44.0-jammy`). Unpinned pip install
  upgraded to 1.61.0 which looked for browser binaries at a different path than
  the image provided.

#### DEV-004 — Extra HTTP headers not sufficient to bypass Myntra IP block on Railway
- **Affects:** Myntra scraping on Railway
- **Attempted:** Added `Sec-Fetch-*`, `Accept-Language`, `Accept-Encoding`,
  `timezone_id`, `Upgrade-Insecure-Requests` headers to browser context — same
  headers used in `run_test.py` locally (where Myntra works).
- **Result:** No effect. Myntra returns a block response in ~200ms regardless of
  headers — confirming the block is at the IP/network layer, not the header layer.
- **Conclusion:** Myntra on Railway requires residential proxies (Phase 3).

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Myntra scraping fails on Railway — Myntra blocks Railway's data center IP range at network level. Works locally. Residential proxies required. | `app/scraper_v2/scrapers/generic_scraper.py` | Phase 3 (ScraperAPIFallback) |
| DEF-002 | ScraperAPIFallback not implemented — bot-detected scrapes (v2 path) are dropped without retry. In v1 path, `ScraperAPIFallback.scrape()` stub was called. | `app/scraper_v2/scrapers/base.py` | Phase 3 |
| DEF-003 | Adaptive layer ordering (LayerStatsCache) has no data yet — using default order for all portals. Requires 2+ months of production diagnostic data. | `app/scraper_v2/scrapers/layer_selector.py` | Automatic — no action needed |
| DEF-004 | Amazon PA-API (Layer 6) still a stub — pending API access approval | `app/scraper_v2/scrapers/base.py` | When PA-API access received |
| DEF-005 | `scrape_diagnostics` rows written by preview route have `product_id=None` — preview scrapes are not linked to a product until confirm step | `app/workers/scraper_worker.py` | Low priority |
| DEF-006 | GitHub Actions `scraper.yml` installs Firefox but Myntra fails on Railway anyway — `playwright install firefox` step is harmless but currently unused in production | `.github/workflows/scraper.yml` | Phase 3 |
| DEF-007 | Amazon extraction ~7–10s — human-simulation hook dominates (3–4s). Acceptable for async workers; worth tuning if Railway timeout pressure increases. | `app/scraper_v2/scrapers/hooks.py` | Phase 2 tuning |

---

### Configuration Added

New settings added to `app/core/config.py`:

| Setting | Default | Used by | Description |
|---|---|---|---|
| `use_scraper_v2` | `True` | `ScraperWorker`, preview route | Toggle between scraper_v2 and old scrapers. Set `USE_SCRAPER_V2=false` in env to rollback. |

New fields added to `portals.yaml` / `PortalConfig`:

| Field | Type | Default | Description |
|---|---|---|---|
| `post_nav_wait_ms` | `int` | `0` | Milliseconds to wait after `page.goto()` before extraction. Used for React-rendered portals (Flipkart, Myntra). |

---

### Portal Status on Railway (July 2026)

| Portal | Preview | Scheduled Scraper | Notes |
|---|---|---|---|
| Amazon | ✅ | ✅ | Working — JSON-LD skipped (absent), selector layer |
| Flipkart | ✅ | ✅ | Working after `post_nav_wait_ms: 2000` fix |
| Myntra | ❌ | ❌ | IP blocked by Myntra on Railway — works locally |

---

### Deployment Notes

| Item | Note |
|---|---|
| Railway build | Switched to Docker. `code/Dockerfile` uses `mcr.microsoft.com/playwright/python:v1.44.0-jammy` |
| Railway start command | `sh -c "uvicorn app.fastapi.main:app --host 0.0.0.0 --port ${PORT:-8080}"` — shell wrapper required for `$PORT` expansion with Docker |
| Railway env vars | `PLAYWRIGHT_BROWSERS_PATH` env var removed — no longer needed with Docker image |
| Railway build command | Cleared — Dockerfile handles all build steps |
| `pyyaml` | Added to `code/requirements.txt` — required by `scraper_v2` for `portals.yaml` |
| Alembic migration | `<hash>_create_scrape_diagnostics.py` run — `scrape_diagnostics` table live in Supabase |
| GitHub Actions | `playwright install firefox` + `playwright install-deps firefox` added to `scraper.yml` |
| Streamlit Cloud | Rebooted to pick up `preview_card.py` and `product_card.py` changes |

---

### Files Modified

| File | Change |
|---|---|
| `app/workers/scraper_worker.py` | Full rewrite — `USE_SCRAPER_V2` branch, v2 path with `GenericScraper`, v1 path preserved, `_write_diagnostic()` added |
| `app/fastapi/api/v1/products.py` | Preview route — `USE_SCRAPER_V2` branch, v2 path uses `GenericScraper` + Firefox support |
| `app/services/url_validator.py` | Myntra added to `SUPPORTED_DOMAINS`, removed from `_KNOWN_UNSUPPORTED_DOMAINS`, `_MYNTRA_PRODUCT_PATTERNS` added |
| `app/core/config.py` | `use_scraper_v2: bool = True` added to `Settings` |
| `app/scraper_v2/scrapers/portals.yaml` | `post_nav_wait_ms: 2000` added to `flipkart` and `myntra` |
| `app/scraper_v2/scrapers/portal_config.py` | `post_nav_wait_ms: int = 0` added to `PortalConfig` dataclass and `load_portal_configs()` |
| `app/scraper_v2/scrapers/generic_scraper.py` | `post_nav_wait_ms` wait added after navigation block |
| `streamlit_app/components/preview_card.py` | `PLATFORM_DISPLAY` dict replaces binary platform label logic |
| `streamlit_app/components/product_card.py` | Same as above |
| `requirements.txt` | `pyyaml` added, `playwright` pinned to `==1.44.0` |

### Files Added

| File | Purpose |
|---|---|
| `code/Dockerfile` | Docker build for Railway — Playwright base image with all browsers pre-installed |
| `alembic/versions/<hash>_create_scrape_diagnostics.py` | Creates `scrape_diagnostics` table with indexes |

---

### Next Phase — Phase 3

| Item | Description |
|---|---|
| ScraperAPIFallback | Implement Zyte/ScrapeOps residential proxy fallback for Myntra and bot-detected scrapes |
| Myntra on Railway | Blocked until ScraperAPIFallback is live |
| LLM extraction layer | Layer 6b via Groq free API — handles pages where all structural layers fail |
| Amazon PA-API | Layer 6 affiliate API — pending API access |
| Redis PreviewCache | Replace in-memory `PreviewCache` with Redis for multi-instance deployments |
| Price history chart | Streamlit UI — price trend chart on product detail page |
| Auth | User login / session management |

---

*Archive this file to `docs/changelog/v2.1-cutover.md` when Phase 3 begins.*
