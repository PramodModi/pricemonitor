# PricePing Changelog — v5.3

---

## [v5.3] — Search UX, Image Extraction, Live Store Search, Platform Radio Buttons

### Summary
Major Track page UX overhaul. Platform radio buttons for name search. Live store search section with per-platform buttons. Product image extraction from Tavily results using og:image / JSON-LD. Hybrid FTS + category-aware re-ranking for DB search. Flipkart Affiliate API endpoint fixed. Query-title similarity validation to skip irrelevant DB results. Landing page dual-mode input. Shared search scoring utilities.

---

## Backend

### FEAT-001 — Hybrid FTS + category-aware search (`canonical_product_repo.py`)
- `search()` method rewritten — three-pass strategy:
  - **Pass 1 (FTS primary):** `fts @@ websearch_to_tsquery('english', :query)` — uses pre-built tsvector GIN index
  - **Pass 2 (trgm fallback):** `similarity > 0.15` — only when FTS returns 0 results (handles typos, model numbers)
  - **Pass 3 (Python re-ranking):** `+0.25` category boost when query intent matches result category
- `fts` column added to `canonical_products` in Supabase SQL editor (generated stored tsvector column):
  ```sql
  ALTER TABLE canonical_products ADD COLUMN fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(normalized_name,'') || ' ' || coalesce(brand,'') || ' ' || coalesce(model_number,''))
  ) STORED;
  CREATE INDEX ix_canonical_products_fts ON canonical_products USING GIN (fts);
  ```
- Imports `_RULES` from `category_mapper.py` — future keyword additions automatically improve search
- `_extract_query_category()` module-level helper — longest-match-first to avoid short-circuit

### FEAT-002 — `category_mapper.py` — `appliances` and `footwear` split
- `VALID_CATEGORIES` updated — added `appliances`, `footwear`
- Electronics block split: `refrigerator`, `washing machine`, `microwave`, `mixer`, `grinder`, `dishwasher`, `cooler`, `fan`, `iron`, `vacuum`, `induction`, `oven`, `kettle` etc. → `appliances`
- Fashion block split: `footwear`, `shoes`, `sandal`, `sneaker`, `boot`, `chappal`, `slipper`, `heel` → `footwear`
- Scraper pipeline unaffected — `home`, `beauty`, `sports`, `toys` categories preserved

### FEAT-003 — `search_scorer.py` — shared scoring utility (`app/utils/search_scorer.py`)
- New file — single source of truth for search candidate ranking
- `score_candidate(candidate, query)` — three signals: model number (+0.5), brand match (+0.2), token overlap (0–0.3)
- `rank_candidates(candidates, query, limit)` — scores, sorts, strips internal key, trims to limit
- `query_title_similarity(query, title)` — token overlap between query and result title. Returns 0.0–1.0. Used for retry decisions and DB result validation
- Imported by `flipkart.py`, `web_search.py`

### FEAT-004 — `flipkart.py` — Affiliate API fixes + re-ranking
- **Endpoint fix:** `/1.0/json/search` → `/1.0/search.json`
- **Query param fix:** `q=` → `query=`, added `resultCount=10`
- **URL encoding fix:** `requests` uses `+` for spaces; Flipkart API requires `%20`. Built URL manually with `urllib.parse.quote()`
- **Special character cleaning:** strips `()[]|/` from query before sending — prevents HTTP 400
- **Re-ranking:** parses 20 raw results, scores via `search_scorer.rank_candidates()`, returns top `limit`
- **Price fix:** uses `flipkartSpecialPrice` (discounted) over `flipkartSellingPrice` (MRP) when available
- **Debug logging:** logs clean_query, full request URL, ranked top-3

### FEAT-005 — `web_search.py` — Tavily image extraction + retry logic
- Fetches up to 10 raw results, re-ranks via `search_scorer`
- **Retry logic (up to 3 attempts):**
  - Attempt 1: `max_results=10`, Attempt 2: `max_results=15`, Attempt 3: `max_results=20`
  - Retry when: `query_title_similarity(query, top_title) < 0.7` OR `domain_count < limit`
  - Keeps best response across all attempts (highest similarity)
- **Query truncation:** first 8 words only — long queries cause Tavily to return off-domain results
- **Myntra query suffix:** appends `" buy"` to prefer product pages over category listing pages
- **Domain filter:** post-fetch filter `site in r.url` — Tavily `include_domains` not always strict
- **Image extraction:** uses Tavily top-level `response["images"]` array — aggregated best images
  - Platform domain whitelist: `assets.myntassets.com`, `m.media-amazon.com`, `rukminim` — filters out brand CDNs, sprites, tracking pixels
  - Positional assignment to ranked candidates
  - Per-result image fallback for Amazon (`m.media-amazon.com/images/I/` pattern)
- **Removed:** `og:image` page fetching for Amazon (blocked by bot detection)

### FEAT-006 — `image_extractor.py` — og:image / JSON-LD extraction (`app/utils/image_extractor.py`)
- New file — extracts product image from a product page URL
- Signals: `og:image` meta tag → JSON-LD `Product.image` → None
- `extract_product_images_parallel(urls, max_workers=3)` — parallel fetch with 3s timeout
- Used by `web_search.py` for Myntra og:image fallback when platform images unavailable
- Never raises — returns None on any error

### FEAT-007 — `search_by_name.py` — image passthrough + URL filter fixes
- **Image passthrough:** `r.image_url` from `web_search` now flows to `ProductCandidate.image_url` for all platforms
- **Myntra URL filter loosened:** accepts all `myntra.com` URLs except homepage and `myntra-fashion-store` pages
- **Dual Tavily search:** full name query + model number query, results merged and deduped by URL, re-ranked
- **Debug logging:** `filter=PASS/FAIL` per URL (removable after confirmed working)

### DEF-003 — Flipkart Affiliate `product_id` vs DB UUID
- Flipkart Affiliate returns PIDs like `WMNGPYWTEFA3VFHF` as `product_id`
- These are not DB UUIDs — direct subscribe fails with 422
- Fix is in frontend `SearchResultsCard.jsx` via `isDbUuid()` check (see Frontend section)

---

## Frontend

### FEAT-008 — `UrlInputForm.jsx` — platform radio buttons
- Added `PLATFORMS` constant: `all`, `amazon`, `flipkart`, `myntra`
- `selectedPlatform` state — defaults to `'all'`
- Radio group shown only in name-search mode (hidden when URL detected)
- Platform resets to `'all'` when input switches to URL mode
- `onSubmitSearch(query, platform)` — platform passed to parent
- Added `initialQuery` prop — pre-fills from `?q=` URL param (landing page navigation)
- Auto-triggers on mount when `initialUrl` or `initialQuery` provided

### FEAT-009 — `TrackPageClient.jsx` — platform-aware search + DB similarity check
- `onSubmitSearch(q, platform)` — platform-aware routing
- DB results filtered client-side by platform when specific platform selected
- **DB similarity check (v5.3):** `queryTitleSimilarity(query, topTitle) < 0.6` → skip DB results, fall back to live search
- `?q=` param read on mount → `initialQuery` passed to `UrlInputForm`
- `LoadingBeacon` extracted as separate component with 15s delayed message: "Taking longer than expected — almost there, hang tight…"
- `search_results` step uses `max-w-5xl` container (was `max-w-xl`)

### FEAT-010 — `SearchResultsCard.jsx` — live store search + grid layout + image placeholders
- **Grid layout:** `grid-cols-2 sm:grid-cols-3 lg:grid-cols-4` — was single column
- **Flattened cards:** `flattenResults()` — one `ListingCard` per listing, vertical layout
- **"Not what you wanted?" banner:** full-width indigo button below header, always visible
- **Live store search section:** prominent indigo box below DB results
  - Three platform buttons: Amazon India, Flipkart, Myntra
  - Button states: default → loading (spinner) → done (✅ green, disabled)
  - Results append below buttons in same grid — no navigation
  - Searches fire `POST /v1/products/search-by-name` per platform
- **`isDbUuid()` check:** Flipkart PIDs fail UUID regex → routed to preview flow, not direct subscribe
- **Button labels:** `"🔔 Monitor this"` for DB products, `"🔍 Get live details"` for non-DB/Tavily
- **Platform logo placeholders:** `/logos/amazon.svg`, `/logos/flipkart.svg`, `/logos/myntra.png` shown when `image_url` is null. `onError` swaps broken product images to platform logo
- **`PLATFORM_PLACEHOLDERS`** constant — local `/public/logos/` paths (no external CDN calls)

### FEAT-011 — `HeroSection.jsx` — dual-mode input
- Input accepts URL or product name (was URL-only)
- Button label changes: URL mode → "Track price →", name mode → "🔍 Search"
- On submit: URL → `/track?url=...`, name → `/track?q=...`
- Subheadline updated to mention name search

### FEAT-012 — `searchUtils.js` — shared frontend search utility (`src/lib/searchUtils.js`)
- New file — JavaScript equivalent of `app/utils/search_scorer.py`
- `queryTitleSimilarity(query, title)` — token overlap, stopword filtering, portal prefix stripping
- Imported by `TrackPageClient.jsx`
- Backend equivalent noted in docstring for easy sync

---

## Infrastructure

### CFG-001 — `requirements.txt`
- Added: `beautifulsoup4==4.15.0`, `lxml==6.1.1`, `tavily-python`

### CFG-002 — Supabase RLS
- `notification_log` table: RLS enabled, service role policy added

### CFG-003 — Static assets
- `public/logos/amazon.svg`, `public/logos/flipkart.svg`, `public/logos/myntra.png` — downloaded locally, no external CDN dependency

### CFG-004 — `TAVILY_API_KEY` env var
- Added to Railway environment variables

---

## Files Modified

| File | Type | Change |
|------|------|--------|
| `app/repositories/canonical_product_repo.py` | Backend | FTS primary search, category re-ranking |
| `app/scraper_v2/scrapers/category_mapper.py` | Backend | appliances + footwear category split |
| `app/utils/search_scorer.py` | Backend | New — shared scoring + query_title_similarity |
| `app/utils/image_extractor.py` | Backend | New — og:image / JSON-LD extraction |
| `app/scraper_v2/affiliate/flipkart.py` | Backend | Endpoint fix, URL encoding, re-ranking, price fix |
| `app/services/web_search.py` | Backend | Retry logic, image extraction, domain filter, query truncation |
| `app/fastapi/api/v1/search_by_name.py` | Backend | Image passthrough, URL filter fixes, dual Tavily search |
| `src/components/track/UrlInputForm.jsx` | Frontend | Platform radio buttons, initialQuery prop |
| `src/components/track/TrackPageClient.jsx` | Frontend | Platform search, DB similarity check, LoadingBeacon |
| `src/components/track/SearchResultsCard.jsx` | Frontend | Grid layout, live search section, isDbUuid, platform logos |
| `src/components/sections/HeroSection.jsx` | Frontend | Dual-mode input, ?q= navigation |
| `src/lib/searchUtils.js` | Frontend | New — queryTitleSimilarity utility |
| `requirements.txt` | Config | beautifulsoup4, lxml, tavily-python |
| `public/logos/amazon.svg` | Asset | New — Amazon logo placeholder |
| `public/logos/flipkart.svg` | Asset | New — Flipkart logo placeholder |
| `public/logos/myntra.png` | Asset | New — Myntra logo placeholder |

---

## Deferred / Known Issues

| ID | Description |
|----|-------------|
| DEF-001 | Save resolved canonical URL + affiliate PID back to `products` table (cron repeats full cascade for Flipkart short URLs) |
| DEF-002 | "Samsung TV" returns Samsung phones — trgm category disambiguation within brand. Category boost (v5.3) partially mitigates but doesn't fully solve |
| DEF-004 | Amazon live search images unreliable — page fetch blocked by bot detection. Platform logo shown as fallback |
| DEF-005 | Tavily image-to-result positional mismatch — top-level images are aggregated across all results, not per-result. Filename matching partially helps for Myntra |

---

## Next Phase Candidates

- Auth endpoints + login page (high priority)
- Notification preferences system (6 new `subscriptions` columns designed)
- `/search` standalone page — DB-only name search with direct subscribe
- Top Deals section, Most Watched Products grid
- `scraper_v3` — API-exposed standalone service
- DEF-001 fix — save canonical URL + PID to `products` table
