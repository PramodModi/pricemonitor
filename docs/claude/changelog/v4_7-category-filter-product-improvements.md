# PricePing — Changelog

All notable changes to design documents and implementation are recorded here.
When a phase is complete, this file is archived to `docs/changelog/` and a new one started.

Format:
- **FEAT** — new feature not in original docs
- **DEV** — deviation from original design
- **FIX** — bug fix during implementation
- **CFG** — new configuration added
- **DEF** — known issue deferred to future phase
- **OPS** — operational/deployment note

---

## [v4.7] — Category Filtering, Filter Bar, Product Page Improvements — August 2026

This phase adds unified product category classification across all three portals,
a collapsible filter bar on the Offers and Dashboard pages, and several product
page improvements including email identity display, contextual back navigation,
and favicon support.

**Scope of this phase:** `category` column on `products` table, `CategoryMapper`
for unified classification, scraper + engine + worker wired to populate category,
`FilterBar` shared component, `useProducts` hook updated for multi-select,
`OffersPageClient` and dashboard page updated with filter bar, product page
`layout.jsx` added, `Breadcrumb` contextual back nav, `SidebarPriceBox` email hint,
favicon SVG + `layout.jsx` metadata.

---

### Summary of Changes

| Area | Change |
|---|---|
| `alembic/versions/80656f837eea_add_product_category.py` | New migration — adds `category VARCHAR(50) DEFAULT 'other'` to `products` |
| `app/core/models/product.py` | `category` mapped column added |
| `app/fastapi/schemas/product.py` | `category` field added to `ProductOut` and `ProductListItem` |
| `app/fastapi/api/v1/products.py` | `?category=` filter param added to `GET /v1/products`; `update_category()` called in all write paths |
| `app/repositories/product_repo.py` | `category` column added to `get_all()` query; `?category=` filter applied; `update_category()` method added |
| `app/scraper_v2/scrapers/category_mapper.py` | New file — maps raw portal category text to unified slug |
| `app/scraper_v2/models/scrape_result.py` | `category: Optional[str] = None` added to `ScrapeResponse` |
| `app/scraper_v2/scrapers/generic_scraper.py` | Category classification added after metadata extraction |
| `app/scraper_v2/engine.py` | `_map_category()` helper added; `category` populated in `_affiliate_result_to_scrape_response()` |
| `app/workers/scraper_worker.py` | `update_category()` called after each successful scrape |
| `priceping-ui/public/favicon.svg` | New file — indigo rounded square with bell emoji |
| `priceping-ui/src/app/layout.jsx` | `icons` metadata added for favicon |
| `priceping-ui/src/app/products/layout.jsx` | New file — wraps product pages with `Navbar` |
| `priceping-ui/src/components/shared/FilterBar.jsx` | New shared component — collapsible platform + category filter bar |
| `priceping-ui/src/hooks/useProducts.js` | Updated to support `platforms[]` and `categories[]` multi-select with parallel API calls |
| `priceping-ui/src/app/offers/OffersPageClient.jsx` | Platform tabs replaced with `FilterBar`; available categories derived from loaded products |
| `priceping-ui/src/app/(app)/dashboard/page.jsx` | `FilterBar` added; platform + category both multi-select; old platform tabs removed |
| `priceping-ui/src/components/product/Breadcrumb.jsx` | Contextual back nav — `← My Items` or `← Offers` based on `?from=` query param |
| `priceping-ui/src/components/product/SidebarPriceBox.jsx` | Email hint added below Monitor button in State B |
| `priceping-ui/src/components/dashboard/ProductCard.jsx` | `?from=dashboard` added to product page link |

---

### Features

#### FEAT-001 — Unified Product Category Classification
- **Files:** `app/scraper_v2/scrapers/category_mapper.py` (new),
  `app/scraper_v2/models/scrape_result.py`, `app/scraper_v2/scrapers/generic_scraper.py`,
  `app/scraper_v2/engine.py`, `app/workers/scraper_worker.py`,
  `app/core/models/product.py`, `app/fastapi/schemas/product.py`,
  `app/fastapi/api/v1/products.py`, `app/repositories/product_repo.py`
- **Change:** Products are now classified into a unified set of 9 categories:
  `mobiles`, `electronics`, `fashion`, `home`, `beauty`, `sports`, `books`,
  `toys`, `other`. Classification happens at scrape time via `CategoryMapper`
  which reads `product_metadata["subcategory"]` first (more specific), then
  `product_metadata["category"]` as fallback, and maps to the unified slug via
  keyword matching.
- **Portal-specific behaviour:**
  - **Flipkart:** Category comes from affiliate API response (`category='Mobiles'`)
    — handled in `engine._map_category()` since affiliate path skips browser scraper.
  - **Amazon:** Breadcrumb is `"Electronics"` (top-level) but subcategory is
    `"Smartphones"` — subcategory-first logic correctly maps phones to `mobiles`
    instead of `electronics`.
  - **Myntra:** Category comes from `product_metadata["category"]` scraped from
    page (`"Clothing"` → `fashion`).
- **DB:** `category` column added with `server_default='other'` — all existing
  rows default to `'other'` and are reclassified on next cron scrape.
- **Write paths:** `update_category()` called in preview (PATH B new + existing),
  background scrape, and cron worker. Only overwrites `'other'` with a specific
  slug — a failed classification never overwrites a previously correct category.

#### FEAT-002 — Collapsible Filter Bar (Offers + Dashboard)
- **Files:** `priceping-ui/src/components/shared/FilterBar.jsx` (new),
  `priceping-ui/src/app/offers/OffersPageClient.jsx`,
  `priceping-ui/src/app/(app)/dashboard/page.jsx`,
  `priceping-ui/src/hooks/useProducts.js`
- **Change:** Both Offers and Dashboard pages now have a collapsible horizontal
  filter bar above the product grid. Collapsed state shows a "Filters" button
  with active filter count badge and removable chips for active selections.
  Expanded state shows two rows: Platform (checkbox-style pills, multi-select)
  and Category (pills, multi-select).
- **Platform filter:** Multi-select — user can select Amazon + Flipkart together
  to compare the same product across portals. "All" chip auto-checks when all
  platforms are deselected.
- **Category filter:** Multi-select pills — only categories that have at least
  one product are shown (derived client-side from loaded items). Empty categories
  are hidden rather than greyed out.
- **Offers page:** Platform + category filter hits the API (`useProducts` makes
  parallel calls for each platform × category combination and merges results
  client-side, deduplicating by `product_id`).
- **Dashboard page:** Platform + category filter is client-side only (all items
  already loaded via `useItems`). No extra API calls.
- **Mobile:** Filter bar collapses to a single "Filters (N)" button; same
  expand/collapse behaviour applies.

#### FEAT-003 — Favicon
- **Files:** `priceping-ui/public/favicon.svg` (new),
  `priceping-ui/src/app/layout.jsx`
- **Change:** Browser tab now shows an indigo rounded square (`#4338ca`) with
  a bell emoji `🔔` — matching the navbar logo. Added as SVG for sharpness
  at all sizes. `icons.icon` and `icons.apple` set in `metadata` export.

#### FEAT-004 — Product Page Navbar + Email Identity
- **Files:** `priceping-ui/src/app/products/layout.jsx` (new),
  `priceping-ui/src/components/product/SidebarPriceBox.jsx`
- **Change:** Product pages (`/products/[slug]`) now render `Navbar` via a
  dedicated `layout.jsx`. Previously the product page had no header — no logo,
  no navigation, no email display. With `Navbar` in place, logged-in users see
  their email avatar dropdown in the top-right (State B), consistent with all
  other public pages.
- **Email hint in sidebar:** When user email is known and the product is not
  yet tracked (State B), a subtle hint appears below the Monitor button:
  `"Pings go to user@example.com"`. Long emails truncate with `…`.

#### FEAT-005 — Contextual Back Navigation on Product Page
- **Files:** `priceping-ui/src/components/product/Breadcrumb.jsx`,
  `priceping-ui/src/components/dashboard/ProductCard.jsx`
- **Change:** The back link on the product page breadcrumb is now contextual:
  - Opened from Dashboard (`?from=dashboard`) + email known → `← My Items`
  - Opened from Offers or directly → `← Offers`
- **Implementation:** `ProductCard` appends `?from=dashboard` to the product
  page URL. `Breadcrumb` reads the `?from=` query param via `useSearchParams`
  (wrapped in Suspense boundary). `document.referrer` was not used because
  Next.js client-side navigation does not set it.

---

### Fixes

#### FIX-001 — Category Mapper Subcategory Priority
- **File:** `app/scraper_v2/scrapers/category_mapper.py`
- **Symptom:** Amazon phones were classified as `electronics` instead of `mobiles`
  because the top-level breadcrumb `"Electronics"` matched the `electronics` rule
  before subcategory `"Smartphones"` was checked.
- **Fix:** `map_category_from_metadata()` now tries `subcategory` first and only
  falls back to `category` when subcategory produces `"other"` or is absent.

#### FIX-002 — Category Not Written on Preview Path
- **File:** `app/fastapi/api/v1/products.py`
- **Symptom:** Newly previewed products had `category = 'other'` in the DB even
  when `product_metadata` contained a valid `"category"` key.
- **Root cause:** `update_category()` was only called from `scraper_worker.py`
  (cron path). The preview router's PATH B (new product) and PATH B (existing
  product update) both write metadata but never called `update_category()`.
- **Fix:** `update_category()` added to all three write paths in `products.py`:
  background scrape, PATH B new product, PATH B existing product update.

#### FIX-003 — Affiliate API Path Skipped Category Classification
- **File:** `app/scraper_v2/engine.py`
- **Symptom:** Flipkart products (which use the affiliate API) always had
  `category = 'other'` — the affiliate API path bypasses `generic_scraper.py`
  entirely so `CategoryMapper` was never called.
- **Fix:** `_map_category()` helper added to `ScraperEngine`. Called inside
  `_affiliate_result_to_scrape_response()` which reads `result.metadata` (the
  affiliate API already parses `category` into this dict).

#### FIX-004 — Duplicate Back Navigation on Product Page
- **File:** `priceping-ui/src/components/product/Breadcrumb.jsx`,
  `priceping-ui/src/app/products/[slug]/page.jsx`
- **Symptom:** Two back links appeared on the product page — `← Offers` added
  to `product_page.jsx` and `← My Items` from the existing `Breadcrumb` component.
- **Fix:** Back navigation consolidated into `Breadcrumb.jsx` only. The
  `product_page.jsx` addition reverted. `Breadcrumb` now handles both cases
  via `useSearchParams`.

#### FIX-005 — Dangerous `drop_table` in Autogenerated Migration
- **File:** `alembic/versions/80656f837eea_add_product_category.py`
- **Symptom:** `alembic revision --autogenerate` generated drop statements for
  `scrape_diagnostics` table (4 indexes + table drop) in `upgrade()` because
  the table has no corresponding SQLAlchemy model.
- **Fix:** Drop statements removed manually before running migration. Only the
  `add_column('products', 'category')` statement retained.

---

### Deviations from Design

#### DEV-001 — Subcategory-First Classification (Not Documented in LLD)
- **Original design:** No category classification documented — the `metadata`
  JSONB field was intended to store the raw portal category string.
- **Actual:** A unified classification layer (`CategoryMapper`) maps raw portal
  categories to a fixed 9-slug taxonomy. Subcategory is checked before category
  to handle Amazon's broad top-level taxonomy (`"Electronics"` covers phones,
  laptops, TVs — subcategory disambiguates).

#### DEV-002 — Parallel API Calls for Multi-Select Filtering
- **Original design:** `useProducts` made a single API call with one platform
  filter at a time.
- **Actual:** When multiple platforms or categories are selected, `useProducts`
  makes parallel API calls (one per platform × category pair) and merges results
  client-side. Results are deduplicated by `product_id` and re-sorted by
  `watcher_count` descending.

#### DEV-003 — Filter Bar Replaces Platform Tabs (Not Sidebar)
- **Original design considered:** Left sidebar filters (separate panel next to
  nav sidebar). Rejected — two sidebars side by side felt cluttered.
- **Actual:** Horizontal collapsible filter bar above the product grid.
  Collapsed state shows active filter chips inline. No layout column added.

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not implemented | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not run | Before Profile page goes live |
| DEF-007 | Product page URL uses `product_id` UUID — no slug column yet | Phase 2 |
| DEF-008 | No rate limiting on preview endpoint | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not built | When auth implemented |
| DEF-011 | `GET /v1/health` endpoint not implemented — AppShell health check disabled | When endpoint added |
| DEF-012 | Buy recommendation for new products shows generic "insufficient data" message | Next session |
| DEF-013 | `ProductDescription.jsx` and `FullSpecsTable.jsx` unused — can be deleted | Cleanup |
| DEF-014 | Flipkart `special_price` fix applies to future scrapes only — not backfilled | Manual re-track or wait for cron |
| DEF-016 | Flipkart short URL stores short URL in DB not real URL | When slug column added |
| DEF-017 | DMARC policy is `p=none` — upgrade to `p=quarantine` after clean delivery confirmed | DNS-only change |
| DEF-018 | Existing products with `category='other'` reclassified only on next cron scrape — no backfill | Automatic over 4-hour cron cycles |
| DEF-019 | Price chart Y-axis shows negative values when price variation is very small | Next session |
| DEF-020 | Product page opened in new tab refetches dashboard items on `← My Items` — cache not shared across tabs | Acceptable — cannot be fixed without same-tab navigation |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **Price chart Y-axis fix** | Medium | Negative Y values when price data has very small variance (DEF-019) |
| **`GET /v1/health`** | Medium | Re-enables AppShell health check banner |
| **`PATCH /v1/subscriptions/{id}`** | Medium | `target_price` persistence — unlocks `TargetPriceInput` |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **DMARC tighten** | Low | Change `p=none` → `p=quarantine; pct=25` after clean delivery confirmed |
| **Products slug column** | Low | Phase 2 — slug backfill + `GET /v1/products/by-slug/{slug}` |

---

### Files Modified

| File | Change type | Description |
|---|---|---|
| `alembic/versions/80656f837eea_add_product_category.py` | FEAT | New migration — `category VARCHAR(50) DEFAULT 'other'` on `products` table |
| `app/core/models/product.py` | FEAT | `category: Mapped[str]` column added |
| `app/fastapi/schemas/product.py` | FEAT | `category: Optional[str] = 'other'` added to `ProductOut` and `ProductListItem` |
| `app/fastapi/api/v1/products.py` | FEAT/FIX | `?category=` query param added; `update_category()` called in all three write paths |
| `app/repositories/product_repo.py` | FEAT | `category` in `get_all()` SELECT; `?category=` WHERE clause; `update_category()` method |
| `app/scraper_v2/scrapers/category_mapper.py` | FEAT | New file — `map_category()` and `map_category_from_metadata()` with 9-slug taxonomy |
| `app/scraper_v2/models/scrape_result.py` | FEAT | `category: Optional[str] = None` added to `ScrapeResponse` |
| `app/scraper_v2/scrapers/generic_scraper.py` | FEAT | Category classification after metadata extraction; `category` in `ScrapeResponse` |
| `app/scraper_v2/engine.py` | FIX | `_map_category()` helper; `category=` in `_affiliate_result_to_scrape_response()` |
| `app/workers/scraper_worker.py` | FEAT | `update_category()` called after successful scrape; only updates when non-`'other'` or confirms `'other'` |
| `priceping-ui/public/favicon.svg` | FEAT | New — indigo rounded square + bell emoji |
| `priceping-ui/src/app/layout.jsx` | FEAT | `icons: { icon, apple }` added to metadata |
| `priceping-ui/src/app/products/layout.jsx` | FEAT | New — wraps product pages with `Navbar` |
| `priceping-ui/src/components/shared/FilterBar.jsx` | FEAT | New — collapsible filter bar with platform + category multi-select |
| `priceping-ui/src/hooks/useProducts.js` | FEAT | Multi-select `platforms[]` + `categories[]`; parallel API calls with client-side merge |
| `priceping-ui/src/app/offers/OffersPageClient.jsx` | FEAT | Platform tabs replaced with `FilterBar`; `availableCategories` derived from loaded products |
| `priceping-ui/src/app/(app)/dashboard/page.jsx` | FEAT | `FilterBar` added; `activePlatforms[]` replaces `activePlatform`; old tabs removed |
| `priceping-ui/src/components/product/Breadcrumb.jsx` | FEAT/FIX | Contextual back nav via `useSearchParams`; `← My Items` vs `← Offers`; product name truncated on all screen sizes |
| `priceping-ui/src/components/product/SidebarPriceBox.jsx` | FEAT | Email hint added in State B: `"Pings go to user@example.com"` |
| `priceping-ui/src/components/dashboard/ProductCard.jsx` | FEAT | `?from=dashboard` appended to product page URL |

---

*Archive this file to `docs/changelog/v4_7-category-filter-product-improvements.md` when the next phase begins.*
