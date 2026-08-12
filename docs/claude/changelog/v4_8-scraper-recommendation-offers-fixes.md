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

## [v4.8] — Scraper Reliability, Recommendation Engine, Offers Direct Subscribe — August 2026

This phase fixes critical scraper reliability issues on Railway (concurrent scrape
contention, Amazon/Flipkart short URL handling, Flipkart affiliate PID extraction via
ScraperAPI), improves the buying recommendation engine (guard rules, stable price band),
and adds inline direct subscription from the Offers page without re-scraping.

**Scope:** `engine.py`, `generic_scraper.py`, `recommendation.js`,
`subscription_service.py`, `subscriptions.py`, `exceptions.py`,
`ProductListCard.jsx`, `api.js`.

---

### Summary Table

| Tag | Area | Description |
|-----|------|-------------|
| FIX-001 | Scraper | Process-level semaphore prevents concurrent Playwright contention |
| FIX-002 | Scraper | `amzn.in` short URL resolved via `page.url` before ScraperAPI |
| FIX-003 | Scraper | Flipkart `dl.flipkart.com/s/` short URL HTTP pre-resolution |
| FIX-004 | Scraper | Flipkart affiliate PID extracted from raw HTML regex on ScraperAPI path |
| FIX-005 | Scraper | Affiliate retry skipped when browser succeeded (prevented double API call) |
| FIX-006 | Recommendation | Rule 1 guard prevents "near all-time low" firing when price is at all-time high |
| FIX-007 | Recommendation | Rule 5 stable band widened from 2% to 3% |
| FIX-008 | Recommendation | Three new guards for brand-new/single-price-point products |
| FIX-009 | Recommendation | Rule 7 fallthrough message distinct from new-product messages |
| FEAT-001 | Offers | `POST /v1/subscriptions/direct` — subscribe without scraping |
| FEAT-002 | Offers | Inline email prompt in `ProductListCard` — no navigation to Track page |
| FEAT-003 | Scraper | `_retry_flipkart_affiliate()` helper — affiliate retry after short URL resolution |
| CFG-001 | API | Axios timeout raised from 35s to 150s |
| CFG-002 | Scraper | Semaphore queue timeout set to 120s |
| DEF-001 | Scraper | Flipkart short URL `marketplace_product_id` not saved to DB after PID extraction |
| DEF-002 | Scraper | Cron job re-resolves Flipkart short URLs every 4h (stored `url` is still short URL) |
| DEF-003 | Scraper | HTTP pre-resolution of `dl.flipkart.com/s/` always times out on Railway (blocked) |

---

### FIX-001 — Process-level semaphore for Playwright contention

**File:** `app/scraper_v2/engine.py`

**Problem:** Rapid double-submits on the Track page spawned two or three concurrent
`ScraperEngine` instances. Playwright's sync API serialises internally but only after
each thread has already launched a full browser and started navigating — causing severe
thread contention. Total wall time became 3× one scrape (~50s), blowing past the 35s
Axios timeout.

**Diagnosis signal:** Three `[NAV]` log lines for the same URL starting within 3 seconds
of each other — the retry cascade is sequential so three overlapping navigations means
three concurrent engine instances.

**Fix:** Added `threading.Semaphore(1)` at module level (`_SCRAPE_SEMAPHORE`). `scrape()`
acquires the semaphore before calling the real logic (moved to `_scrape_inner()`). A
second request waits up to `_SCRAPE_QUEUE_TIMEOUT_S=120` seconds. If timeout expires,
returns `ScrapeFailureReason.TIMEOUT` with "queue" in the message — caller returns
HTTP 503 `SCRAPE_BUSY` so the frontend shows "try again" immediately.

```python
_SCRAPE_SEMAPHORE = threading.Semaphore(1)
_SCRAPE_QUEUE_TIMEOUT_S = 120
```

---

### FIX-002 — `amzn.in` short URL resolved via `page.url` before ScraperAPI

**File:** `app/scraper_v2/engine.py`

**Problem:** ScraperAPI returned 3506 bytes (redirect stub) instead of the real product
page ~50% of the time on `amzn.in` short URLs — requiring 2-3 retry attempts and pushing
total scrape time to 110+ seconds.

**Fix:** After browser attempt 1 fails (CAPTCHA), `page.url` already holds the real
`amazon.in/dp/ASIN` URL because Playwright follows the redirect before Amazon's bot check
fires. Added `page_url_out` parameter to `_attempt_browser()` — a mutable list used as
a side-channel to capture `page.url` without changing `ScrapeResponse`. All subsequent
ScraperAPI attempts use the resolved full URL, which ScraperAPI handles reliably.

**Log signal after fix:**
```
[ENGINE] amzn.in short URL resolved — short=amzn.in/d/xxx resolved=amazon.in/dp/ASIN
attempt=2 ScraperAPI url=amazon.in/dp/ASIN → 200 content_length=2.5MB ✅
```

---

### FIX-003 — Flipkart `dl.flipkart.com/s/` short URL HTTP pre-resolution

**File:** `app/scraper_v2/engine.py`

**Problem:** On Railway, Flipkart's WAF intercepts the Firebase Dynamic Link redirect
with a bot-check page BEFORE following the redirect — so `page.url` stays as
`dl.flipkart.com/s/...` and the post-browser capture cannot extract the PID. ScraperAPI
was being called with the short URL which it handled inconsistently.

**Fix:** Added `_resolve_flipkart_short_url()` — a plain HTTP HEAD request with
`allow_redirects=True` before any browser opens. Firebase Dynamic Links respond to
standard HTTP redirects from any IP. After resolution, retries affiliate API with the
real URL.

**Status:** This works locally but `dl.flipkart.com` also blocks Railway's outbound IPs
on HTTPS — `ReadTimeout` every time on Railway (see DEF-003). Falls through gracefully
to browser cascade.

---

### FIX-004 — Flipkart affiliate PID extracted from raw HTML regex on ScraperAPI path

**File:** `app/scraper_v2/scrapers/generic_scraper.py`

**Problem:** When ScraperAPI pre-loads HTML (`skip_navigation=True`), `page.url` is
`about:blank`. The post-redirect affiliate retry was calling
`extract_product_id(page.url)` → None, then falling back to the path-based `itm...` ID
which the Flipkart affiliate API rejects with HTTP 404. Result: `mrp=None`,
`special_price=None`, `offers_count=0` on Railway.

**Attempts:**
1. Extract canonical URL from `<link rel="canonical">` → canonical omits `?pid=` param →
   `extract_product_id()` returns `itm...` path ID → 404.
2. Regex on raw HTML for `[?&]pid=([A-Z0-9]{10,20})` → finds real affiliate PID
   (uppercase alphanumeric, never matches lowercase `itm...`) → 200 ✅.

**Fix:** Three-tier PID resolution in the affiliate retry block:
- Path A (browser): `page.url` has `?pid=` → use `extract_product_id(page.url)`
- Path B (ScraperAPI): `page.url` = `about:blank` → regex scan raw HTML for
  `[?&]pid=([A-Z0-9]{10,20})` → extracts real PID
- Last resort: path-based `product_id` (will 404 but won't crash)

**Result after fix:**
```
[AFFILIATE] pid extracted from raw HTML — pid=TVSHMX46YA6QT3RR
[AFFILIATE] HTTP 200 — mrp=79900 special_price=58990 offers=26 ✅
```

---

### FIX-005 — Affiliate retry skipped when browser already succeeded

**File:** `app/scraper_v2/engine.py`

**Problem:** When Flipkart browser attempt succeeded (Railway not blocking that session),
`generic_scraper` already ran the post-redirect affiliate call internally. The engine-level
`_retry_flipkart_affiliate()` then ran again — making a second identical affiliate API
call for the same PID, wasting ~170ms and one API credit.

**Fix:** Engine-level affiliate retry wrapped in `if not response.success:` — only runs
when browser attempt failed.

---

### FIX-006 — Recommendation Rule 1 guard for narrow price ranges

**File:** `src/lib/recommendation.js`

**Problem:** Rule 1 checks `current <= low * 1.05`. When the overall price range is
narrow (e.g. all-time low ₹18,289, all-time high ₹18,700 — a 2.2% band), current price
at the all-time high still satisfied `18,700 <= 18,289 * 1.05 = 19,203` → "Great time
to buy" verdict even though price was at its all-time high.

**Fix:** Rule 1 now requires `current <= low * 1.05 AND current < high * 0.95`. If
current is within 5% of the high, Rule 3 ("near all-time high") takes priority.

---

### FIX-007 — Stable price band widened from 2% to 3%

**File:** `src/lib/recommendation.js`

**Problem:** Rule 5 (stable price) fired when `(high - low) / high <= 0.02`. A product
with a 2.2% band (₹411 spread on ₹18,700) didn't trigger it — falling through to
insufficient data or neutral with a less useful message.

**Fix:** Threshold widened to `<= 0.03` (3%) — captures products with very narrow price
ranges that are unlikely to change significantly.

---

### FIX-008 — Three new guards for new/single-price-point products

**File:** `src/lib/recommendation.js`

**Problem:** Brand new products and products with only one scrape showed "We're still
collecting price history. Check back in a few days." — generic and identical for all
three distinct situations.

**Fix:** Three specific guards before all rules:
- **Guard 0a** (`priceStats` null or `currentPrice` null): "Just started tracking.
  We'll build up price history over the next few days."
- **Guard 0b** (`all_time_low`/`all_time_high`/`drop_count` null): same message —
  stats object exists but incomplete.
- **Guard 0c** (`low === high` — only one distinct price seen): "Only one price recorded
  so far. Check back after a few more scans." — distinct message, product has been
  scanned but hasn't moved.

---

### FIX-009 — Rule 7 fallthrough message distinct from new-product messages

**File:** `src/lib/recommendation.js`

**Problem:** Products that had history but didn't match any rule showed the same
"collecting price history" message as brand-new products — misleading.

**Fix:** Rule 7 fallthrough now returns "Not enough price variation yet to give a
confident signal." — accurate for products with history but no strong directional signal.

---

### FEAT-001 — `POST /v1/subscriptions/direct` endpoint

**Files:** `app/fastapi/api/v1/subscriptions.py`,
`app/services/subscription_service.py`, `app/core/exceptions.py`

**What:** New endpoint `POST /v1/subscriptions/direct` takes `{ product_id, email }`.
No scrape, no preview cache required — product must already exist in DB. Used by the
Offers page "Monitor this" button. Returns same `SubscriptionOut` shape as existing
`POST /v1/subscriptions`.

**New exception:** `ProductNotFoundError` added to `exceptions.py` — maps to HTTP 404
`PRODUCT_NOT_FOUND`.

**New service method:** `SubscriptionService.subscribe_direct(product_id, email)` — uses
`_get_or_create_user()` private helper (inline SQLAlchemy, no separate UserRepository
import needed) + existing `SubscriptionRepository.get_or_create()`.

**Sends confirmation email** on new subscription only. Silent on duplicate (idempotent).

---

### FEAT-002 — Inline email prompt in `ProductListCard`

**File:** `src/components/offers/ProductListCard.jsx`

**What:** "Monitor this" button on Offers page cards no longer navigates to `/track`.
Instead:
- Email in Zustand store → calls `POST /v1/subscriptions/direct` immediately
- No email in store → inline email prompt expands within the card
- On success → toast notification, button flips to "✅ Monitoring", email saved to store
- Button shows "Adding…" spinner while request is in flight
- Disabled on duplicate (already tracking)

---

### FEAT-003 — `_retry_flipkart_affiliate()` helper

**File:** `app/scraper_v2/engine.py`

**What:** New private method on `ScraperEngine`. After a Flipkart short URL is resolved
(either via HTTP pre-resolution or `page.url` capture), attempts the Flipkart affiliate
API with the resolved URL. Returns a full `ScrapeResponse` on hit, `None` on miss.
Caller falls through to ScraperAPI on None. Used by both the pre-resolution block and
the post-browser-capture block.

---

### CFG-001 — Axios timeout raised to 150s

**File:** `src/lib/api.js`

**Before:** `timeout: 35_000`
**After:** `timeout: 150_000`

**Reason:** Worst-case scrape path on Railway: browser CAPTCHA (~15s) + ScraperAPI
(~90s) + extraction (~7s) = ~112s. Previous 35s caused UI timeout even when the backend
eventually succeeded. 150s = 120s semaphore queue timeout + 30s buffer.

---

### CFG-002 — Semaphore queue timeout set to 120s

**File:** `app/scraper_v2/engine.py`

**Before:** `_SCRAPE_QUEUE_TIMEOUT_S = 60`
**After:** `_SCRAPE_QUEUE_TIMEOUT_S = 120`

**Reason:** A queued request that waited 60s was rejected 9 seconds before the active
scrape completed (which took ~51s). 120s provides comfortable headroom for the worst-case
ScraperAPI response time.

---

### DEF-001 — Flipkart short URL `marketplace_product_id` not saved to DB

**Severity:** High — causes operational inefficiency and broken deduplication.

**Problem:** When a `dl.flipkart.com/s/` short URL is scraped via ScraperAPI, the regex
extracts the affiliate PID (`TVSHMX46YA6QT3RR`) successfully. However this PID and the
resolved canonical URL (`flipkart.com/.../itm.../`) are not returned in `ScrapeResponse`
and are not saved to the `products` table. The product is stored with:
- `url = dl.flipkart.com/s/...` (short URL)
- `marketplace_product_id = None`

**Impact:**
- Cron job scrapes `dl.flipkart.com/s/...` every 4 hours — goes through full cascade
  (HTTP timeout + browser CAPTCHA + ScraperAPI + regex) every time.
- Deduplication broken — same product pasted twice creates two rows if short URL
  differs even slightly.
- Affiliate API cannot be called at attempt 0 on subsequent scrapes.

**Fix needed:**
1. Return extracted PID and resolved canonical URL from `ScrapeResponse`.
2. `ProductSyncService` saves resolved canonical URL as `url` and PID as
   `marketplace_product_id`.
3. Cron job then hits affiliate API at attempt 0 (full URL has PID) — no ScraperAPI
   needed on subsequent scrapes.

**Files to change:** `app/scraper_v2/models/scrape_result.py` (add `resolved_url`,
`affiliate_pid` fields), `app/scraper_v2/scrapers/generic_scraper.py` (populate fields),
`app/services/product_sync.py` (use resolved URL and PID when saving).

---

### DEF-002 — Cron job re-resolves Flipkart short URLs every 4 hours

**Severity:** Medium — wastes ScraperAPI credits and adds latency to scheduled scrapes.

**Blocked by:** DEF-001 — fix DEF-001 first (save resolved URL to DB).

**Problem:** Scheduled cron scrapes use `product.url` from the DB. If the short URL is
stored, the full cascade runs every 4 hours for each Flipkart short URL product.

---

### DEF-003 — `dl.flipkart.com` blocks Railway outbound IPs on HTTPS

**Severity:** Low — graceful fallback exists.

**Problem:** `_resolve_flipkart_short_url()` makes an HTTP HEAD request to
`dl.flipkart.com` — times out after 10s on Railway with
`ReadTimeout: HTTPSConnectionPool(host='dl.flipkart.com', port=443)`.
Firebase Dynamic Link resolution fails on Railway, though it works locally.

**Current behaviour:** Falls through to browser cascade with original short URL.
Scrape still succeeds via ScraperAPI + regex PID extraction (FIX-004).

**Possible future fix:** Use ScraperAPI itself to follow the short URL redirect and
return the final URL before the main scrape — one extra ScraperAPI call but avoids the
10s timeout wait.

---

### Files Modified

| File | Type | Changes |
|------|------|---------|
| `app/scraper_v2/engine.py` | Backend | Semaphore, `amzn.in` resolve, Flipkart short URL pre-resolution, `_retry_flipkart_affiliate()`, `_resolve_flipkart_short_url()`, `page_url_out` on `_attempt_browser()` |
| `app/scraper_v2/scrapers/generic_scraper.py` | Backend | Three-tier PID resolution (Path A/B/regex), affiliate retry guard |
| `app/services/subscription_service.py` | Backend | `DirectSubscribeResult`, `_get_or_create_user()`, `subscribe_direct()` |
| `app/fastapi/api/v1/subscriptions.py` | Backend | `DirectSubscribeRequest`, `POST /v1/subscriptions/direct` |
| `app/core/exceptions.py` | Backend | `ProductNotFoundError` |
| `src/lib/recommendation.js` | Frontend | Guards 0a/0b/0c, Rule 1 high-guard, Rule 5 band 3%, Rule 7 message |
| `src/components/offers/ProductListCard.jsx` | Frontend | Inline subscribe, email prompt, toast |
| `src/lib/api.js` | Frontend | Axios timeout 35s → 150s |

---

### Next Phase Candidates

| Priority | Item | Notes |
|----------|------|-------|
| P0 | DEF-001 — Save resolved URL + PID to DB for Flipkart short URLs | Fixes cron inefficiency and deduplication |
| P1 | Login page (`/login`) | DEF from v4.5 |
| P1 | FastAPI auth endpoints | DEF from v4.5 |
| P2 | Price chart Y-axis negative values fix | DEF-019 from v4.7 |
| P2 | `GET /v1/health` endpoint | DEF-011 from v4.7 |
| P2 | `PATCH /v1/subscriptions/{id}` — target price persistence | DEF-010 from v4.7 |
| P3 | Double-submit prevention on Track page (`useRef` guard) | Reduces semaphore contention |
| P3 | `products.slug` column + ISR product pages | Phase 2 foundation |
