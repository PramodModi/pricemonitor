# PricePing Changelog — v5.1 + v5.2

---

## [v5.1] — Search Endpoint + pg_trgm

### Summary
Added PostgreSQL trigram + full-text search on `canonical_products`. Backfilled all 136 existing products with canonical identity. Added `GET /v1/search` endpoint.

### Backend

#### FEAT-001 — pg_trgm indexes
- **Migration:** `72005865ef60_add_search_indexes.py`
- **Indexes added:**
  - `ix_canonical_products_normalized_name_trgm` — GIN trigram on `canonical_products.normalized_name`
  - `ix_canonical_products_normalized_name_fts` — GIN tsvector on `canonical_products.normalized_name`
  - `ix_canonical_products_brand_trgm` — GIN trigram on `canonical_products.brand`
  - `ix_products_normalized_name_trgm` — GIN trigram on `products.normalized_name`
- **Note:** `pg_trgm` extension enabled in Supabase SQL editor before migration

#### FEAT-002 — `find_by_brand_and_name()` replaced with pg_trgm
- **File:** `app/repositories/canonical_product_repo.py`
- **Change:** Python-side Jaccard loop replaced with single `text()` SQL using `similarity()`
- **Threshold:** 0.85 (unchanged)

#### FEAT-003 — `search()` method — two-pass strategy
- **File:** `app/repositories/canonical_product_repo.py`
- **Pass 1 (strict):** `similarity > 0.22` — trgm-only filtering
  - Verified: Samsung Galaxy S25 (0.296) passes, Apple iPhone (0.172) filtered for "samsung phone"
- **Pass 2 (fallback):** `similarity > 0.10` — only when Pass 1 returns 0
- **Scoring:** `trgm_score * 0.6 + fts_score * 0.4` — FTS for scoring only, NOT filtering
- **Known DEF-002:** "Samsung TV" returns Samsung phones — trgm can't distinguish categories within brand. Fix deferred.

#### FEAT-004 — `GET /v1/search` endpoint
- **File:** `app/fastapi/api/v1/search.py`
- **Route:** `GET /v1/search?q=samsung+galaxy+s24&limit=20`
- **Response:** `{ query, count, results: [{ canonical_id, name, brand, category, image_url, model_number, best_price, best_platform, listings: [{product_id, platform, current_price, mrp, special_price, url, availability, last_checked_at}] }] }`
- **Two-query approach:** search canonicals → batch fetch listings (no N+1)
- **Wired in:** `app/fastapi/main.py`

#### FEAT-005 — DEF-001 fix: cron identity service
- **File:** `app/workers/scraper_worker.py`
- **Change:** `_write_result()` calls `ProductIdentityService` when `canonical_id is None`
- **model_number backfill:** from `canonical.model_number` when listing extraction returned `None`

#### FEAT-006 — Backfill script
- **File:** `backfill_identity.py` (project root)
- **Result:** 136 products linked, 0 skipped, 0 failed
- **Note:** No network calls — uses existing DB data only. Safe to re-run.

#### FIX-001 — `model_number` backfill in products.py
- **File:** `app/fastapi/api/v1/products.py`
- After identity service, if `extract_model_number(specs)` returns `None`, backfill from `canonical.model_number`

---

## [v5.2] — Scrape Failure Fallback + Cross-Portal Suggestion

### Summary
Scrape failure recovery UI. Cross-portal Option B suggestion after subscription. Tavily search integration. URL validator for fast-fail on invalid product IDs.

### Backend

#### FEAT-001 — `web_search.py` — Tavily Search API wrapper
- **File:** `app/services/web_search.py`
- **API:** Tavily (https://tavily.com) — 1,000 free queries/month
- **Config:** `TAVILY_API_KEY=tvly-...` in `.env` + `app/core/config.py`
- **Note:** Google Custom Search API not available for new GCP projects after Jan 20, 2026
- **Platforms:** `amazon.in`, `flipkart.com`, `myntra.com`
- **`include_images=True`:** Tavily returns source images (quality varies)
- **Never raises:** returns empty list on any error

#### FEAT-002 — `flipkart.py` — `search_by_name()` method
- **File:** `app/scraper_v2/affiliate/flipkart.py`
- **API:** `GET /affiliate/1.0/json/search?q={query}&type=json`
- **Note:** Returns HTTP 404 for many queries — not all accounts have search access
- Falls back to Tavily when 0 candidates returned

#### FEAT-003 — `POST /v1/products/search-by-name`
- **File:** `app/fastapi/api/v1/search_by_name.py`
- **Request:** `{ name, platform, limit }`
- **Platform routing:**
  - `flipkart` → Affiliate API → if 0 → Tavily fallback
  - `amazon` / `myntra` → Tavily directly
- **URL filtering:** `_is_product_url()`:
  - Amazon: `/dp/` required
  - Flipkart: `pid=`, `/p/itm`, or slug `/p/` pattern
  - Myntra: `/{id}/buy` pattern
- **Amazon images:** ASIN CDN `images-na.ssl-images-amazon.com/images/P/{ASIN}.jpg`
- **Wired in:** `app/fastapi/main.py`

#### FEAT-004 — `cross_portal_listings` in subscription responses
- **Files:** `app/fastapi/api/v1/subscriptions.py`, `app/fastapi/schemas/subscription.py`
- Both `POST /v1/subscriptions` and `POST /v1/subscriptions/direct` return `cross_portal_listings`
- `SubscriptionOut.cross_portal_listings: Optional[list[dict]] = None` — additive, Streamlit-safe
- `_get_cross_portal_listings()` queries same canonical, excludes subscribed listing, cheapest first

#### FEAT-005 — `config.py` updated
- **File:** `app/core/config.py`
- Added: `tavily_api_key: str = ""`

### Frontend

#### FEAT-006 — `UrlInputForm` — dual-mode + URL validator
- **File:** `src/components/track/UrlInputForm.jsx`
- **Dual-mode:** Single input, auto-detects URL vs name on submit
- **URL mode:** No platform selector shown. `validateProductUrl()` fast-fail before scrape:
  - Skip list (no validation): `amzn.in/*`, `dl.flipkart.com/*`, `onelink.me/*`, `myntra.com/mailers/*`
  - Amazon: requires `/dp/[A-Z0-9]{10}`
  - Flipkart: requires `pid=` or `/p/itm`
  - Myntra: requires `/{numeric_id}/buy`
- **Name mode:** Platform radio buttons shown: `● All  ○ Amazon  ○ Flipkart  ○ Myntra` (default: All)
- **Props:** `onSubmitUrl(url)`, `onSubmitSearch(query, platform)`, `isLoading`, `isSearching`, `initialUrl`

**⚠️ STATUS: Platform radio buttons NOT YET BUILT — next session first task**

#### FEAT-007 — `TrackPageClient` — state machine
- **File:** `src/app/(app)/track/TrackPageClient.jsx`
- **States:**
  - `input` → UrlInputForm
  - `loading` → beacon animation (URL scrape, 10-20s)
  - `searching` → search spinner (name search, <2s)
  - `search_results` → SearchResultsCard
  - `scrape_failed` → ScrapeFailureCard
  - `preview` → PreviewCard
  - `confirming` → PreviewCard with spinner
  - `success` → SuccessScreen with Option B

#### FEAT-008 — `ScrapeFailureCard` — scrape failure recovery
- **File:** `src/components/track/ScrapeFailureCard.jsx`
- **Shown when:** `trackStep === 'scrape_failed'`
- **Flow:**
  1. User types product name + selects platform
  2. DB + Tavily fire in **parallel** via `Promise.all`
  3. Brand filter: first word matched against `r.brand`. If brand filter returns empty → skip DB, show Tavily
  4. Case A: DB match on requested platform → "🔔 Monitor this" / "✅ Monitoring"
  5. Case B: DB match on different platform → amber card + "Search {platform} →" button → Tavily
  6. Case C: DB empty/wrong brand → Tavily URL candidates → `onSelectUrl` → preview flow
- Header hidden when results showing
- Loading spinner replaces form while searching

#### FEAT-009 — `SuccessScreen` — Option B cross-portal suggestion
- **File:** `src/components/track/SuccessScreen.jsx`
- `crossPortalListings` prop — shows `CrossPortalSuggestion` cards above action buttons
- "💡 Also available on Flipkart — ₹72,999 (last checked Xh ago)"
- Always shows "last checked X ago" caveat
- Dismissable per listing

#### FEAT-010 — `SearchResultsCard`
- **File:** `src/components/track/SearchResultsCard.jsx`
- Shows canonical product cards with portal listings
- DB listings: "🔔 Monitor this" / "✅ Monitoring" (direct subscribe, same as Offers page)
- Tavily listings (`_is_tavily: true`): "🔔 Monitor this" → `onSelectUrl` → preview flow

#### FEAT-011 — `usePreview.js` updated
- `onError` → `setScrapedUrl(url)` + `setTrackStep('scrape_failed')`

#### FEAT-012 — `useAppStore.js` updated
- Added: `scrapedUrl`, `setScrapedUrl`, `resetTrack` clears `scrapedUrl`

#### FEAT-013 — `useSearch.js` — new hook
- `GET /v1/search` mutation

#### FEAT-014 — `useSearchByName.js` — new hook
- `POST /v1/products/search-by-name` mutation

---

## CONFIRMED FINAL DESIGN — Track Page (for next session)

### Complete flow

**Input (Step 1):**
- Single input box — URL or product name
- URL detected → no platform selector
- Name detected → platform radio: `● All  ○ Amazon India  ○ Flipkart  ○ Myntra`

**URL flow:**
- URL → `POST /v1/products/preview`
- Backend returns `catalog_data` (if product in DB) + live scrape data
- `PreviewCard` shows DB context (watcher count, price history, already-tracking state)
- Scrape fails → `ScrapeFailureCard` → product name flow

**Product name flow:**
- Step 4.1 — `GET /v1/search` (filtered by platform if not All)
  - If DB has results → show `SearchResultsCard`
  - If DB empty → `POST /v1/products/search-by-name` on selected platform(s) → Tavily results
  - If All selected → parallel search on all 3 platforms
- Step 4.2 — Results shown. If user can't find product → "Can't find it? Go back and give more details ←" button
- Step 4.3 — Monitor clicked:
  - DB listing → `POST /v1/subscriptions/direct` (no scrape)
  - Tavily listing → `onSelectUrl(url)` → `POST /v1/products/preview` → PreviewCard → subscribe

**After subscription:**
- Success screen shows Option B cross-portal suggestion if `cross_portal_listings` non-empty

---

## Next Session — Tasks in Order

### Task 1 — Add platform radio buttons to `UrlInputForm`
- Show radio group only when input is name (not URL)
- Options: All (default), Amazon India, Flipkart, Myntra
- Pass selected platform to `onSubmitSearch(query, platform)`

### Task 2 — Update `TrackPageClient` search handler
- When platform = All → `Promise.allSettled` on all 3 platforms in parallel
- When platform = specific → single `GET /v1/search` filtered by platform, then Tavily if empty
- "Can't find it?" back button in `SearchResultsCard`

### Task 3 — Add "Can't find it?" button to `SearchResultsCard`
- Below results: "Can't find what you're looking for? Go back and try a more specific name ←"
- Calls `onBack()`

### Task 4 — Railway deploy
- `git push` → Railway auto-deploy
- Add `TAVILY_API_KEY` to Railway Variables
- Verify `GET https://api.priceping.in/v1/search?q=samsung`
- Run `backfill_identity.py` if needed on production DB

### Task 5 — Deferred loading tip messages (low priority)
- During `loading` state (URL scrape, 10-20s) — rotating useful shopping tips
- Not static text

---

## Deferred Items

| Item | Notes |
|---|---|
| DEF-002: Search "Samsung TV" returns phones | Category keyword detection needed |
| DEF-003: Flipkart Affiliate search 404 | Tavily fallback covers it |
| Notification preferences UI | Designed in v4.8, still pending |
| `portal_listings` table rename | Phase 3 |
| Amazon PA-API | No credentials |
| Rotating loading tips | Low priority, deferred |

---

## Known Working State (local, pre-next-session)

- Backend: FastAPI `localhost:8001`, Supabase
- Frontend: Next.js `localhost:3000`
- 136 products identity-linked
- `GET /v1/search` — two-pass trgm working
- `POST /v1/products/search-by-name` — Tavily returning Amazon URLs with images
- `ScrapeFailureCard` — Case A, B, C tested and working
- Platform radio buttons on `UrlInputForm` — NOT YET BUILT
- Option B success screen — built, not fully end-to-end tested
- Railway — NOT YET DEPLOYED for v5.1/v5.2
