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

## [v2.9] — Flipkart Affiliate Deep Link — August 2026

This phase implements Flipkart affiliate tracking using the recommended deep
link format (`dl.flipkart.com/dl/...`) which supports attribution from both
the Flipkart website and the Flipkart mobile app. Previously, only Amazon
affiliate tags were being appended; Flipkart had the `flipkart_affiliate_id`
config key wired but the wrong query parameter name was used and the affiliate
URL was never applied to existing products.

Three bugs were identified and fixed: wrong query param name (`affExtParam1`
instead of the correct `affid`), affiliate URL never backfilled on existing
products, and the scraper engine failing on the rewritten deep link domain
(`dl.flipkart.com`) because it was not registered in `portals.yaml` or
`SUPPORTED_DOMAINS`.

No database migrations. No new dependencies. Four files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/services/url_validator.py` | Added `dl.flipkart.com` to `SUPPORTED_DOMAINS`; new `_canonicalise_flipkart()` rewrites all Flipkart URLs to deep link format |
| `app/services/product_sync.py` | `_build_affiliated_url()` appends `affid=` and `affExtParam1=`; Step 2b backfills affiliate URL on existing products |
| `app/repositories/product_repo.py` | Added `update_url()` method |
| `app/scraper_v2/scrapers/portals.yaml` | Added `dl.flipkart.com` to Flipkart domains |

---

### Features

#### FEAT-001 — Flipkart Deep Link Affiliate URL
- **Affects:** `app/services/url_validator.py`, `app/services/product_sync.py`
- **Before:** Flipkart URLs were stored in the standard format
  (`www.flipkart.com/...`) with no affiliate tracking. The `flipkart_affiliate_id`
  config key existed but was never correctly applied.
- **After:** All Flipkart URLs are rewritten to the Flipkart-recommended deep
  link format at canonicalisation time, and both affiliate params are appended
  at subscription time. The stored URL works for attribution from both the
  Flipkart website and the Flipkart mobile app.
- **Deep link format:**
  ```
  https://dl.flipkart.com/dl/<product-path>?<params>&affid=<ID>&affExtParam1=<ID>
  ```
- **Example:**
  ```
  Input:   https://www.flipkart.com/sony-playstation-5-console-825-gb/p/itm62f0f8b3c0bfb
  Stored:  https://dl.flipkart.com/dl/sony-playstation-5-console-825-gb/p/itm62f0f8b3c0bfb?affid=YOUR_ID&affExtParam1=YOUR_ID
  ```
- **Why both params:** `affid=` is the primary Flipkart affiliate tracking ID
  (required for commission attribution). `affExtParam1=` is the secondary
  tracking parameter recommended by Flipkart for app + web deep link tracking.
  Both are set to the same `flipkart_affiliate_id` value from config.
- **Files:** `app/services/url_validator.py`, `app/services/product_sync.py`

#### FEAT-002 — Affiliate URL Backfill for Existing Products
- **Affects:** `app/services/product_sync.py`, `app/repositories/product_repo.py`
- **Before:** `_build_affiliated_url()` was called only in the new-product
  branch (`product is None`). Existing products already in the DB never had
  their stored URL updated with the affiliate tag.
- **After:** Step 2b in `sync()` computes the affiliated URL and compares it
  against `product.url`. If they differ (i.e. the stored URL has no affiliate
  tag, or has the old `www.flipkart.com` domain), `update_url()` is called to
  overwrite the stored URL. This fires on the next preview or subscription
  confirm for any existing product.
- **`update_url()` method:** Added to `ProductRepository` — sets `product.url`
  and calls `db.flush()`. Follows the same pattern as `update_current_price()`.
- **Files:** `app/services/product_sync.py`, `app/repositories/product_repo.py`

---

### Fixes

#### FIX-001 — Wrong Flipkart Affiliate Query Parameter Name
- **Affects:** `app/services/product_sync.py`
- **Symptom:** Flipkart affiliate ID was configured and read correctly from
  `.env`, but no affiliate commissions were being tracked because the appended
  query parameter was wrong.
- **Root cause:** `_build_affiliated_url()` used `affExtParam1=` as the sole
  parameter. The correct primary Flipkart affiliate parameter is `affid=`.
  `affExtParam1=` is a secondary parameter and has no effect on its own.
- **Fix:** Flipkart branch now appends `affid=<ID>&affExtParam1=<ID>` — both
  params with the same value, as recommended by Flipkart for app + web tracking.
- **Files:** `app/services/product_sync.py`

#### FIX-002 — Scraper Engine Failing on Deep Link Domain
- **Affects:** `app/scraper_v2/scrapers/portals.yaml`
- **Symptom:** After URL canonicalisation rewrote the domain to
  `dl.flipkart.com`, the scraper engine raised `No portal config for platform
  'dl.flipkart.com'` and returned a 502 on every Flipkart preview.
- **Root cause:** The portal registry builds its `_BY_DOMAIN` lookup at import
  time from `portals.yaml`. Only `flipkart.com` was listed under Flipkart
  domains. `dl.flipkart.com` was not registered, so `get_config_for_domain()`
  raised `UnsupportedPlatformError`.
- **Fix:** Added `dl.flipkart.com` to the `flipkart.domains` list in
  `portals.yaml`. No Python changes required — the registry rebuilds from YAML
  at startup and picks up the new domain automatically.
- **Files:** `app/scraper_v2/scrapers/portals.yaml`

#### FIX-003 — Deep Link Domain Not Accepted by URL Validator
- **Affects:** `app/services/url_validator.py`
- **Symptom:** Users who copied a Flipkart deep link URL
  (`dl.flipkart.com/dl/...`) directly from the Flipkart app would receive an
  `InvalidURLError` — "Domain 'dl.flipkart.com' is not supported."
- **Root cause:** `SUPPORTED_DOMAINS` only listed `flipkart.com` and
  `www.flipkart.com`. `dl.flipkart.com` was absent.
- **Fix:** Added `"dl.flipkart.com": "flipkart"` to `SUPPORTED_DOMAINS`.
  `_canonicalise_flipkart()` handles the case where the input is already a deep
  link (path is already `/dl/...`) — the domain is normalised without
  double-prepending `/dl`.
- **Files:** `app/services/url_validator.py`

---

### Deviations from Design

#### DEV-001 — Flipkart URL Canonicalisation Extracted to Dedicated Method
- **Affects:** `app/services/url_validator.py`
- **Original design:** `_canonicalise()` handled all platforms with a single
  generic strip-params + urlunparse path.
- **Actual:** Flipkart is routed to a new `_canonicalise_flipkart()` method.
  The generic `_canonicalise()` now only handles Amazon (the only remaining
  platform that uses it — Myntra has no strip params and Amazon has its own
  `/dp/` reconstruction path).
- **Reason:** Flipkart canonicalisation requires domain rewriting
  (`www.flipkart.com` → `dl.flipkart.com/dl`) in addition to param stripping,
  which cannot be expressed in the generic path without special-casing.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Future phase |
| DEF-002 | `--reload` flag in local uvicorn wipes in-memory `PreviewCache` on file save, causing 404 on confirm | `app/services/preview_cache.py` | Replace with Redis |
| DEF-003 | `social_share` query param not stripped from Amazon canonical URLs — stored in DB with trailing junk | `app/services/url_validator.py` — `_AMAZON_STRIP_PARAMS` | Next phase |
| DEF-004 | UTM params (`utm_source`, `utm_medium`, `utm_campaign`, `shared`) not stripped from Myntra URLs | `app/services/url_validator.py` — no `_MYNTRA_STRIP_PARAMS` defined | Next phase |
| DEF-005 | `amzn.in` short URL stored as canonical `url` in DB — Path A gets `marketplace_product_id=""` on resubmit | `app/services/product_sync.py` | Future phase |
| DEF-006 | Wall-clock timeout guard missing — preview Path B can 504 on Railway's 30s HTTP limit | `app/fastapi/api/v1/products.py` | Future phase |
| DEF-007 | Existing Flipkart products in DB still have `www.flipkart.com` URLs until next preview/confirm — backfill via SQL UPDATE if immediate migration needed | `products` table | Run SQL UPDATE manually in Supabase if required |

---

### Files Modified

| File | Change |
|---|---|
| `app/services/url_validator.py` | FIX-003, DEV-001: Added `dl.flipkart.com` to `SUPPORTED_DOMAINS`. New `_canonicalise_flipkart()` rewrites all Flipkart URLs to deep link format (`dl.flipkart.com/dl/...`), strips affiliate/tracker params, preserves `pid=` and other legitimate params. `_canonicalise()` now routes Flipkart to the new method |
| `app/services/product_sync.py` | FIX-001, FEAT-002: `_build_affiliated_url()` now appends `affid=<ID>&affExtParam1=<ID>` for Flipkart. Step 2b added to existing-product branch — computes affiliated URL and calls `update_url()` when stored URL differs |
| `app/repositories/product_repo.py` | FEAT-002: `update_url()` method added — overwrites `product.url` and flushes |
| `app/scraper_v2/scrapers/portals.yaml` | FIX-002: `dl.flipkart.com` added to `flipkart.domains` list |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| Strip dirty params from Amazon/Myntra URLs | High | Add `social_share` to `_AMAZON_STRIP_PARAMS`; add `_MYNTRA_STRIP_PARAMS` for UTM params |
| Skip orphaned products in scraper | Medium | Filter `get_all_for_scraping()` to products with at least one subscriber — saves ScraperAPI credits |
| Notification preferences | Medium | Per-subscription `notify_on_drop` / `notify_on_rise` / pause controls. Full design already written |
| All-time low/high badges | Low | Visual badge when current price equals all-time low |
| Redis PreviewCache | Low | Replace in-memory cache — eliminates the `--reload` / restart issue permanently |

---

*Archive this file to `docs/changelog/v2.9-flipkart-affiliate.md` when the next phase begins.*
