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

## [v2.0] — Scraper Rewrite — July 2026

This phase replaces the original `app/scrapers/` layer (amazon.py, flipkart.py,
base.py, scraperapi_fallback.py) with a complete rewrite under `app/scraper_v2/`.
The existing scraper layer is untouched and remains in production during development.
`app/workers/scraper_worker.py` continues to use the old scrapers until the cutover
is explicitly triggered.

---

### New Module: `app/scraper_v2/`

#### Folder Structure

```
code/
└── app/
    ├── scrapers/                      ← EXISTING, untouched, still in production
    │   ├── amazon.py
    │   ├── flipkart.py
    │   ├── base.py
    │   └── scraperapi_fallback.py
    │
    └── scraper_v2/                    ← NEW — built and tested in this phase
        ├── __init__.py
        ├── run_test.py                ← CLI test tool (dev only)
        ├── core/
        │   ├── __init__.py
        │   ├── config.py              ← scraper_v2-specific settings
        │   ├── exceptions.py          ← ScrapeExtractionError, ScrapeFailureReason
        │   └── logging.py             ← logger factory
        ├── models/
        │   ├── __init__.py
        │   └── scrape_result.py       ← ScrapeRequest, ScrapeResponse
        ├── scrapers/
        │   ├── __init__.py
        │   ├── base.py                ← BaseScraper + 6 extraction layers
        │   ├── generic_scraper.py     ← single scraper for all portals
        │   ├── hooks.py               ← portal-specific page interactions
        │   ├── layer_selector.py      ← adaptive layer ordering
        │   ├── portal_config.py       ← PortalConfig dataclass + YAML loader
        │   ├── portals.yaml           ← all portal definitions
        │   └── registry.py            ← domain/platform → PortalConfig lookup
        ├── diagnostics/
        │   ├── __init__.py
        │   ├── models.py              ← ScrapeDiagnostic ORM model
        │   └── repository.py          ← insert, layer stats, purge
        └── tests/
            └── __init__.py
```

---

### Features

#### FEAT-001 — Portal-Agnostic Scraper Architecture
- **Replaces:** `app/scrapers/amazon.py`, `app/scrapers/flipkart.py`
- **Change:** Single `GenericScraper` class handles all portals. No portal-specific
  Python outside `hooks.py`. Adding a new portal requires only YAML — zero Python changes.
- **Implementation:** `app/scraper_v2/scrapers/generic_scraper.py`
- **Config:** `app/scraper_v2/scrapers/portals.yaml`

#### FEAT-002 — Six-Layer Price Extraction with Ordered Fallback
- **Change:** Price extraction tries layers in order, stopping at first success.
  Replaces the single-selector approach in the original scrapers.
- **Layers (default order):**

  | Layer | Method | Notes |
  |---|---|---|
  | 1 — meta_tags | `<meta property="product:price:amount">` | Most stable |
  | 2 — json_ld | `<script type="application/ld+json">` | SEO-driven, works on Flipkart + Myntra |
  | 3 — semantic | `[itemprop="price"]`, `[data-testid*="price"]` | Structural |
  | 4 — selector | Portal CSS from `portals.yaml` | Fast but degrades over time |
  | 5 — heuristic | ₹-regex over page body | Reliable last resort |
  | 6 — affiliate_api | Amazon PA-API stub | Pending API access |

- **Implementation:** `BaseScraper._extract_price_with_fallbacks()` — `app/scraper_v2/scrapers/base.py`

#### FEAT-003 — JSON-LD Full Product Cache
- **Change:** When Layer 2 (JSON-LD) extracts price, it also caches name, brand,
  image, rating, review count, availability, seller, and currency from the same
  block. All field extractors check this cache before touching the DOM.
- **Benefit:** For Flipkart and Myntra, a single JSON-LD parse provides all fields
  with no additional selector calls.
- **Implementation:** `BaseScraper._dig_jsonld_product()`, `self._jsonld_cache` —
  `app/scraper_v2/scrapers/base.py`

#### FEAT-004 — Adaptive Layer Ordering (ML-Ready)
- **Change:** `LayerStatsCache` queries `scrape_diagnostics` every 30 minutes and
  reorders extraction layers per portal based on historical success rates and speed.
  Scoring formula: `score = (success_rate × 0.7) - (speed_penalty × 0.3)`.
  Falls back to default order on cold start or insufficient data.
- **Implementation:** `app/scraper_v2/scrapers/layer_selector.py`
- **Status:** Infrastructure in place; requires 2+ months of production diagnostic
  data before adaptive ordering provides meaningful lift.

#### FEAT-005 — Portal-Specific skip_layers
- **Change:** `portals.yaml` supports a `skip_layers` list per portal. Layers in
  this list are bypassed entirely, saving the time otherwise spent on guaranteed
  misses. Confirmed via live HTML dump analysis.
- **Configured:**
  - Amazon: skips `meta_tags`, `json_ld`, `semantic` (all absent on Amazon.in)
  - Flipkart: skips `meta_tags`
  - Myntra: skips `meta_tags`
- **Result:** Amazon tries only `['selector']`; Flipkart and Myntra try only
  `['json_ld']`. Zero failed layers in successful scrapes.
- **Implementation:** `PortalConfig.skip_layers`, `BaseScraper._extract_price_with_fallbacks(skip_layers=)`

#### FEAT-006 — Per-Portal Browser Engine Selection
- **Change:** `portals.yaml` supports a `browser` field (`"chromium"` or
  `"firefox"`). Portals that block headless Chromium at the TLS fingerprint level
  can specify Firefox. `run_test.py` and `WorkerManager` read this field and
  launch the correct browser engine automatically.
- **Configured:** `myntra: browser: firefox`
- **Confirmed:** Myntra blocks headless Chromium (TLS fingerprinting); Firefox
  headless bypasses the block completely.
- **Implementation:** `PortalConfig.browser`, `run_test.py` browser launch block,
  `WorkerManager` (pending cutover)

#### FEAT-007 — Pre-Extract Hooks System
- **Change:** Portal-specific page interactions (modal dismissal, human simulation)
  run before extraction begins. Hooks are registered by name in `hooks.py` and
  referenced in `portals.yaml` via `pre_extract_hook`. No portal logic anywhere else.
- **Hooks implemented:**

  | Hook | Portal | Purpose |
  |---|---|---|
  | `dismiss_flipkart_login` | Flipkart | Dismiss login modal (500ms probe per selector) |
  | `simulate_amazon_human_behaviour` | Amazon | Mouse moves, scroll, 800–1400ms dwell |
  | `patch_myntra_headless` | Myntra | JS property patches + gentle scroll |

- **Implementation:** `app/scraper_v2/scrapers/hooks.py`

#### FEAT-008 — Per-Portal Field Selectors in YAML
- **Change:** `portals.yaml` supports `title_selector`, `brand_selector`,
  `image_selector`, `seller_selector` per portal. Field extractors try the
  portal-specific selector before generic fallbacks.
- **Configured:**
  - Amazon: `title_selector: "#productTitle"`, `brand_selector: "#bylineInfo"`,
    `image_selector: "#landingImage"`, `seller_selector: "#sellerProfileTriggerId"`
  - Flipkart: all null (JSON-LD covers all fields)
  - Myntra: all null (JSON-LD covers all fields)
- **Implementation:** `GenericScraper._extract_name/brand/image/seller()`

#### FEAT-009 — Scrape Diagnostics Table (Schema Ready)
- **Change:** `scrape_diagnostics` ORM model and repository defined for per-layer
  observability. Every scrape attempt will write which layers were tried, which
  succeeded, timing per phase, and error details. Linked to `price_history` via
  `scrape_job_id`. 90-day retention.
- **Status:** Schema and repository implemented. Alembic migration not yet run.
  Data collection wired when `scraper_worker.py` cutover happens.
- **Implementation:** `app/scraper_v2/diagnostics/`

#### FEAT-010 — CLI Test Tool (`run_test.py`)
- **Change:** Standalone CLI for testing any portal URL without a running server
  or database. Supports `--verbose`, `--dump-html`, `--inspect-html`,
  `--no-headless`, `--firefox`, `--curl-cffi`.
- **Implementation:** `app/scraper_v2/run_test.py`

#### FEAT-011 — goto_wait_until Per Portal
- **Change:** `portals.yaml` supports `goto_wait_until` to override the default
  `"domcontentloaded"` wait strategy per portal.
- **Implementation:** `PortalConfig.goto_wait_until`, used in `GenericScraper` navigation block.

---

### Deviations from Original Design

#### DEV-001 — JSON-LD Parsed from Raw HTML, Not DOM
- **Affects:** Layer 2 extraction
- **Original:** `script.inner_text()` / `text_content()` to read JSON-LD blocks
- **Actual:** Regex over `page.content()` raw HTML source
- **Reason:** Flipkart's React app mutates `<script>` tag content after hydration,
  truncating product names in the DOM (appending `...more`). The raw HTML source
  retains the full value. `page.content()` returns the serialised DOM which also
  reflects this mutation, but the regex approach applied before React mutates
  catches the correct value more reliably.
- **Remaining issue:** `page.content()` is also post-hydration; Flipkart name still
  truncated via JSON-LD. Resolved by falling through to OG title when JSON-LD name
  ends with `...more`.

#### DEV-002 — OG Title Used as Name Fallback for Flipkart
- **Affects:** `GenericScraper._extract_name()`
- **Original:** JSON-LD name used directly
- **Actual:** If JSON-LD name ends with `...more` (Flipkart truncation), falls
  through to `meta[property="og:title"]` and strips the ` - Buy ... | Flipkart.com`
  portal suffix.
- **Reason:** Flipkart truncates the product title in JSON-LD at ~70 characters
  when rendered via React; OG title contains the full name.

#### DEV-003 — Myntra Uses Firefox, Not Chromium
- **Affects:** SAD §15 (Playwright Design), LLD §12
- **Original:** All portals use `pw.chromium.launch(headless=True)`
- **Actual:** Myntra uses `pw.firefox.launch(headless=True)`
- **Reason:** Myntra performs TLS fingerprinting on the Chromium handshake and
  drops the connection before the first byte is sent. Firefox has a distinct TLS
  profile that bypasses this block. Confirmed via systematic testing:
  HTTP/2 error → timeout on Chromium; 447 KB product page on Firefox headless.

#### DEV-004 — dismiss_flipkart_login Probe Timeout Reduced
- **Affects:** `hooks.py`
- **Original:** 2000ms per selector × 5 selectors = up to 10s when no modal present
- **Actual:** 500ms per selector — exits in under 2.5s when no modal appears
- **Reason:** Flipkart shows the login modal inconsistently; most headless loads
  skip it entirely. The full 2s timeout was burning ~10s of dead time per scrape.

#### DEV-005 — Hook Signature Accepts Optional url Kwarg
- **Affects:** `hooks.py`, all hook functions
- **Original:** `def hook(page: Page) -> None`
- **Actual:** `def hook(page: Page, url: Optional[str] = None) -> None`
- **Reason:** `hooks.run()` passes `url=url` to all hooks uniformly so hooks that
  need the original URL (e.g. redirect recovery after interstitial) can use it.
  Hooks that don't need it ignore it via the default.

#### DEV-006 — Amazon Hook Is Human-Simulation, Not Interstitial Click
- **Affects:** `hooks.py`, original `dismiss_amazon_interstitial`
- **Original:** Hook clicked "Continue shopping" button on Amazon interstitial
- **Actual:** Hook (`simulate_amazon_human_behaviour`) performs random mouse
  movement, page scroll, and random dwell (800–1400ms) before extraction.
  Does not click anything.
- **Reason:** Clicking "Continue shopping" redirected to homepage instead of
  returning to product page — making extraction worse. The goal is to avoid the
  interstitial appearing at all, not to click through it.

#### DEV-007 — CSS Selector Cascade Uses 1500ms Timeout Cap
- **Affects:** `BaseScraper._try_css_selectors()`
- **Original:** Full `page_selector_timeout_ms` (5000ms) applied per selector
- **Actual:** `cascade_timeout = min(timeout_ms, 1500)` — 1500ms cap per selector
- **Reason:** 11 selectors × 5000ms worst-case = 55s per layer when elements are
  absent. 1500ms is sufficient for elements that need a render tick; the full
  timeout is still used for targeted `wait_for_selector` calls outside the cascade.

#### DEV-008 — ScrapeResponse Is a Dataclass, Not ScrapeResult
- **Affects:** `app/scraper_v2/models/scrape_result.py`
- **Original LLD:** `ScrapeResult` dataclass (from `app/scrapers/base.py`)
- **Actual:** `ScrapeRequest` + `ScrapeResponse` dataclasses with richer
  diagnostics fields (layers_attempted, layers_failed, extraction_ms,
  navigation_ms, worker_id, attempt_number, error_type, error_message).
- **Reason:** Diagnostic observability requires more than price + availability;
  `scraper_worker.py` needs to know which layers ran and why the scrape
  succeeded or failed.

---

### Portal Test Results (July 2026)

Confirmed working against live URLs. Results may vary with time as portal
CSS classes rotate.

| Portal | URL Pattern | Method | Price | Name | Brand | Avail | Rating | Reviews | Image | Seller | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Amazon | `amazon.in/dp/{ASIN}` | Layer 4 selector | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ~7–10s |
| Flipkart | `flipkart.com/.../p/{PID}` | Layer 2 JSON-LD | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ~3–4s |
| Myntra | `myntra.com/.../buy` | Layer 2 JSON-LD | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ~4s |

Notes:
- Flipkart seller: not present in JSON-LD for most products; CSS selector not confirmed
- Myntra rating/reviews: not present in JSON-LD for this product; may exist on others
- Seller is not critical for PriceMonitor core functionality

---

### Configuration Added

New settings in `app/scraper_v2/core/config.py`:

| Setting | Default | Used by | Description |
|---|---|---|---|
| `layer_stats_refresh_min` | `30` | LayerStatsCache | Minutes between diagnostic data refresh |
| `layer_stats_lookback_days` | `30` | LayerStatsCache | Days of history for layer scoring |
| `layer_stats_min_samples` | `20` | LayerStatsCache | Min samples before adaptive ordering activates |
| `layer_score_success_weight` | `0.7` | LayerStatsCache | Weight of success rate in layer scoring |
| `layer_score_speed_weight` | `0.3` | LayerStatsCache | Weight of speed in layer scoring |
| `page_goto_timeout_ms` | `30000` | GenericScraper | Playwright page.goto() timeout |
| `page_selector_timeout_ms` | `5000` | BaseScraper | Max wait per selector (capped to 1500ms in cascade) |

New fields in `portals.yaml` / `PortalConfig` (not in original LLD):

| Field | Type | Default | Description |
|---|---|---|---|
| `skip_layers` | `list[str]` | `[]` | Layers to bypass entirely for this portal |
| `browser` | `str` | `"chromium"` | Browser engine: `"chromium"` or `"firefox"` |
| `goto_wait_until` | `str` | `"domcontentloaded"` | Playwright wait_until strategy for page.goto() |
| `title_selector` | `str\|null` | `null` | Portal-specific CSS selector for product title |
| `brand_selector` | `str\|null` | `null` | Portal-specific CSS selector for brand |
| `image_selector` | `str\|null` | `null` | Portal-specific CSS selector for product image |
| `seller_selector` | `str\|null` | `null` | Portal-specific CSS selector for seller name |
| `scraper_api_required` | `bool` | `false` | Reserved — no longer used (replaced by `browser`) |

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | `scraper_worker.py` still uses old `app/scrapers/` layer — cutover not done | `app/workers/scraper_worker.py` | Phase 2 cutover |
| DEF-002 | `WorkerManager` hardcodes `pw.chromium.launch()` — Firefox support for Myntra not wired into production worker | `app/workers/scraper_worker.py` | Phase 2 cutover |
| DEF-003 | Alembic migration for `scrape_diagnostics` table not run — diagnostic data collection not active | `app/scraper_v2/diagnostics/` | Before Phase 2 cutover |
| DEF-004 | Adaptive layer ordering (LayerStatsCache) has no data — uses default order for all portals | `app/scraper_v2/scrapers/layer_selector.py` | After 2+ months production data |
| DEF-005 | Amazon PA-API (Layer 6 affiliate_api) is a stub — pending API access approval | `app/scraper_v2/scrapers/base.py` | When PA-API access received |
| DEF-006 | Flipkart affiliate API: same as above — stub only | `app/scraper_v2/scrapers/base.py` | When affiliate access received |
| DEF-007 | Myntra seller not extracted — absent from JSON-LD on tested products; CSS selector not identified | `app/scraper_v2/scrapers/generic_scraper.py` | Low priority — seller not critical |
| DEF-008 | Myntra rating/reviews null on some products — may be absent from JSON-LD for certain categories | `app/scraper_v2/scrapers/generic_scraper.py` | Investigate per category |
| DEF-009 | Flipkart seller null — JSON-LD `offers.seller` absent on most products; CSS classes obfuscated | `app/scraper_v2/scrapers/portals.yaml` | Low priority |
| DEF-010 | `ScraperAPIFallback` stub not implemented — Zyte/ScrapeOps integration pending | `app/scraper_v2/scrapers/base.py` | Phase 3 |
| DEF-011 | LLM extraction layer (Layer 6b) not implemented — Groq free API identified as best option | `app/scraper_v2/scrapers/base.py` | Phase 3 |
| DEF-012 | `--inspect-html` in run_test.py requires `beautifulsoup4` + `lxml` — not in requirements.txt | `app/scraper_v2/run_test.py` | Dev dependency only |
| DEF-013 | Amazon extraction time ~7–10s — dominated by human-simulation hook (3–4s) and navigation (4s). Hook dwell time acceptable for async workers but worth tuning. | `app/scraper_v2/scrapers/hooks.py` | Phase 2 tuning |

---

### New Files Added

All files under `app/scraper_v2/` are new. Files not in the original LLD:

| File | Purpose |
|---|---|
| `app/scraper_v2/__init__.py` | Package marker |
| `app/scraper_v2/run_test.py` | CLI test tool — `--verbose`, `--dump-html`, `--inspect-html`, `--curl-cffi`, `--firefox`, `--no-headless` |
| `app/scraper_v2/core/config.py` | Scraper-specific settings (layer weights, timeouts) |
| `app/scraper_v2/core/exceptions.py` | `ScrapeExtractionError`, `ScrapeFailureReason` enum |
| `app/scraper_v2/core/logging.py` | Logger factory |
| `app/scraper_v2/models/scrape_result.py` | `ScrapeRequest`, `ScrapeResponse` dataclasses |
| `app/scraper_v2/scrapers/base.py` | `BaseScraper` — 6 extraction layers, field extractors, JSON-LD cache |
| `app/scraper_v2/scrapers/generic_scraper.py` | `GenericScraper` — portal-agnostic scrape orchestration |
| `app/scraper_v2/scrapers/hooks.py` | Portal-specific hooks registry |
| `app/scraper_v2/scrapers/layer_selector.py` | `LayerStatsCache` — adaptive layer ordering |
| `app/scraper_v2/scrapers/portal_config.py` | `PortalConfig` dataclass + YAML loader |
| `app/scraper_v2/scrapers/portals.yaml` | All portal definitions — selectors, hooks, skip_layers, browser |
| `app/scraper_v2/scrapers/registry.py` | Domain/platform → `PortalConfig` lookup |
| `app/scraper_v2/diagnostics/models.py` | `ScrapeDiagnostic` ORM model |
| `app/scraper_v2/diagnostics/repository.py` | `ScrapeDiagnosticRepository` — insert, stats, purge |
| `app/scraper_v2/tests/__init__.py` | Test package marker |

---

### Deployment Notes

| Item | Note |
|---|---|
| Firefox installation | `playwright install firefox` required on Railway and GitHub Actions before cutover |
| Chromium args | `--disable-blink-features=AutomationControlled`, `--disable-http2` added to all Chromium launches |
| Browser RAM | Firefox adds ~120 MB per worker in addition to existing Chromium workers. With 3 Chromium + 1 Firefox worker: ~900 MB total — within Railway starter plan |
| `scrape_diagnostics` table | Alembic migration must run before first production scrape with scraper_v2 |
| `run_test.py` dev dependencies | `beautifulsoup4`, `lxml`, `curl_cffi` — install locally only, not in `requirements.txt` |
| Portal CSS drift | Flipkart CSS classes rotate periodically. JSON-LD is the primary layer — CSS selectors are fallback only. Monitor `layers_failed` in diagnostics for drift signals. |

---

*Archive this file to `docs/changelog/v2.0-scraper.md` when Phase 2 cutover begins.*
