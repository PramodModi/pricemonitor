# PriceMonitor — Changelog

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

## [v3.1] — Product Metadata Enrichment + UI Fixes — August 2026

This phase introduces structured product metadata enrichment across all three
portals (Flipkart, Amazon, Myntra) and fixes several UI issues discovered in
production.

**1. Product metadata JSONB column** — a new `metadata` JSONB column on the
`products` table stores portal-specific enrichment data: description, images,
category, subcategory, specs/attributes, feature bullet points, sizes (Myntra),
material/fit/style (Myntra). Stored as a flexible key-value structure so
different portals can populate different keys without schema changes.

**2. Flipkart API enrichment** — `FlipkartAffiliateClient._parse()` extended
to extract all available fields from the API response, including
`categorySpecificInfoV1.specificationList` (specs) and `keySpecs` (features).
Previously only price/MRP/offers were extracted.

**3. Browser scraper enrichment** — `GenericScraper` extended with
`_extract_metadata()` dispatcher and three portal-specific implementations:
Amazon (DOM selectors — specs table, bullet points, breadcrumb, images),
Flipkart browser fallback (DOM — for when affiliate API fails), and Myntra
(JS state extraction from `window.__mweb_init_data__` with DOM fallback).

**4. Merge-on-write strategy** — `ScraperEngine.merge_metadata()` ensures
existing DB metadata is preserved when a browser fallback scrape cannot
provide all the fields that a previous API call captured. Existing keys win
on conflict.

**5. UI display** — product detail page now shows description (collapsed
expander), key features (expanded expander), specs as a dataframe table,
size chips (Myntra), and material/fit/style caption (Myntra).

**6. UI fixes** — price history chart date axis corrected (was showing
unordered string labels), offer price display added to dashboard cards and
product detail page.

One database migration. No new pip dependencies. Fourteen files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/scraper_v2/affiliate/result.py` | `metadata: dict` field added to `AffiliateResult` |
| `app/scraper_v2/affiliate/flipkart.py` | Extracts description, images, category, subcategory, specs, features from API response |
| `app/scraper_v2/engine.py` | Passes `product_metadata` through `_affiliate_result_to_scrape_response()`; `merge_metadata()` static method added |
| `app/scraper_v2/models/scrape_result.py` | `product_metadata: dict` field added to `ScrapeResponse` |
| `app/scraper_v2/scrapers/generic_scraper.py` | `_extract_metadata()` dispatcher + `_extract_metadata_amazon()`, `_extract_metadata_flipkart()`, `_extract_metadata_myntra()`, `_parse_myntra_state()` |
| `app/core/models/product.py` | `product_metadata` ORM column mapped to `"metadata"` JSONB |
| `app/repositories/product_repo.py` | `update_product_metadata()` method added |
| `app/fastapi/schemas/product.py` | `product_metadata: dict` added to `LiveData` and `ProductOut`; `coerce_metadata` validator added |
| `app/fastapi/api/v1/products.py` | `get_product()` reads `product_metadata` explicitly; PATH A/B and background scrape all write metadata |
| `app/workers/scraper_worker.py` | `_write_result()` merges and writes `product_metadata` via `update_product_metadata()` |
| `alembic/versions/e8d4f84f775b_*.py` | Migration: adds `metadata` JSONB to `products` table |
| `streamlit_app/pages/product.py` | Metadata display section (description, features, specs, sizes, material/fit); price history chart fix |
| `streamlit_app/components/product_card.py` | Offer price (`special_price`) displayed on dashboard cards |

---

### Features

#### FEAT-001 — `metadata` JSONB Column on `products` Table
- **File:** `app/core/models/product.py`, `alembic/versions/e8d4f84f775b_*.py`
- **Change:** New nullable `metadata` JSONB column stores portal-specific
  enrichment data. ORM attribute named `product_metadata` (Python attribute)
  mapped to `"metadata"` (DB column name) to avoid conflict with SQLAlchemy's
  reserved `metadata` declarative attribute.
- **Schema:** unified keys across all portals —

  | Key | Portals | Description |
  |---|---|---|
  | `description` | All | Product description text |
  | `images` | All | Additional image URLs beyond `image_url` column |
  | `category` | All | Top-level category |
  | `subcategory` | All | Subcategory / article type |
  | `specs` | Flipkart, Amazon | Key-value spec dict |
  | `features` | Flipkart, Amazon | Bullet point highlights list |
  | `sizes_available` | Myntra | Available size labels |
  | `material` | Myntra | Fabric / material |
  | `fit` | Myntra | Fit type (Regular, Slim, etc.) |
  | `style_notes` | Myntra | Style description |

  Keys absent for a portal are simply missing — not null.

#### FEAT-002 — Flipkart API Full Field Extraction
- **File:** `app/scraper_v2/affiliate/flipkart.py`
- **Change:** `_parse()` now extracts all available fields from the Flipkart
  Affiliate API v1.0 response in addition to price/MRP/offers:
  - **`features`** — from `categorySpecificInfoV1.keySpecs` (flat list of
    highlight strings e.g. `"128 GB ROM"`, `"12 MP Camera"`)
  - **`specs`** — from `categorySpecificInfoV1.specificationList` (nested
    group → values → key/value structure, flattened to a plain dict)
  - **`category` / `subcategory`** — from `productBaseInfoV1.categoryPath`
    (breadcrumb string `"Electronics>Appliances>..."`, split on `">"`)
  - **`description`** — from `productBaseInfoV1.productDescription` with HTML
    tags stripped
  - **`images`** — all resolutions from `imageUrls` dict collected
- **Noise filter:** spec entries with blank keys or cancellation policy text
  are excluded from the specs dict.

#### FEAT-003 — `AffiliateResult.metadata` Field
- **File:** `app/scraper_v2/affiliate/result.py`
- **Change:** `metadata: dict = field(default_factory=dict)` added to
  `AffiliateResult`. Carries enrichment from any affiliate client through to
  `ScrapeResponse` and ultimately to the DB. Self-contained — no dependency
  on `scraper_v2.models`.

#### FEAT-004 — `ScrapeResponse.product_metadata` Field
- **File:** `app/scraper_v2/models/scrape_result.py`
- **Change:** `product_metadata: dict = field(default_factory=dict)` added to
  `ScrapeResponse`. Empty dict by default — no breaking change to existing
  callers. Populated by both the affiliate API path and the browser scraper path.

#### FEAT-005 — `ScraperEngine.merge_metadata()` Static Method
- **File:** `app/scraper_v2/engine.py`
- **Change:** `merge_metadata(existing, incoming)` merges incoming metadata
  into existing, with **existing keys winning on conflict**.
- **Rationale:** If yesterday's API call populated `specs` and today the API
  is down so the browser scraper runs without specs, the richer API data is
  preserved. Called by `scraper_worker._write_result()`, `products.py`
  background scrape, and both PATH A/B write paths.

#### FEAT-006 — Browser Scraper Metadata Extraction (All Portals)
- **File:** `app/scraper_v2/scrapers/generic_scraper.py`
- **Change:** `_extract_metadata(page, config)` dispatcher added, called on
  every successful scrape. Routes to portal-specific implementation:

  **Amazon — `_extract_metadata_amazon()`:**
  - `description` — `#productDescription`
  - `features` — `#feature-bullets ul li span.a-list-item`
  - `category/subcategory` — `#wayfinding-breadcrumbs_feature_div ul li a`
  - `specs` — `#productDetails_techSpec_section_1 tr` (two fallback table IDs)
  - `images` — `#altImages ul li img` thumbnails upgraded to `._SL500_.` large

  **Flipkart browser fallback — `_extract_metadata_flipkart()`:**
  - Same fields as API would have returned, extracted from DOM selectors
  - Used when affiliate API attempt 0 fails; targets same unified schema

  **Myntra — `_extract_metadata_myntra()`:**
  - **Approach A (preferred):** `page.evaluate()` extracts
    `window.__mweb_init_data__` or `window.__initial_state__` JS state object
    — structured, complete. `_parse_myntra_state()` handles multiple known
    state shapes across Myntra app versions.
  - **Approach B (DOM fallback):** CSS selectors for description, breadcrumb,
    size buttons, and spec name-value pairs. Fills gaps when JS state is unavailable.
  - Never raises — all exceptions caught and logged.

#### FEAT-007 — `ProductRepository.update_product_metadata()`
- **File:** `app/repositories/product_repo.py`
- **Change:** New method `update_product_metadata(product, metadata)` writes
  the already-merged dict to `product.product_metadata` and flushes.
  Merge logic stays in `ScraperEngine.merge_metadata()` — repository only persists.

#### FEAT-008 — Offer Price on Dashboard Cards
- **File:** `streamlit_app/components/product_card.py`
- **Change:** `special_price` (offer/bank deal price) now displayed below the
  main price on dashboard product cards when present and lower than
  `current_price`. Rendered in bold blue (`#2563EB`) to draw attention.
  Guarded by three conditions: `special_price` not None, `current_price` not
  None, `special_price < current_price`.

#### FEAT-009 — Metadata Display on Product Detail Page
- **File:** `streamlit_app/pages/product.py`
- **Change:** New metadata section between bank offers and price history chart.
  Reads `p.get("product_metadata") or {}`. Fully conditional — hidden when
  any key is absent:
  - **📄 Product Description** — collapsed `st.expander`
  - **✨ Key Features (N)** — expanded `st.expander`, bullet list
  - **Sizes Available** — inline chips rendered as bordered `div` elements
    in a column row (Myntra only)
  - **🔧 Specifications (N items)** — collapsed `st.expander` with
    `st.dataframe` (Specification / Value columns, `hide_index=True`)
  - **Material / Fit / Style** — `st.caption` line (Myntra only)

---

### Bug Fixes

#### FIX-001 — Price History Chart Date Axis Unordered
- **File:** `streamlit_app/pages/product.py`
- **Symptom:** Chart x-axis showed dates out of order — `1 Aug, 2 Aug,
  31 Jul, 30 Jul` — or missing dates (e.g. `Aug 01` swallowed by month
  boundary tick). Ambiguous labels like `Fri 24` with no month shown.
- **Root cause:** `st.line_chart` with `x="date"` (string-formatted column)
  treats dates as unordered categories. Streamlit/Altair auto-formats datetime
  ticks inconsistently at month boundaries.
- **Fix:** Switched to `st.altair_chart` with explicit `format="%d %b"` on
  the x-axis. `df.sort_values("checked_at")` ensures chronological order.
  `scale=alt.Scale(zero=False)` on y-axis makes price movements visible.
  Point markers and rich tooltips added.

#### FIX-002 — `get_product()` Not Returning `product_metadata`
- **File:** `app/fastapi/api/v1/products.py`
- **Symptom:** Metadata section never appeared on product detail page despite
  data being present in the DB.
- **Root cause:** `get_product()` built `ProductOut` by iterating
  `product.__table__.columns` and calling `getattr(product, c.name)`. The DB
  column is named `"metadata"` but the ORM attribute is `product_metadata`.
  `getattr(product, "metadata")` silently returned SQLAlchemy's internal
  declarative `metadata` object — not the JSONB data. `ProductOut` received
  no value for `product_metadata`.
- **Fix:** Skip `"metadata"` from the column loop; pass
  `product_metadata=product.product_metadata or {}` explicitly.

#### FIX-003 — Flipkart `categoryPath` Split on Wrong Separator
- **File:** `app/scraper_v2/affiliate/flipkart.py`
- **Symptom:** `category` stored as the full path string
  `"Electronics>Appliances>Kitchen Appliances>Dish washers"` instead of
  just `"Electronics"`.
- **Root cause:** Code split on `">>"` (double angle bracket). Real Flipkart
  API uses `">"` (single).
- **Fix:** Changed `category_path.split(">>")` to `category_path.split(">")`.

#### FIX-004 — Flipkart Specs and Features from Wrong Response Key
- **File:** `app/scraper_v2/affiliate/flipkart.py`
- **Symptom:** `specs` and `features` always empty for Flipkart products
  despite being present in the API response.
- **Root cause:** Code looked in `productBaseInfoV1.productAttributes` (only
  contains `size`, `color`, `storage` — basic variant attributes). Real specs
  are in `categorySpecificInfoV1.specificationList` (nested group/value
  structure) and features in `categorySpecificInfoV1.keySpecs` (flat list).
  Discovered by inspecting real Postman API response.
- **Fix:** Read from `categorySpecificInfoV1` block. Flatten
  `specificationList` group → values → key/value structure into a plain dict.
  Read `keySpecs` directly as the features list.

#### FIX-005 — Myntra Subcategory Showing "More By {Brand}"
- **File:** `app/scraper_v2/scrapers/generic_scraper.py`
- **Symptom:** `subcategory` populated with `"More By Levis"` — a related
  products section — instead of a real product category.
- **Root cause:** DOM breadcrumb selector matched a related-products link at
  the bottom of the page in addition to the actual breadcrumb.
- **Fix:** Added noise filter in DOM fallback: skip entries where text starts
  with `"more by"`, equals `"home"`, or is a single character. Only set
  `subcategory` when it is meaningfully different from `category`.

---

### Deviations from Design

#### DEV-001 — ORM Attribute Named `product_metadata` Not `metadata`
- **Original intent:** column and attribute both named `metadata`.
- **Actual:** ORM attribute is `product_metadata`; DB column is `metadata`
  via `mapped_column("metadata", JSONB, ...)`.
- **Reason:** SQLAlchemy's Declarative API reserves the `metadata` attribute
  name on all mapped classes — using it raises
  `InvalidRequestError: Attribute name 'metadata' is reserved`.

#### DEV-002 — Metadata Written at All Write Points, Not Just Cron
- **Original intent (discussion):** metadata written only by `scraper_worker`.
- **Actual:** also written in `products.py` PATH B new product create, PATH B
  existing product update, and background scrape (`_background_scrape_and_store`).
- **Reason:** Ensures metadata is populated on first preview for new products,
  not only after the first cron run. Merge strategy is consistent at all sites.

---

### Database Migration

| Migration | Revision | Description |
|---|---|---|
| `e8d4f84f775b_add_products_metadata.py` | `e8d4f84f775b` | Adds `metadata` JSONB column to `products` table |

Run: `python -m alembic upgrade head`

No data backfill required — column is nullable, defaults to `NULL`. Populated
on the next preview or cron run for each product. UI hides all metadata
sections when `product_metadata` is empty dict or None.

**Note:** The autogenerated migration also contained `op.drop_table('scrape_diagnostics')`
and related `alter_column` statements. The drop was removed manually before
running — caused by `scrape_diagnostics` ORM model not being visible to
Alembic at generation time. The `alter_column` statements (stripping column
comments from `mrp`, `special_price`, `discount_pct`, `offers`) were kept as
harmless.

---

### Files Modified

| File | Change |
|---|---|
| `app/scraper_v2/affiliate/result.py` | `metadata: dict` field added to `AffiliateResult` |
| `app/scraper_v2/affiliate/flipkart.py` | Full field extraction — description, images, category, subcategory, specs, features; category separator fix; noise filter |
| `app/scraper_v2/engine.py` | `product_metadata` passed through `_affiliate_result_to_scrape_response()`; `merge_metadata()` static method added |
| `app/scraper_v2/models/scrape_result.py` | `product_metadata: dict` added to `ScrapeResponse` |
| `app/scraper_v2/scrapers/generic_scraper.py` | `_extract_metadata()` dispatcher; `_extract_metadata_amazon()`, `_extract_metadata_flipkart()`, `_extract_metadata_myntra()`, `_parse_myntra_state()` added; Myntra subcategory noise filter |
| `app/core/models/product.py` | `product_metadata` ORM column mapped to `"metadata"` JSONB; `JSONB` import added |
| `app/repositories/product_repo.py` | `update_product_metadata()` method added |
| `app/fastapi/schemas/product.py` | `product_metadata: dict` added to `LiveData` and `ProductOut`; `coerce_metadata` validator added |
| `app/fastapi/api/v1/products.py` | `get_product()` explicit `product_metadata` read; metadata merge + write in PATH B new/existing and background scrape |
| `app/workers/scraper_worker.py` | `_write_result()` merges and writes `product_metadata` |
| `streamlit_app/pages/product.py` | Metadata section (description, features, specs, sizes, material/fit/style); price history chart switched to `st.altair_chart` with `format="%d %b"` axis |
| `streamlit_app/components/product_card.py` | `special_price` offer price display added to dashboard cards |
| `alembic/versions/e8d4f84f775b_add_products_metadata.py` | Migration file (manually edited to remove erroneous `drop_table scrape_diagnostics`) |

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Next phase |
| DEF-002 | `--reload` flag in local uvicorn wipes in-memory `PreviewCache` on file save | `app/services/preview_cache.py` | Replace with Redis |
| DEF-003 | `social_share` query param not stripped from Amazon canonical URLs | `app/services/url_validator.py` | Next phase |
| DEF-004 | UTM params not stripped from Myntra URLs | `app/services/url_validator.py` | Next phase |
| DEF-005 | Amazon PA-API stub — `AmazonAffiliateClient` excluded until credentials configured | `app/scraper_v2/affiliate/amazon.py` | When PA-API access received |
| DEF-006 | Amazon specs table selector misses some product types — specs empty for some Amazon products | `app/scraper_v2/scrapers/generic_scraper.py` — `_extract_metadata_amazon()` | Future phase |
| DEF-007 | Myntra JS state extraction not working for all products — sizes/specs empty when JS state unavailable | `app/scraper_v2/scrapers/generic_scraper.py` — `_extract_metadata_myntra()` | Future phase |
| DEF-008 | `product_metadata` not shown in price drop email | `app/notifications/email_sender.py` | Future phase |
| DEF-009 | `mrp`/`offers` enrichment not shown in price drop email | `app/notifications/email_sender.py` | Carried from v3.0 |
| DEF-010 | Adaptive layer ordering not yet active — needs 2+ months production data | `app/scraper_v2/scrapers/layer_selector.py` | Automatic |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| Strip dirty URL params | High | `social_share` from Amazon, UTM params from Myntra |
| Skip orphaned products in cron | Medium | Filter `get_all_for_scraping()` to products with ≥1 subscriber |
| Notification preferences | Medium | Per-subscription `notify_on_drop`/`notify_on_rise`/pause/threshold controls — full schema design already written |
| All-time low/high badges | Low | Visual badge when current price equals all-time low |
| Activate Amazon PA-API | When credentials arrive | Implement `_authenticate()` and `_fetch()` in `amazon.py` only |
| Show metadata in price drop email | Low | Pass `product_metadata` through `NotificationJob` to email template |
| Redis PreviewCache | Low | Replace in-memory dict — eliminates `--reload` restart issue |
| Myntra JS state extraction hardening | Low | Investigate correct state key for current Myntra app version |

---

*Archive this file to `docs/changelog/v3_1-product-metadata.md` when the next phase begins.*
