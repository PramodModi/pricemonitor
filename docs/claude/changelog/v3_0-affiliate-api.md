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

## [v3.0] — Flipkart Affiliate API + Preview Rearchitecture — August 2026

This phase introduces three major changes:

**1. Flipkart Affiliate API layer** — a new `app/scraper_v2/affiliate/` package
with an abstract base class (`BaseAffiliateClient`), a concrete Flipkart
implementation (`FlipkartAffiliateClient`), and an Amazon stub ready for PA-API.
The affiliate API is wired into `ScraperEngine` as attempt 0 — tried before any
Playwright browser is opened. On success it returns instantly with enriched data
(MRP, selling price, discount %, bank offers); on miss the existing 5-attempt
browser cascade runs unchanged.

**2. Affiliate enrichment fields in DB** — four new columns added to the
`products` table (`mrp`, `special_price`, `discount_pct`, `offers`). Written
on every successful affiliate API call (preview, confirm, cron). Read directly
from DB on product detail page load — no live API call needed.

**3. Preview rearchitecture** — product data is now written to DB at preview
time, not at confirmation time. `ProductSyncService.sync()` is reduced to
subscription-only. PATH A (known product) returns DB data instantly and triggers
a background scrape to refresh the DB. PATH B (new product) scrapes, writes
product to DB immediately, then returns the preview.

One database migration. No new pip dependencies. Fifteen files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/scraper_v2/affiliate/` | New package — 6 files (base, exceptions, result, flipkart, amazon, __init__) |
| `app/scraper_v2/engine.py` | Attempt 0 affiliate API block; `_affiliate_result_to_scrape_response()` helper |
| `app/scraper_v2/models/scrape_result.py` | Four new fields on `ScrapeResponse`: `mrp`, `special_price`, `discount_pct`, `offers` |
| `app/scraper_v2/scrapers/base.py` | `_try_affiliate_api()` replaced with no-op stub (superseded by affiliate package) |
| `app/core/config.py` | `flipkart_affiliate_token: str = ""` added |
| `app/core/models/product.py` | Four new ORM columns: `mrp`, `special_price`, `discount_pct`, `offers` |
| `app/repositories/product_repo.py` | `update_affiliate_data()` method added |
| `app/fastapi/schemas/product.py` | `mrp`, `special_price`, `discount_pct`, `offers` added to `LiveData` and `ProductOut`; `coerce_offers` validator added |
| `app/fastapi/api/v1/products.py` | PATH A background scrape; PATH B writes product to DB; `get_product()` reads affiliate fields from DB |
| `app/services/product_sync.py` | Stripped to subscription-only — product create/update moved to preview endpoint |
| `app/workers/scraper_worker.py` | `_write_result()` writes affiliate enrichment fields to DB |
| `alembic/versions/b3f9d12e4c71_*.py` | Migration: adds `mrp`, `special_price`, `discount_pct`, `offers` to `products` |
| `streamlit_app/components/preview_card.py` | MRP strikethrough, discount badge, offer price, bank offers expander |
| `streamlit_app/pages/product.py` | Same enrichment display on product detail page; IST timezone fix |

---

### Features

#### FEAT-001 — Affiliate API Abstract Base Class
- **File:** `app/scraper_v2/affiliate/base.py`
- **Change:** `BaseAffiliateClient` ABC defines the contract for all marketplace
  API clients. Subclasses implement 5 abstract members: `platform_name`,
  `can_handle()`, `extract_product_id()`, `_authenticate()`, `_fetch()`.
  All retry, backoff, re-auth, and logging logic lives in the base class.
- **Adding a new marketplace:** create a subclass, implement the 5 abstract
  members, register in `__init__.py`. Zero changes to `base.py`, `engine.py`,
  or any existing client.

#### FEAT-002 — Exponential Backoff Retry (3 attempts, 1s / 2s)
- **File:** `app/scraper_v2/affiliate/base.py` — `_call_with_retry()`
- **Change:** Up to 3 API call attempts per `fetch()` invocation with delays
  `1s → 2s` between attempts.
- **Per error-type behaviour:**

  | Error type | Behaviour |
  |---|---|
  | `AffiliateNotFoundError` | Return `None` immediately — not retriable |
  | `AffiliateTimeoutError` | Re-auth once, then retry with backoff |
  | `AffiliateAuthError` | Re-auth once, then retry; give up if re-auth fails |
  | `AffiliateRateLimitError` | Wait 30s flat, then retry (no re-auth) |
  | `AffiliateError` (base) | Log and retry with backoff |
  | All attempts exhausted | Return `None` — engine falls through to browser cascade |

#### FEAT-003 — Re-authentication on Timeout or Auth Error
- **File:** `app/scraper_v2/affiliate/base.py`
- **Change:** `_reauth_done` flag limits re-auth to once per `fetch()` call.
  On `AffiliateTimeoutError` or `AffiliateAuthError`, `_authenticate()` is
  called before the next retry. If re-auth fails, returns `None` immediately.

#### FEAT-004 — FlipkartAffiliateClient
- **File:** `app/scraper_v2/affiliate/flipkart.py`
- **Endpoint:** `GET https://affiliate-api.flipkart.net/affiliate/1.0/product.json?id=<PID>`
- **Auth:** `Fk-Affiliate-Id` + `Fk-Affiliate-Token` headers (stateless)
- **PID extraction:** `?pid=` query param first, then `/p/itm{id}` path fallback
- **Fields returned:** `price` (flipkartSellingPrice), `mrp` (maximumRetailPrice),
  `special_price` (flipkartSpecialPrice), `discount_pct`, `name`, `image_url`,
  `brand`, `availability`, `offers` (raw strings), `seller_name`, `cod_available`
- **Schema:** handles both v0.1.0 (`productBaseInfo.productAttributes`) and
  v1.0 (`productBaseInfoV1`) response shapes

#### FEAT-005 — AmazonAffiliateClient (Stub)
- **File:** `app/scraper_v2/affiliate/amazon.py`
- **Change:** Stub — `can_handle()` and `extract_product_id()` fully working.
  `_authenticate()` raises `AffiliateAuthError` until PA-API credentials are
  configured, making `fetch()` return `None` silently (transparent to engine).
- **Activation:** implement `_authenticate()` and `_fetch()` in `amazon.py`
  only — zero other file changes needed.

#### FEAT-006 — ScraperEngine Attempt 0 (Affiliate API)
- **File:** `app/scraper_v2/engine.py`
- **Change:** `ScraperEngine.scrape()` tries the affiliate API before opening
  any Playwright browser. On `AffiliateResult` returned → converts to
  `ScrapeResponse` with `extraction_method='affiliate_api'` and returns
  immediately. On `None` → falls through to browser cascade (attempts 1–5,
  unchanged).

#### FEAT-007 — Affiliate Enrichment Fields in DB
- **Files:** `app/core/models/product.py`, `app/repositories/product_repo.py`,
  `alembic/versions/b3f9d12e4c71_*.py`
- **Change:** Four new nullable columns on `products` table:
  - `mrp NUMERIC(10,2)` — Maximum Retail Price
  - `special_price NUMERIC(10,2)` — Price after bank/card offers
  - `discount_pct NUMERIC(5,2)` — Discount percentage off MRP
  - `offers TEXT[]` — Raw promotional offer strings (Postgres array)
- **`update_affiliate_data()`** — new `ProductRepository` method that skips
  `None` values so browser-scraped results never overwrite stored affiliate data.

#### FEAT-008 — Preview Rearchitecture (DB-write at preview time)
- **Files:** `app/fastapi/api/v1/products.py`, `app/services/product_sync.py`
- **Before:** Product row created at confirm time by `ProductSyncService.sync()`.
  Affiliate enrichment data lost between preview and confirmation.
- **After:**
  - **PATH A** (known product): returns DB data instantly, triggers background
    scrape via `FastAPI BackgroundTasks` to refresh price + affiliate fields.
  - **PATH B** (new product): scrapes live, writes product row to DB immediately
    (including affiliate fields), then returns preview. No product write at confirm.
  - **Confirm** (`ProductSyncService.sync()`): subscription-only — looks up
    product from DB, creates subscription row. No product create/update.

#### FEAT-009 — Enrichment Display in Streamlit UI
- **Files:** `streamlit_app/components/preview_card.py`,
  `streamlit_app/pages/product.py`
- **Change:** Both preview card and product detail page now display:
  - Selling price (always)
  - MRP with strikethrough (only when different from selling price)
  - Green discount badge e.g. `14% off` (only when `discount_pct` present)
  - `💰 Offer price: ₹X` (only when `special_price` < selling price)
  - `🏦 Bank & Card Offers (N available)` expander (only when `offers` non-empty)
- **Conditional rendering:** all enrichment rows are completely hidden for
  Amazon, Myntra, and browser-scraped results — no empty sections shown.

---

### Fixes

#### FIX-001 — Flipkart API Wrong Query Parameter Name
- **Affects:** `app/scraper_v2/affiliate/flipkart.py`
- **Symptom:** HTTP 400 — `Required String parameter 'id' is not present` on
  every Flipkart affiliate API call.
- **Root cause:** Initial implementation sent `?query=<PID>`. The Flipkart
  affiliate API requires `?id=<PID>`.
- **Fix:** Changed `params = {"query": product_id}` to `params = {"id": product_id}`.

#### FIX-002 — `offers` Column NULL Rejected by Pydantic
- **Affects:** `app/fastapi/schemas/product.py`
- **Symptom:** `ValidationError: offers — Input should be a valid list` on
  `GET /v1/items` for all existing products after migration.
- **Root cause:** Migration added `offers` column with no default — all existing
  rows have `NULL`. Pydantic's `list[str]` type rejects `None`.
- **Fix:** Changed to `Optional[list[str]] = []` and added `coerce_offers`
  field validator that converts `None → []`.

#### FIX-003 — `ProductOut` Duplicate Keyword Argument
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** `TypeError: ProductOut() got multiple values for keyword argument 'mrp'`
  on `GET /v1/products/{id}`.
- **Root cause:** `**{c.name: getattr(product, c.name) for c in product.__table__.columns}`
  now includes the four new ORM columns. They were also passed explicitly —
  causing duplicate keyword arguments.
- **Fix:** Removed the explicit `mrp=`, `special_price=`, `discount_pct=`,
  `offers=` arguments — the `**` spread already covers them.

#### FIX-004 — `_build_affiliated_url` Not Found in `products.py`
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** `NameError: name '_build_affiliated_url' is not defined` on
  PATH B preview for new products.
- **Root cause:** PATH B now writes product to DB directly, needing
  `_build_affiliated_url()` which lives in `product_sync.py`. It was not
  imported into `products.py`.
- **Fix:** Added `from app.services.product_sync import _build_affiliated_url`.

#### FIX-005 — IST Timezone Not Applied on Product Detail Page
- **Affects:** `streamlit_app/pages/product.py`
- **Symptom:** "Last fetched: 2 Aug, 2:52 AM" displayed instead of "8:22 AM"
  (UTC shown instead of IST).
- **Root cause:** `_format_last_fetched()` formatted the UTC datetime directly
  without converting to IST (UTC+5:30).
- **Fix:** Added `dt.astimezone(IST)` before `strftime()`. Same fix already
  applied to `preview_card.py` in an earlier phase — now consistent across both.

---

### Deviations from Design

#### DEV-001 — AffiliateResult Is a Separate Dataclass
- **Original intent:** affiliate clients could return `ScrapeResponse` directly.
- **Actual:** `AffiliateResult` is a separate dataclass in `affiliate/result.py`.
  `ScrapeResponse` is produced only in `engine.py` via
  `_affiliate_result_to_scrape_response()`.
- **Reason:** The affiliate package must be self-contained and importable
  without pulling in `scraper_v2.models` — keeping future microservice
  extraction clean. `AffiliateResult` also carries richer fields (`mrp`,
  `offers` etc.) not present in `ScrapeResponse`.

#### DEV-002 — Amazon Stub Excluded from AFFILIATE_CLIENTS
- **Original intent:** Amazon stub registered in `AFFILIATE_CLIENTS` — transparent
  because `_authenticate()` raises, making `fetch()` return `None`.
- **Actual:** `AmazonAffiliateClient` removed from `AFFILIATE_CLIENTS` entirely
  until PA-API credentials are available.
- **Reason:** Avoids unnecessary `can_handle()` call on every Amazon URL scrape.
  Re-adding requires one line in `__init__.py`.

#### DEV-003 — ProductSyncService Reduced to Subscription-Only
- **Original design (LLD §8.3):** `ProductSyncService.sync()` owned the full
  product upsert + subscription write path.
- **Actual:** Product create/update moved to `products.py` preview endpoint
  (PATH B). `sync()` now only handles User + Subscription.
- **Reason:** Writing product data at preview time (not confirm time) eliminates
  the gap where affiliate enrichment data was lost between preview and DB.
  Confirm becomes idempotent — product always exists in DB by that point.

#### DEV-004 — Background Scrape Uses FastAPI BackgroundTasks
- **Original design:** no background scrape concept in original docs.
- **Actual:** PATH A preview queues `_background_scrape_and_store()` via
  `FastAPI BackgroundTasks`. Runs after response is sent — user sees DB data
  instantly, fresh data available on next 🔄 Refresh.
- **Reason:** Balances immediacy (instant preview from DB) with freshness
  (live data available shortly after).

---

### Configuration Added

| Setting | Where | Description |
|---|---|---|
| `flipkart_affiliate_token` | `app/core/config.py` Settings | `Fk-Affiliate-Token` header value for Flipkart affiliate API |
| `FLIPKART_AFFILIATE_TOKEN` | Railway Variables + `.env` + GitHub Actions secrets | Env var for above |

**Future — Amazon PA-API (uncomment in config.py when credentials available):**

| Setting | Description |
|---|---|
| `amazon_paapi_access_key` | AWS Access Key ID for SigV4 signing |
| `amazon_paapi_secret_key` | AWS Secret Access Key |
| `amazon_paapi_partner_tag` | Associates partner tag |

---

### Database Migration

| Migration | Revision | Description |
|---|---|---|
| `b3f9d12e4c71_add_affiliate_fields_to_products.py` | `b3f9d12e4c71` | Adds `mrp`, `special_price`, `discount_pct`, `offers` to `products` table |

Run: `python -m alembic upgrade head`

No data backfill required — values populated on next preview or cron run for
each Flipkart product. Existing rows default to `NULL`; UI hides enrichment
sections when `NULL`.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Future phase |
| DEF-002 | `--reload` flag in local uvicorn wipes in-memory `PreviewCache` on file save | `app/services/preview_cache.py` | Replace with Redis |
| DEF-003 | `social_share` query param not stripped from Amazon canonical URLs | `app/services/url_validator.py` | Next phase |
| DEF-004 | UTM params not stripped from Myntra URLs | `app/services/url_validator.py` | Next phase |
| DEF-005 | `amzn.in` short URL stored as canonical URL — Path A gets empty ASIN on resubmit | `app/services/product_sync.py` | Future phase |
| DEF-006 | Background scrape in PATH A runs `ScraperEngine` which opens Playwright even when affiliate API would succeed — could be lazy-init | `app/fastapi/api/v1/products.py` | Future phase |
| DEF-007 | `mrp`/`offers` enrichment not shown in price drop email — email template uses only `current_price` | `app/notifications/email_sender.py` | Future phase |
| DEF-008 | Amazon PA-API stub — `AmazonAffiliateClient` excluded until credentials configured | `app/scraper_v2/affiliate/amazon.py` | When PA-API access received |
| DEF-009 | Adaptive layer ordering not yet active — needs 2+ months production data | `app/scraper_v2/scrapers/layer_selector.py` | Automatic |

---

### Files Added

| File | Purpose |
|---|---|
| `app/scraper_v2/affiliate/__init__.py` | `AFFILIATE_CLIENTS` registry |
| `app/scraper_v2/affiliate/exceptions.py` | `AffiliateError` hierarchy — 5 exception types |
| `app/scraper_v2/affiliate/result.py` | `AffiliateResult` dataclass — normalised product data |
| `app/scraper_v2/affiliate/base.py` | `BaseAffiliateClient` ABC — retry + backoff + re-auth |
| `app/scraper_v2/affiliate/flipkart.py` | `FlipkartAffiliateClient` — active implementation |
| `app/scraper_v2/affiliate/amazon.py` | `AmazonAffiliateClient` — PA-API stub |
| `alembic/versions/b3f9d12e4c71_add_affiliate_fields_to_products.py` | DB migration |

---

### Files Modified

| File | Change |
|---|---|
| `app/scraper_v2/engine.py` | Attempt 0 affiliate block; `_affiliate_result_to_scrape_response()`; enrichment fields in `ScrapeResponse` construction |
| `app/scraper_v2/models/scrape_result.py` | `mrp`, `special_price`, `discount_pct`, `offers` added to `ScrapeResponse` |
| `app/scraper_v2/scrapers/base.py` | `_try_affiliate_api()` replaced with no-op stub |
| `app/core/config.py` | `flipkart_affiliate_token` field added |
| `app/core/models/product.py` | `mrp`, `special_price`, `discount_pct`, `offers` ORM columns added; `ARRAY` import added |
| `app/repositories/product_repo.py` | `update_affiliate_data()` method added |
| `app/fastapi/schemas/product.py` | Enrichment fields added to `LiveData` and `ProductOut`; `coerce_offers` validator added |
| `app/fastapi/api/v1/products.py` | PATH A background scrape; PATH B DB write; `_build_affiliated_url` import; `get_product()` simplified |
| `app/services/product_sync.py` | Stripped to User + Subscription only; `price_updated` field removed from `SyncResult` |
| `app/workers/scraper_worker.py` | `_write_result()` writes affiliate enrichment via `update_affiliate_data()` |
| `streamlit_app/components/preview_card.py` | MRP, discount badge, offer price, bank offers expander; IST timezone fix |
| `streamlit_app/pages/product.py` | Same enrichment display; IST timezone fix |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| Strip dirty URL params | High | `social_share` from Amazon, UTM params from Myntra |
| Skip orphaned products in cron | Medium | Filter `get_all_for_scraping()` to products with ≥1 subscriber |
| Notification preferences | Medium | Per-subscription `notify_on_drop`/`notify_on_rise`/pause controls — full design already written |
| Activate Amazon PA-API | When credentials arrive | Implement `_authenticate()` and `_fetch()` in `amazon.py` only |
| Show MRP/offers in price drop email | Low | Pass enrichment fields through `NotificationJob` to email template |
| All-time low/high badges | Low | Visual badge when current price equals all-time low |
| Redis PreviewCache | Low | Replace in-memory dict — eliminates `--reload` restart issue |

---

*Archive this file to `docs/changelog/v3.0-affiliate-api.md` when the next phase begins.*
