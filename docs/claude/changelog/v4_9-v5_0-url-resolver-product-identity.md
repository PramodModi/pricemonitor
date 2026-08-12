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

## [v5.0] — Product Identity Graph — August 2026

Adds cross-portal product identity: the ability to recognise that the same physical
product tracked on Amazon and on Flipkart is the same item. Introduces
`canonical_products` as a new additive table — `products` is NOT renamed, all
existing code, queries, and frontend calls are untouched.

Three new columns on `products`: `canonical_id` (FK), `model_number`, `normalized_name`.

**Scope:** `canonical_product.py`, `product.py`, `canonical_product_repo.py`,
`product_repo.py`, `product_identity.py`, `products.py`, Alembic migration.

---

### Summary Table

| Tag | Area | Description |
|---|---|---|
| FEAT-001 | Identity | `canonical_products` table — one row per real-world product |
| FEAT-002 | Identity | `ProductIdentityService` — normalize_name, extract_model_number, find_or_create_canonical |
| FEAT-003 | Identity | `extract_model_number_from_name()` — name-based fallback when Amazon returns specs=0 |
| FEAT-004 | Identity | Identity service wired into preview PATH B — runs after DB write, same transaction |
| FEAT-005 | DB | Three new columns on `products`: `canonical_id`, `model_number`, `normalized_name` |
| FEAT-006 | DB | `CanonicalProductRepository` — find_by_model_number, find_by_isbn, find_by_brand_and_name, create |
| FEAT-007 | DB | Four new `product_repo` methods: update_canonical_id, update_model_number, update_normalized_name, update_canonical_url |
| FIX-001 | DB | `product_repo.create()` handles concurrent duplicate inserts — catches IntegrityError, returns existing row |
| FIX-002 | Identity | `normalize_name()` step 2b threshold raised 25 → 60 chars to strip Flipkart accessory lists |
| FIX-003 | Identity | `extract_model_number()` rejects values < 4 chars and pure integers (e.g. "29" series numbers) |
| DEF-001 | Identity | Cron worker does not call identity service — canonical_id only set via preview PATH B |
| DEF-002 | Identity | `find_by_brand_and_name()` is Python-side similarity — slow at scale (> 1000 products) |
| DEF-003 | Identity | Amazon `model_number` on product row saved as None when extracted from name (not from specs) |
| DEF-004 | Identity | Cross-portal suggestion UI (Option B) not built yet |

---

### FEAT-001 — `canonical_products` table

**File:** `app/core/models/canonical_product.py` (new)

One row per real-world product, independent of portal. Multiple `products` rows
(portal listings) link to one `canonical_products` row via `canonical_id` FK.

**Fields:**
- `canonical_id` UUID PK
- `normalized_name` TEXT — product name with variant specs stripped (e.g. "Samsung Galaxy S24 5G")
- `brand` VARCHAR(255) — title-cased brand name
- `category` VARCHAR(50) — unified slug (mobiles/electronics/fashion/home/etc.)
- `image_url` TEXT — best available image across all portal listings
- `model_number` VARCHAR(255) — indexed, primary cross-portal key
- `isbn` VARCHAR(20) — books only
- `created_at`, `updated_at` TIMESTAMP WITH TIME ZONE

**Indexes:** `ix_canonical_products_model_number`, `ix_canonical_products_brand`

---

### FEAT-002 — ProductIdentityService

**File:** `app/services/product_identity.py` (new)
**Singleton:** `product_identity_service`

**`normalize_name(raw_name, brand, specs)`**

Strips variant specs and marketing noise from raw portal titles.

Steps:
1. Strip pipe suffix (`| AI Smartphone | ...`)
2. Strip parenthesized specs containing units (`(8GB RAM, 128GB)`, `(2000 W)`)
3. Strip parenthesized content ≤ 60 chars (`(Blue, 29)`, `(Fry Pan, Kadhai, Pressure Cooker)`)
4. Strip known color from specs dict
5. Normalize brand casing at start of name (SAMSUNG → Samsung)
6. Strip trailing noise words (smartphone, laptop, power bank, etc.)
7. Clean whitespace and trailing punctuation

Example:
```
"SAMSUNG Galaxy S24 5G (Cobalt Violet, 128 GB) (8 GB RAM) | AI Smartphone"
→ "Samsung Galaxy S24 5G"

"PHILIPS 2100 W Induction Cooktop Touch Panel(Fry Pan, Kadhai, Pressure Cooker, Sauce Pan, Tawa, , HD4928/01)"
→ "Philips 2100 W Induction Cooktop Touch Panel"
```

**`extract_model_number(specs)`**

Tries 9 spec keys in priority order:
`Model Number`, `Model`, `Model Name`, `Part Number`, `Manufacturer Part Number`,
`Item model number`, `Style Code`, `Style`, `SKU`.

Guards:
- Rejects placeholder values (`N/A`, `NA`, `None`, `NULL`, `-`)
- Rejects values shorter than 4 characters
- Rejects pure integers (series numbers like `"29"` for Prestige 29)
- Returns uppercased and stripped value

**`extract_isbn(specs)`**

Tries `ISBN-13`, `ISBN-10`, `ISBN`, `ASIN`. Validates 10 or 13 digit format.

**`find_or_create_canonical(db, platform, name, brand, category, image_url, specs)`**

Match priority:
1. `model_number` exact match (case-insensitive UPPER) — electronics/footwear
2. `isbn` exact match — books
3. Brand + `normalized_name` Jaccard similarity ≥ 0.85 — fuzzy fallback
4. Fashion category — always creates new canonical (no cross-portal matching)
5. No match → creates new `canonical_products` row

Never raises. Returns `None` when name and brand are both absent.

---

### FEAT-003 — `extract_model_number_from_name()` fallback

**File:** `app/services/product_identity.py`

Amazon browser scrapes frequently return `specs=0` — the specs tab is
JavaScript-rendered and not always captured. Flipkart affiliate API always
returns rich specs (28-32 fields). Without this fallback, cross-portal matching
fails for Amazon products even when the model number is visible in the title.

**Pattern matched:**
```
HD4928/01    — Philips codes (uppercase letters + digits + slash + digits)
SM-S921B     — Samsung codes (letters + hyphen + alphanumeric)
SMS6HMI00I   — Bosch codes (uppercase alphanumeric 8+ chars)
AH8050-002   — Nike style codes
```

**Noise blocklist:** `USB`, `LED`, `LCD`, `RAM`, `ROM`, `SSD`, `HDD`, `HDMI`,
`GPS`, `NFC`, `OTG`, `WiFi`, `ISI`, `BIS`, `MRP`, `EMI`, `GST` and others —
common product description abbreviations that match the model number pattern
but are not model numbers.

**Guards:**
- Minimum 4 characters
- Must contain at least one digit
- Not a pure integer
- Not in noise blocklist

**Verified cross-portal match:**

Bosch SMS6HMI00I dishwasher:
- Flipkart: `specs=32`, `model_number='SMS6HMI00I'` from specs → canonical created `9455ae7f`
- Amazon: `specs=0`, `model_number` extracted from title `"Bosch...SMS6HMI00I..."` → matched to `9455ae7f`

---

### FEAT-004 — Identity service wired into preview PATH B

**File:** `app/fastapi/api/v1/products.py`

Step 4b added between DB write and `db.commit()` in PATH B (new product and
existing product update). All identity writes happen in the same transaction as
the product write — committed together.

```
Step 1:  url_validator.validate()
Step 1b: url_resolver.resolve()         ← v4.9
Step 2:  DB lookup
Step 3:  Live scrape
Step 3b: best_canonical_url derivation  ← v4.9
Step 4:  DB write (create/update product)
Step 4b: ProductIdentityService         ← v5.0 NEW
         → find_or_create_canonical()
         → update_canonical_id()
         → update_model_number()
         → update_normalized_name()
Step 5:  db.commit()
Step 6:  Preview cache store
```

On any identity service error: warning logged, transaction continues unchanged.
Identity matching is non-critical — a failure never breaks the scrape or subscription.

---

### FEAT-005 — New columns on `products`

**File:** `app/core/models/product.py`

```python
canonical_id:    Optional[UUID]  FK → canonical_products (SET NULL on delete, indexed)
model_number:    Optional[str]   VARCHAR(255), indexed
normalized_name: Optional[str]   TEXT
```

All nullable. Existing rows have NULL — backfilled on next PATH B preview.
`canonical_id` index: `ix_products_canonical_id`
`model_number` index: `ix_products_model_number`

---

### FIX-001 — Concurrent duplicate insert no longer returns 500

**File:** `app/repositories/product_repo.py` — `create()` method

**Problem:** The frontend sends 2-3 rapid concurrent preview requests (React
useEffect double-invocation or impatient double-click). All three race to insert
the same `platform + marketplace_product_id`. First wins; remaining two crash
with `IntegrityError: duplicate key value violates unique constraint
"uq_products_platform_marketplace_id"` → HTTP 500.

**Fix:** `create()` wraps `flush()` in try/except `IntegrityError`. On catch:
session rolled back to a clean state, existing row fetched and returned. Callers
receive a valid product regardless of which request "won" the race.

```python
def create(self, **fields) -> Product:
    from sqlalchemy.exc import IntegrityError
    product = Product(**fields)
    self.db.add(product)
    try:
        self.db.flush()
        return product
    except IntegrityError:
        self.db.rollback()
        existing = self.get_by_platform_and_marketplace_id(
            fields["platform"], fields["marketplace_product_id"]
        )
        if existing:
            return existing
        raise
```

---

### FIX-002 — normalize_name step 2b threshold raised

**File:** `app/services/product_identity.py`

**Problem:** Flipkart product titles include accessory compatibility lists in
parentheses: `"(Fry Pan, Kadhai, Pressure Cooker, Sauce Pan, Tawa)"` — 52 chars.
The original 25-char threshold did not strip these, leaving noise in the
normalized name used for similarity matching.

**Fix:** Threshold raised from 25 → 60 chars.
- Catches: `(Blue, 29)`, `(Black)`, `(Fry Pan, Kadhai, Pressure Cooker, ...)`
- Preserves: genuine parenthetical descriptions > 60 chars

---

### FIX-003 — extract_model_number rejects short and integer-only values

**File:** `app/services/product_identity.py`

**Problem:** Prestige induction cooktop model spec key `"Model"` contained value
`"29"` (the product series number). This was extracted as `model_number='29'`
and stored as the cross-portal match key — too short and ambiguous to be useful.
Would incorrectly match any Prestige product with series number 29 across portals.

**Fix:** Two new guards added after placeholder rejection:
- Reject if `len(clean) < 4`
- Reject if `re.match(r'^\d+$', clean)` (pure integer — sizes, wattages, series numbers)

Real model numbers like `SM-S921B`, `HD4928/01`, `PIC16.0PLUS` pass both guards.

---

### Migration — `ced3bfc62de6_add_product_identity_graph.py`

`down_revision = '6db88644e1b0'` (v4.9 migration)

**upgrade():**
1. `CREATE TABLE canonical_products` with all fields + PK
2. `CREATE INDEX ix_canonical_products_model_number`
3. `CREATE INDEX ix_canonical_products_brand`
4. `ADD COLUMN products.canonical_id UUID NULLABLE`
5. `ADD COLUMN products.model_number VARCHAR(255) NULLABLE`
6. `ADD COLUMN products.normalized_name TEXT NULLABLE`
7. `CREATE INDEX ix_products_canonical_id`
8. `CREATE INDEX ix_products_model_number`
9. `CREATE FOREIGN KEY products_canonical_id_fkey → canonical_products(canonical_id) ON DELETE SET NULL`

**Note:** Autogenerate included erroneous `drop_table('scrape_diagnostics')` — removed manually before applying.

---

### Deferred

#### DEF-001 — Cron worker does not call identity service

**Impact:** Products scraped by the cron job don't get `canonical_id` set on
subsequent scrapes — only products going through preview PATH B get
identity-linked. In practice all products go through PATH B at first tracking,
so `canonical_id` is set at creation. Cron-only updates don't re-run identity.

**Fix (v5.1):** Add identity service call to `scraper_worker._write_result()`
when `product.canonical_id` is None after a successful scrape.

#### DEF-002 — `find_by_brand_and_name()` is Python-side similarity

**Impact:** At small catalog size (< 500 products) this is fast. At 5000+
products it becomes a full table scan on `canonical_products` filtered by brand.

**Fix (v5.1):** Replace with PostgreSQL `pg_trgm` trigram index query — same
migration that enables the search endpoint.

#### DEF-003 — Amazon `model_number` column saved as None when extracted from name

**Impact:** When `extract_model_number_from_name()` fires (Amazon specs=0),
the model number is used for the canonical match but not saved to
`products.model_number` — that column stays NULL. The canonical link is correct;
only the denormalised column on the listing is missing.

**Root cause:** In `products.py` Step 4b, `model_number` passed to
`update_model_number()` comes from `extract_model_number(specs)` which returned
None. The name-based fallback result is not bubbled back to the caller.

**Fix (v5.1):** After `find_or_create_canonical()` returns, if
`product.model_number` is None and `canonical.model_number` is set, write
`canonical.model_number` to the product row.

#### DEF-004 — Cross-portal suggestion UI (Option B) not built

**Design agreed:** After user subscribes to Amazon listing, if a Flipkart listing
exists for the same `canonical_id`, show suggestion card after subscription
confirmed: `"💡 Also on Flipkart — ₹XX,XXX (last checked Xh ago)"` with
`[Track on Flipkart too]` / `[No thanks]` buttons.

**Fix (v5.2):** Requires subscription endpoint to return `canonical_id` in
response, and frontend to call `GET /v1/products/cross-portal?canonical_id=...`
to find other listings.

---

### Files Modified

| File | Type | Change |
|---|---|---|
| `app/core/models/canonical_product.py` | New | CanonicalProduct ORM model |
| `app/core/models/product.py` | Modified | `canonical_id` FK + `model_number` + `normalized_name` + relationship |
| `app/core/models/__init__.py` | Modified | `CanonicalProduct` import added for Alembic |
| `app/repositories/canonical_product_repo.py` | New | find_by_model_number, find_by_isbn, find_by_brand_and_name, create, update_image |
| `app/repositories/product_repo.py` | Modified | update_canonical_url (v4.9) + update_canonical_id, update_model_number, update_normalized_name (v5.0) + FIX-001 in create() |
| `app/services/product_identity.py` | New | ProductIdentityService singleton |
| `app/fastapi/api/v1/products.py` | Modified | Step 4b identity service call |
| `alembic/versions/ced3bfc62de6_add_product_identity_graph.py` | New | Migration |

**Not changed:** `engine.py`, `generic_scraper.py`, `url_resolver.py`,
`scraper_worker.py`, `run_manager.py`, `url_validator.py`, `product_sync.py`,
`scrape_result.py`, all frontend files, all other API endpoints.

---

---

## [v4.9] — URL Resolver + Canonical URL — August 2026

Solves the core mobile short URL problem: users paste `amzn.in/d/XXXX`,
`dl.flipkart.com/s/XXXXX`, or `onelink.me/...` links from mobile apps and the
scraper fails because it receives an unresolved URL. Resolution now happens as a
mandatory first step before any scrape or DB lookup.

**Root cause:** `url_validator.validate()` returned the short URL unchanged for
`amzn.in` (no ASIN extractable). For `dl.flipkart.com/s/` it attempted HTTP
redirect resolution which always timed out on Railway (Firebase blocks Railway
IPs). The engine received the short URL, the affiliate API found no PID,
browser attempts followed the redirect internally (via `page.url`) but the
resolved URL was never saved — causing the cron to re-resolve every 4 hours.

**Scope:** `url_resolver.py`, `product.py`, `product_repo.py`, `products.py`,
`scraper_worker.py`, `run_manager.py`, Alembic migration.

---

### Summary Table

| Tag | Area | Description |
|---|---|---|
| FEAT-001 | Resolver | `URLResolver` — 3-step resolution per portal, module-level singleton |
| FEAT-002 | DB | `canonical_url` TEXT NULLABLE column on `products` |
| FEAT-003 | Resolver | `best_canonical_url` derived from scrape result when resolver falls through |
| FEAT-004 | Cron | `ScrapeJob.canonical_url` field — cron uses resolved URL |
| FIX-001 | Cron | DEF-001/DEF-002 resolved — short URL never re-resolved after first preview |
| FIX-002 | Affiliate | Flipkart affiliate API miss rate reduced — PID always in canonical URL |
| FIX-003 | Preview | PATH A now hits correctly for short URLs of known products |
| DEF-001 | Worker | `run_manager.py` one-liner update required (applied) |

---

### FEAT-001 — URLResolver

**File:** `app/services/url_resolver.py` (new)
**Singleton:** `url_resolver`

Runs after `url_validator.validate()` and before the DB lookup / `engine.scrape()`.
Never raises — falls back to original URL on any failure.

**Resolution strategies:**

| Portal | Step 1 | Step 2 | Step 3 |
|---|---|---|---|
| Amazon | Regex ASIN from URL path — `<1ms` | HTTP redirect follow (`amzn.in` → `amazon.in/dp/ASIN`) — `~200ms` | ScraperAPI redirect — paid fallback |
| Flipkart | Regex PID from `?pid=` query param — `<1ms` | ScraperAPI HTML fetch — Firebase Dynamic Links need JS render | — |
| Myntra | Regex catalog ID from URL path — `<1ms` | HTTP redirect follow (`onelink.me` → `myntra.com/...`) | ScraperAPI og:url extraction |

**`ResolvedURL` fields:**
- `portal` — amazon / flipkart / myntra
- `canonical_url` — clean desktop URL (or original on failure)
- `product_id` — ASIN / PID / catalog_id (None on failure)
- `method` — regex / http_redirect / scraperapi_redirect / scraperapi_html / og_url / passthrough
- `confidence` — 0.0–1.0 (logged, not enforced as a gate)

**Verified results:**
```
amzn.in/d/04sDSbjb        → method=http_redirect  asin=B0CS3GS3DP    ~1s
dl.flipkart.com/s/!9Fx2j  → method=passthrough    (no ScraperAPI locally)
                             browser page.url captures PID → best_canonical_url derived
www.myntra.com/...?utm=..  → method=regex          catalog_id=24624410 <1ms
```

---

### FEAT-002 — `canonical_url` column

**Files:** `app/core/models/product.py`,
`alembic/versions/6db88644e1b0_add_canonical_url_to_products.py`

```sql
ALTER TABLE products ADD COLUMN canonical_url TEXT;
```

Semantics:
- `url` = affiliated URL (for display + click-through, has `?tag=` or `affid=`)
- `canonical_url` = clean resolved URL (for scraping, no affiliate params)

Both written at PATH B (preview) time. NULL for products created before v4.9 —
backfilled on next preview or cron scrape.

---

### FEAT-003 — `best_canonical_url` derivation

**File:** `app/fastapi/api/v1/products.py` — Step 3b

When `url_resolver` returns `method=passthrough` (e.g. Flipkart short URL on
local dev without ScraperAPI key), the engine still resolves the URL internally
via `page.url` after browser redirect. The `marketplace_product_id` in the scrape
result is then used to build a clean canonical URL:

```python
if resolved.method == "passthrough" and marketplace_product_id:
    if platform == "amazon":
        best_canonical_url = f"https://www.amazon.in/dp/{marketplace_product_id}"
    elif platform == "flipkart":
        best_canonical_url = f"https://www.flipkart.com/product/p/itm?pid={marketplace_product_id}"
```

This ensures `canonical_url` saved to DB is never a short URL, even when the
resolver could not resolve before the scrape.

**Verified:** Flipkart short URL `dl.flipkart.com/s/!9Fx2j...` → `canonical_url`
saved as `flipkart.com/product/p/itm?pid=PWBHAVYSUUG64VSS` not the short URL.

---

### FEAT-004 — `ScrapeJob.canonical_url` + cron usage

**Files:** `app/workers/scraper_worker.py`, `app/scheduler/run_manager.py`

`ScrapeJob` gains `canonical_url: Optional[str] = None` field.

`_process_job_v2()` uses `job.canonical_url or job.url` as the URL passed to
`engine.scrape()` — prefers the clean resolved URL, falls back to `product.url`
for pre-v4.9 rows.

`run_manager.py` passes `canonical_url=product.canonical_url` when building
`ScrapeJob` — one line added to the product enumeration loop.

`_write_result()` backfills `canonical_url` for pre-v4.9 Amazon rows when
`product.canonical_url` is NULL and the scrape returns a `marketplace_product_id`:
`canonical_url = f"https://www.amazon.in/dp/{asin}"`

---

### FIX-001 — Short URL never re-resolved after first preview (DEF-001/DEF-002)

**Root cause:** `product.url` stored the short URL. Cron used it every 4 hours.
Engine ran the full resolution cascade (browser attempts, `page.url` capture,
affiliate retry) on every cron run.

**Fix:** `canonical_url` stored at preview time. Cron uses `canonical_url`.
Resolution runs once — at first preview — never again per product.

---

### FIX-002 — Flipkart affiliate miss rate on short URLs eliminated

**Root cause:** `FlipkartAffiliateClient.extract_product_id()` found no `?pid=`
in `dl.flipkart.com/s/` short URLs → `fetch()` returned None → affiliate API
skipped → engine fell through to browser cascade every time.

**Fix:** Resolver extracts PID before engine is called. `effective_canonical_url`
has `?pid=XXXX` in query string. Attempt 0 (affiliate API) hits immediately.
Flipkart products now return price + MRP + offers in ~400ms vs ~30s browser cascade.

---

### FIX-003 — PATH A now hits for short URLs of known products

**Root cause:** `url_validator.validate("amzn.in/d/XXXX")` returned
`marketplace_product_id=""`. DB lookup on empty string found nothing. PATH B
(full scrape) triggered even when product was already in catalog.

**Fix:** Resolver extracts ASIN from the `amzn.in` redirect. DB lookup uses the
real ASIN. PATH A hits correctly — instant return from DB.

---

### Migration — `6db88644e1b0_add_canonical_url_to_products.py`

`down_revision = '80656f837eea'` (v4.7 category migration)

```python
def upgrade():
    op.add_column('products', sa.Column('canonical_url', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('products', 'canonical_url')
```

Note: Autogenerate included erroneous `drop_table('scrape_diagnostics')` — removed manually.

---

### Files Modified

| File | Type | Change |
|---|---|---|
| `app/services/url_resolver.py` | New | URLResolver + ResolvedURL dataclass |
| `app/core/models/product.py` | Modified | `canonical_url` column + docstring |
| `app/repositories/product_repo.py` | Modified | `update_canonical_url()` added |
| `app/fastapi/api/v1/products.py` | Modified | Step 1b (resolver) + Step 3b (best_canonical_url) |
| `app/workers/scraper_worker.py` | Modified | `ScrapeJob.canonical_url` + backfill logic |
| `app/scheduler/run_manager.py` | Modified | `canonical_url=product.canonical_url` in ScrapeJob |
| `alembic/versions/6db88644e1b0_*.py` | New | Single column migration |

**Not changed:** `engine.py`, `generic_scraper.py`, `base.py`, `flipkart.py`,
`url_validator.py`, `product_sync.py`, `scrape_result.py`, all frontend files.

---

## Next Phase — v5.1 — Search

- Enable `pg_trgm` extension in Supabase
- Trigram + full-text index on `canonical_products.normalized_name`
- `GET /v1/search?q=samsung+galaxy+s24` endpoint returning canonical products with all portal listings
- Search box on Track page — accepts URL or product name
- Replace Python-side `find_by_brand_and_name()` with PostgreSQL trigram query (DEF-002 fix)
- Cron worker: call identity service when `product.canonical_id` is None (DEF-001 fix)
- Fix `products.model_number` backfill from canonical when extracted from name (DEF-003 fix)

---

---

# PricePing — Full Design Context, Roadmap & Deferred Items

This section captures all design decisions made during the v4.9–v5.0 session,
the complete planned roadmap, and everything explicitly deferred with reasoning.
It serves as the authoritative handoff document for future sessions.

---

## Problem Statement

Most PricePing users are on mobile. They open Amazon/Flipkart/Myntra, find a
product, and share the link. Mobile apps generate short URLs:

- Amazon: `amzn.in/d/XXXXXX`
- Flipkart: `dl.flipkart.com/s/XXXXX` (Firebase Dynamic Links)
- Myntra: `onelink.me/XXXX/YYYY` (AppsFlyer deep links)

These short URLs cannot be scraped directly — they are redirect wrappers, not
product pages. The previous scraper treated URL intake and scraping as one step,
making short URLs a persistent failure point.

**The reframe:** Stop thinking of this as a "scraper problem." The real problem is:

> Given an arbitrary product URL shared from a mobile app, reliably identify
> the product, merchant, and product ID — then obtain trustworthy price data.

---

## Core Architecture: Three Separated Layers

```
LAYER 1: URL Resolution        (what product is this?)
LAYER 2: Product Identity      (have we seen this before? same as another portal?)
LAYER 3: Price Extraction      (what is its current price?)
```

These three concerns were previously conflated inside the scraper engine.
The fix is to make each a distinct, independently-testable service.

---

## Key Design Decisions (Locked)

### Decision 1 — URL Resolver runs before everything else

`URLResolver` is a mandatory step between `url_validator.validate()` and the
DB lookup. It produces `canonical_url + product_id` before any engine or affiliate
API is touched. On failure it returns a passthrough — the engine runs unchanged.
This is purely additive; resolution failure changes nothing vs. the old behaviour.

### Decision 2 — Scraper cascade order unchanged for all portals

```
Attempt 0:  Affiliate API     ← free, instant
Attempt 1:  Browser Chromium  ← free
Attempt 2:  Browser new ctx   ← free
Attempt 3:  Browser Firefox   ← free
Attempt 4:  Google/Bing Cache ← free
Attempt 5:  ScraperAPI        ← paid, last resort
```

Amazon was considered for special-casing (skip browser — Railway IPs always
blocked). **Decision: do not special-case Amazon.** The extra 30-40 seconds of
browser attempts is acceptable for now. ScraperAPI stays last for all portals.
Amazon PA-API (free, instant) is the correct long-term fix but requires
credentials not yet available.

### Decision 3 — Product Identity Graph is additive only

`canonical_products` added as a new table. `products` table is NOT renamed to
`portal_listings`. All existing code unchanged. This avoids a high-risk rename
migration across 15+ files while still delivering cross-portal identity.

The rename can happen in a future version when there is a clear product reason.

### Decision 4 — Cross-portal matching identifiers (priority order)

```
1. Model number from specs  ← exact, electronics/footwear ~90%
2. ISBN                     ← exact, books 100%
3. Brand + name similarity  ← Jaccard ≥ 0.85, fallback
4. Fashion category         ← skip matching entirely (too noisy)
```

Fashion products have no model numbers. Name similarity is unreliable because
colour/size variants have near-identical names but are different products.
Each fashion listing always gets its own canonical product.

### Decision 5 — Cross-portal suggestion: Option B (post-subscribe)

When a user pastes an Amazon URL for a product already in DB from Flipkart:

**Step 1:** Show the Amazon product. User clicks Track → subscribed to Amazon.
**Step 2:** After subscription confirmed, show suggestion card:
`"💡 Also on Flipkart — ₹XX,XXX (last checked Xh ago)"`
with `[Track on Flipkart too]` / `[No thanks]` buttons.

**Rationale:**
- Respects user's original intent (they chose Amazon)
- Post-commitment upsell feels helpful, not distracting
- Mobile UX: sequential flow works better than side-by-side comparison
- Always shows "last checked X ago" — never claims price is current
- User decides independently — no forced bundling

**Not built (v5.2):** Requires subscription endpoint to return `canonical_id`,
and frontend to query other portal listings for the same canonical.

### Decision 6 — Name-based search uses PostgreSQL, not external service

No Elasticsearch, no Algolia, no external search API. PostgreSQL already
installed (Supabase) and has:
- `pg_trgm` — trigram similarity for fuzzy/typo-tolerant matching
- `tsvector` — full-text search for keyword matching

Both used together: trigram catches typos, full-text catches word order variations.
Python-side Jaccard similarity (current) is a temporary placeholder until v5.1
adds the trigram index.

### Decision 7 — Scrape failure fallback: ask user for product name

When the scraper fails for a URL, instead of showing an error, recover:

```
"We couldn't load this product automatically."
"What are you looking for?"
[ Product name input ]  [ Platform: Amazon / Flipkart / Myntra ]
[ Search ]
```

- **Flipkart selected** → Flipkart Affiliate Search API (structured, free)
- **Amazon/Myntra selected** → Google Custom Search API (`site:amazon.in {name}`)

Google Custom Search API chosen over Tavily (built for content extraction) and
SerpAPI (expensive) because PricePing only needs the product URL from search
results, not page content. Free tier: 100 queries/day.

**Not built (v5.2).**

### Decision 8 — `scraper_v2` remains loosely coupled

`ScraperEngine` is the single public surface. No tight dependencies on other
application layers. Planned for eventual extraction as a standalone FastAPI
microservice. The URL resolver and identity service are caller-side concerns
(in `products.py`) — the engine never imports them.

---

## Complete Planned Roadmap

### v4.9 — URL Resolver + Canonical URL ✅ COMPLETE

**Problem solved:** Mobile short URLs (`amzn.in`, `dl.flipkart.com/s/`, `onelink.me`)
fail because the engine receives an unresolvable URL. Resolved URLs never saved
to DB — cron re-resolves every 4 hours.

**Delivered:**
- `URLResolver` with 3-step resolution per portal
- `canonical_url` column on `products`
- Cron uses `canonical_url` — DEF-001/002 from v4.8 fixed
- Flipkart affiliate API now gets real PID on attempt 0

**Files:** `url_resolver.py` (new), `product.py`, `product_repo.py`,
`products.py`, `scraper_worker.py`, `run_manager.py`, migration `6db88644e1b0`

---

### v5.0 — Product Identity Graph ✅ COMPLETE

**Problem solved:** Same product tracked by two users via different URLs creates
duplicate rows. No cross-portal price comparison possible.

**Delivered:**
- `canonical_products` table
- `canonical_id`, `model_number`, `normalized_name` on `products`
- `ProductIdentityService` with normalize_name, extract_model_number,
  extract_model_number_from_name, find_or_create_canonical
- Identity wired into preview PATH B
- Cross-portal match verified: Bosch SMS6HMI00I on Amazon matched to Flipkart
  using model number extracted from title (specs=0 on Amazon)

**Files:** `canonical_product.py` (new), `canonical_product_repo.py` (new),
`product_identity.py` (new), `product.py`, `product_repo.py`, `products.py`,
migration `ced3bfc62de6`

---

### v5.1 — Search ⏳ NEXT

**Problem solved:** Users can only track by URL. Name-based search not possible.
Python-side similarity slow at scale.

**Planned deliverables:**

**Backend:**
- Enable `pg_trgm` extension in Supabase (`CREATE EXTENSION pg_trgm`)
- Trigram index: `CREATE INDEX ... USING gin (normalized_name gin_trgm_ops)` on `canonical_products`
- Full-text index: `CREATE INDEX ... USING gin (to_tsvector('english', normalized_name))`
- `GET /v1/search?q=samsung+galaxy+s24&limit=20` endpoint
  - Returns `canonical_products` with all portal `listings` attached
  - Each listing has `platform`, `current_price`, `url`, `availability`
  - Response includes `best_price` and `best_platform`
  - Combined trigram + FTS scoring: `trgm_score * 0.6 + fts_score * 0.4`
- Replace `find_by_brand_and_name()` Python-side with PostgreSQL trigram query

**DEF fixes included:**
- DEF-001: Cron worker calls identity service when `product.canonical_id` is None
- DEF-002: `find_by_brand_and_name()` replaced by `pg_trgm`
- DEF-003: `products.model_number` backfilled from `canonical.model_number` when
  extracted from name

**Frontend:**
- Search box on Track page — accepts URL or product name
- Auto-detect input: if URL → existing flow; if text → `GET /v1/search`
- Search results list: canonical product cards with all portal prices
- User picks exact variant + portal → existing subscribe flow

**Search result shape:**
```json
{
  "query": "samsung galaxy s24",
  "results": [
    {
      "canonical_id": "uuid",
      "name": "Samsung Galaxy S24 5G",
      "brand": "Samsung",
      "category": "mobiles",
      "image_url": "...",
      "listings": [
        { "platform": "amazon",   "current_price": 74999, "url": "..." },
        { "platform": "flipkart", "current_price": 72999, "url": "..." }
      ],
      "best_price": 72999,
      "best_platform": "flipkart"
    }
  ]
}
```

---

### v5.2 — Scrape Failure Fallback + Cross-Portal Suggestion ⏳ PLANNED

**Problem solved:** When scrape fails, user sees error and gives up. Users who
paste a URL for a product already tracked on another portal don't know about
the better price.

**Planned deliverables:**

**Scrape failure recovery:**
- New endpoint: `POST /v1/products/search-by-name`
  - Body: `{ "name": "Samsung Galaxy S24", "platform": "flipkart" }`
  - Flipkart → Flipkart Affiliate Search API (`/1.0/json/search?q=...`)
  - Amazon/Myntra → Google Custom Search API (`site:amazon.in {name}`)
  - Returns list of product candidates with name, price, image, URL
- Frontend recovery UI on Track page:
  ```
  ⚠️ We couldn't load this product automatically.
  Tell us what you're looking for:
  [ Product name input ]
  Where do you want to track it?
  ● Amazon  ○ Flipkart  ○ Myntra
  [ Search ]
  ```
- Results list: user picks exact variant, existing subscribe flow

**Flipkart Affiliate Search:**
- New `search_by_name(query, limit)` method on `FlipkartAffiliateClient`
- Uses `/affiliate/1.0/json/search?q={query}&type=json`
- Returns up to 5 results ranked by relevance
- Confidence scoring: brand match (0.40) + token overlap (0.50)

**Google Custom Search (Amazon/Myntra fallback):**
- New `app/services/web_search.py` wrapping Google Custom Search API
- `site:amazon.in {name}` returns product URL directly
- URL passed to `URLResolver` → ASIN extracted → existing scrape flow
- Free tier: 100 queries/day (sufficient for failure-only use case)
- API key: `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID` env vars

**Cross-portal suggestion (Option B):**
- After subscription confirmed, backend checks:
  `SELECT * FROM products WHERE canonical_id = :canonical_id AND platform != :subscribed_platform`
- If other portal listings exist → return them in subscription response
- Frontend shows suggestion card after subscription success:
  ```
  ✓ Tracking on Amazon
  💡 Also on Flipkart — ₹72,999 (last checked 3h ago)
  [Track on Flipkart too]    [No thanks]
  ```
- Always shows "last checked X ago" — never claims price is current
- User decides independently — no forced bundling

**API change:**
- `POST /v1/subscriptions` response gains `cross_portal_listings: []` field
  (additive, `Optional`, Streamlit-safe)

---

### Phase 3 — Future (not scheduled)

These items were discussed and agreed to defer. Not on the near-term roadmap.

| Item | Why Deferred |
|---|---|
| Amazon PA-API | No credentials. When available: implement `AmazonAffiliateClient._fetch()`. Eliminates ScraperAPI for ~95% of Amazon products. |
| Amazon browser skip optimisation | 30-40s browser attempts before ScraperAPI is acceptable. Only worth fixing after PA-API is wired. |
| "Best price across portals" subscription | User subscribes to a canonical product — pinged when any portal drops below target. Phase 3 UX change. |
| Image perceptual hash cross-portal matching | Computationally expensive. Model number covers ~90% of electronics — not needed now. |
| Fashion cross-portal linking | Too many variants (colour, size). Name similarity produces false positives. Deferred indefinitely. |
| Mobile share sheet / native app | Would allow iOS/Android Share → PricePing directly. Big infrastructure change. Phase 3. |
| Cross-portal Product Identity rename (`portal_listings`) | Rename `products` table. High code change surface. No clear product need yet. |
| Tavily web search | Considered for scrape failure fallback. Google CSE chosen instead — only need URL, not content. |
| Notification preferences system | 6 new `subscriptions` columns + 1 `users` column. Designed in v4.8, not implemented. Still pending. |
| Top Deals / Most Watched sections | Phase 2 frontend features. Slots exist on landing page. Data model supports it. |
| Cross-portal product search UI | Full comparison page. Enabled by v5.1 search endpoint. Phase 3 frontend. |

---

## Infrastructure & Configuration Reference

| Component | Details |
|---|---|
| Backend | FastAPI on Railway (Hobby, $5/month) |
| DB | PostgreSQL on Supabase |
| Frontend | Next.js 15 on Vercel at `www.priceping.in` |
| Legacy UI | Streamlit on Streamlit Community Cloud (must not be broken) |
| Scraper image | `mcr.microsoft.com/playwright/python:v1.44.0-jammy` |
| Cron | GitHub Actions every 4 hours |
| Email | SendGrid from `pings@priceping.in` |
| Proxy | ScraperAPI (residential, `premium=true` for Myntra) |
| Affiliate | Flipkart Affiliate API (active) · Amazon PA-API (pending credentials) |
| Monitoring | Railway logs + scrape_diagnostics table |

**Key env vars needed for v5.2:**
- `GOOGLE_CSE_API_KEY` — Google Custom Search API key
- `GOOGLE_CSE_ID` — Custom Search Engine ID (configured for `amazon.in` + `myntra.com`)

---

## Invariants — Never Break These

1. **`scraper_v2` loosely coupled** — engine never imports from `app/fastapi/` or `app/services/`. URL resolution and identity are caller-side concerns.
2. **`db.flush()` not `db.commit()`** — caller owns the transaction.
3. **f-string logging only** — `logging.Logger` does not accept keyword arguments (DEV-006).
4. **`metadata` is reserved in SQLAlchemy** — ORM attribute must be named `product_metadata` mapped to `"metadata"` DB column.
5. **Additive-only schema changes** — new Pydantic fields must be `Optional` with `None` defaults (Streamlit backward compat).
6. **Railway IPs blocked by Amazon** — browser attempts on Railway always hit CAPTCHA. ScraperAPI or PA-API required for reliable Amazon scraping in production.
7. **Firefox for Myntra** — Chromium blocked by Myntra's TLS fingerprinting. Firefox contexts must never override user agent.
8. **Alembic autogenerate always hallucinates `drop_table('scrape_diagnostics')`** — always remove manually before applying migration.
9. **Affiliate params re-appended by `_build_affiliated_url()`** — `url_resolver` strips them; `product_sync.py` re-adds them. Never store affiliate params in `canonical_url`.
10. **`product_identity_service` never raises** — identity matching is non-critical. Failure logs a warning and the request continues unchanged.
