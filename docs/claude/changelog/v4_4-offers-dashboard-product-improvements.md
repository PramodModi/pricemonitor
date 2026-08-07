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

## [v4.4] — Offers Page + Dashboard Overhaul + Product Page Improvements — August 2026

This phase introduces the public product catalogue (`/offers`), a major dashboard
redesign (vertical card grid, portal filter tabs, beacon loading, price drop badge),
and several product detail page improvements (collapsible sections, tabbed
Description/Specs, subscription status fix). One backend fix corrects how Flipkart's
bank offer price is stored in price history.

**Scope of this phase:** `GET /v1/products` endpoint, `/offers` page, dashboard grid
layout, dashboard price drop badge (`get_max_prices` batch query), dashboard portal
tabs, beacon loading animation (Dashboard + Track), vertical `ProductCard`, product
detail tabs (`ProductDetailTabs`), collapsible Bank Offers section, Sidebar/Navbar
Offers link activated, `SidebarPriceBox` subscription status fix, Flipkart
`special_price` → `current_price` backend fix.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/repositories/product_repo.py` | `get_all()` — paginated products with watcher count + all-time stats (1 batch query); `get_max_prices()` — all-time max price per product for price drop badge (1 batch query) |
| `app/fastapi/schemas/product.py` | `ProductListItem`, `ProductListOut` added for `GET /v1/products` |
| `app/fastapi/schemas/subscription.py` | `price_drop_pct: Optional[float] = None` added to `ItemOut` |
| `app/fastapi/api/v1/products.py` | `GET /v1/products` endpoint added (before `/{product_id}` route) |
| `app/fastapi/api/v1/items.py` | `get_max_prices()` batch call + `price_drop_pct` computation added to `get_items()` |
| `app/scraper_v2/engine.py` | `_affiliate_result_to_scrape_response()` — Flipkart `special_price` used as `current_price` when lower; `discount_pct` recalculated from effective price vs MRP |
| `src/components/layout/Sidebar.jsx` | `phase: 2` removed from Offers — now a real `<Link>` |
| `src/components/landing/Navbar.jsx` | "Deals" → "Offers", rendered as real `<Link>`; Coupons/Blog remain disabled spans |
| `src/app/(app)/dashboard/page.jsx` | Beacon loading animation; portal filter tabs; 4-column responsive grid; `displayPrice`/`regularPrice` logic; subtitle reflects active filter |
| `src/components/dashboard/ProductCard.jsx` | Rewritten as vertical card (image top, content below); opens product page in new tab (`window.open`); price drop badge (↓ X%) from `price_drop_pct`; `useRouter` removed |
| `src/components/product/SidebarPriceBox.jsx` | `useItems(userEmail)` replaces stale cache read; `isCheckingStatus` guard prevents wrong button flash |
| `src/app/(app)/track/TrackPageClient.jsx` | Beacon loading animation replaces `PreviewSkeleton`; `PreviewSkeleton` import removed |
| `src/components/product/OffersSection.jsx` | Collapsible — collapsed by default; count badge `(N)` on header; `'use client'` added |
| `src/components/product/ProductDetailTabs.jsx` | **New** — replaces `ProductDescription` + `FullSpecsTable`; two tabs when both sections have data; plain heading when only one section (Amazon/Myntra) |
| `src/app/products/[slug]/page.jsx` | `ProductDescription` + `FullSpecsTable` replaced with `ProductDetailTabs`; imports updated |
| `src/hooks/useProducts.js` | **New** — `GET /v1/products` TanStack Query hook; `queryKey: ['products', platform]`; 5-minute stale time |
| `src/components/offers/ProductListCard.jsx` | **New** — vertical card for offers page; 3-state Monitor button; tracking state from cache |
| `src/app/(app)/offers/page.jsx` | **New** — Suspense wrapper (useSearchParams requirement) |
| `src/app/(app)/offers/OffersPageClient.jsx` | **New** — platform filter tabs; 4-column grid; prefetches `useItems` for tracking state; reads `?platform=` from URL |

---

### Features

#### FEAT-001 — `GET /v1/products` Listing Endpoint
- **Files:** `app/repositories/product_repo.py`, `app/fastapi/schemas/product.py`, `app/fastapi/api/v1/products.py`
- **Change:** New public endpoint returning all products in the catalogue ordered by
  watcher count descending. Optional `platform` query param (`amazon`|`flipkart`|`myntra`).
  `limit` (max 100) and `offset` for pagination. Single SQL query with two LEFT JOIN
  subqueries: watcher count (from `subscriptions`) and all-time low/high (from
  `price_history`). No authentication required.
- **Route:** `GET /v1/products?platform=amazon&limit=50&offset=0`
- **Response:** `{ total, count, platform, items: ProductListItem[] }`

#### FEAT-002 — `/offers` Page (Public Product Catalogue)
- **Files:** `src/hooks/useProducts.js`, `src/components/offers/ProductListCard.jsx`,
  `src/app/(app)/offers/page.jsx`, `src/app/(app)/offers/OffersPageClient.jsx`
- **Change:** Public product listing page inside `(app)/` route group (keeps AppShell
  sidebar). Platform filter tabs (All / Amazon / Flipkart / Myntra) read initial state
  from `?platform=` URL param — Footer links like `/offers?platform=amazon` pre-select
  the correct tab. Product grid: `1→2→3→4` columns responsive. `useItems(userEmail)`
  prefetched once at page level so each card reads tracking state from cache (zero
  per-card API calls). Monitor button: `✅ Monitoring` (green, disabled) or
  `🔔 Monitor this` (→ `/track?url=...`).
- **Resolves:** DEF-009 (Footer "Track prices on" links now work).

#### FEAT-003 — Price Drop Badge on Dashboard Cards
- **Files:** `app/repositories/product_repo.py`, `app/fastapi/api/v1/items.py`,
  `app/fastapi/schemas/subscription.py`, `src/components/dashboard/ProductCard.jsx`
- **Change:** `GET /v1/items` now runs a second batch query (`get_max_prices()`) to
  fetch the all-time maximum price per product in one SQL call. `price_drop_pct` is
  computed per item: `((max_price - current_price) / max_price * 100)` when
  `current_price < max_price` AND drop ≥ 1%. Shown as a green `↓ X%` pill badge
  on the product image (top-right). `price_drop_pct: Optional[float] = None` added
  to `ItemOut` — Streamlit ignores unknown JSON fields (backward compatible).
- **Threshold:** 1% minimum — catches meaningful drops, not rounding noise.
- **Why all-time max (not previous scrape):** Previous-scrape comparison only catches
  drops in the last cron cycle. All-time max correctly surfaces "price peaked then
  dropped" scenarios that remain stable at the lower price across multiple scrapes.

#### FEAT-004 — Dashboard Redesign
- **File:** `src/app/(app)/dashboard/page.jsx`, `src/components/dashboard/ProductCard.jsx`
- **Changes:**
  - **Vertical card layout** — `ProductCard` rewritten with image on top (matches
    offers page), opens product detail in a new tab (`window.open`), removes
    `useRouter`
  - **4-column responsive grid** — `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3
    xl:grid-cols-4` replaces single-column `space-y-3`
  - **Portal filter tabs** — computed from the user's actual items; shown only when
    items span 2+ platforms; count badge per tab; subtitle updates to
    "N of M items · Amazon" when filtered
  - **Beacon loading animation** — indigo bell with two `animate-ping` rings + three
    bouncing dots; replaces 3× `ProductCardSkeleton`; `ProductCardSkeleton` import
    removed
  - **Full-width layout** — `max-w-2xl mx-auto` removed; content fills available
    space beside sidebar

#### FEAT-005 — Beacon Loading Animation on Track Page
- **File:** `src/app/(app)/track/TrackPageClient.jsx`
- **Change:** Same beacon animation as Dashboard (indigo bell, ping rings, bouncing
  dots) replaces `PreviewSkeleton` on the `loading` step. Copy: "Fetching product
  details / Checking the live price — this takes around 10–20 seconds…" sets accurate
  expectations for Playwright scrape duration. `PreviewSkeleton` import removed.

#### FEAT-006 — Collapsible Bank Offers Section
- **File:** `src/components/product/OffersSection.jsx`
- **Change:** Section collapses by default. Header is a full-width button with
  chevron; count badge `(N)` shows item count without expanding. `'use client'` and
  `useState` added. Separator `<hr>` added below for visual separation.

#### FEAT-007 — Tabbed Description & Specifications (`ProductDetailTabs`)
- **Files:** `src/components/product/ProductDetailTabs.jsx` (new),
  `src/app/products/[slug]/page.jsx`
- **Change:** `ProductDescription` and `FullSpecsTable` replaced by a single
  `ProductDetailTabs` component. When both description/features and specs are present
  (Flipkart): two tabs rendered with indigo underline on active. When only one section
  has data (Amazon/Myntra — no specs): content rendered directly with a plain
  "Description & Features" heading. "Show all N features" toggle remains functional
  inside the description tab.
- **Resolves:** Amazon and Myntra products were showing description/features with no
  section heading (FIX-002).

#### FEAT-008 — Sidebar Subscription Status Fix
- **File:** `src/components/product/SidebarPriceBox.jsx`
- **Change:** Replaced stale `queryClient.getQueryData()` cache read with
  `useItems(userEmail)` live fetch. Added `isCheckingStatus` guard (same pattern as
  `PreviewCard`): shows disabled "Checking…" spinner while fetch is in-flight, so
  neither "Monitor" nor "Watching this" flashes incorrectly. Product page now shows
  correct subscription state even when opened in a new tab (empty cache).

#### FEAT-009 — Navbar and Sidebar Offers Link Activated
- **Files:** `src/components/landing/Navbar.jsx`, `src/components/layout/Sidebar.jsx`
- **Change:** Offers link changed from disabled span/div to real `<Link href="/offers">`.
  Navbar label changed from "Deals" to "Offers" to match the page title. Coupons and
  Blog remain disabled ("Soon"). `phase: 2` flag removed from Sidebar Offers entry.

---

### Fixes

#### FIX-001 — Flipkart `special_price` Not Used as Canonical Price
- **File:** `app/scraper_v2/engine.py`
- **Symptom:** Flipkart products stored `current_price = flipkartSellingPrice`
  (e.g. ₹69,900) while the actual effective buying price after bank offer
  (`flipkartSpecialPrice`, e.g. ₹65,749) was only stored as `special_price`.
  Price history, all-time stats, drop detection, and notifications were all based
  on the intermediate price, not what users actually pay.
- **Root cause:** `_affiliate_result_to_scrape_response()` always used `result.price`
  (selling price) as `current_price`.
- **Fix:** When `config.name == "flipkart"` AND `result.special_price` is set AND
  `special_price < price`: use `special_price` as `current_price` (effective price),
  and recalculate `discount_pct` as `((mrp - special_price) / mrp * 100)` to show
  the true saving from MRP. Amazon and Myntra are explicitly excluded by the
  `config.name == "flipkart"` guard — no effect on other portals.
- **Impact:** All downstream data (price history, all-time low/high, drop detection)
  now records the real buying price. Frontend `special_price < current_price`
  evaluates to `false` when both are equal — "Offer price" line disappears naturally.

#### FIX-002 — ProductDetailTabs Missing Heading for Amazon/Myntra
- **File:** `src/components/product/ProductDetailTabs.jsx`
- **Symptom:** Amazon and Myntra product pages showed description/features content
  with no section heading — the content appeared as an unlabelled card below the
  price history chart.
- **Root cause:** `showTabs = hasContent && hasSpecs`. For Amazon/Myntra (no specs),
  `showTabs = false`, so the tab header block was skipped entirely. No fallback
  heading was rendered.
- **Fix:** Changed `{showTabs && <tabs>}` to `{showTabs ? <tabs> : <h2>}`. When
  `showTabs = false`, a plain `"Description & Features"` or `"Full Specifications"`
  heading is rendered instead.

#### FIX-003 — `price_drop_pct` Badge Not Showing for Stable-Low Products
- **File:** `app/fastapi/api/v1/items.py`, `app/repositories/product_repo.py`
- **Symptom:** Products whose price peaked then dropped (e.g. weight plates:
  ₹2,184 → ₹1,145) showed no drop badge because the previous two scrapes were both
  at ₹1,145 — the initial implementation compared only the second-most-recent row
  (ROW_NUMBER = 2).
- **Root cause:** Price stabilised at the lower value across multiple scrapes, so
  `current == prev` and `price_drop_pct = null`.
- **Fix:** Changed batch query from ROW_NUMBER=2 to `MAX(price)` from all price
  history. Badge now shows when `current_price < all_time_max AND drop ≥ 1%`.

---

### Deviations from Design

#### DEV-001 — `ProductDescription` and `FullSpecsTable` Now Unused
- **Original design:** `ProductDescription` (section ⑥) and `FullSpecsTable` (section
  ⑦) as separate components in the product page left column.
- **Actual:** Both replaced by `ProductDetailTabs`. The collapsible versions delivered
  earlier in this session are also superseded. Files remain in
  `src/components/product/` but are no longer imported by `page.jsx`.
- **Reason:** Tabs provide a better UX than two separate collapsible sections — same
  vertical space, user switches between them with one click.

#### DEV-002 — Offers Page Inside `(app)/` Route Group
- **Original design (UI_Design_Document.md):** `/offers` at `src/app/offers/` —
  public page with Navbar, outside AppShell.
- **Actual:** `src/app/(app)/offers/` — inside AppShell, Sidebar visible.
- **Reason:** Primary access is via Sidebar nav link; user stays in app context.
  Phase 2 ISR upgrade can move it outside `(app)/` for SEO if needed.

#### DEV-003 — Dashboard Product Card Opens in New Tab
- **Original design:** `router.push('/products/{id}')` — same-tab navigation.
- **Actual:** `window.open('/products/{id}', '_blank', 'noopener,noreferrer')`.
- **Reason:** User navigating to a product page loses dashboard context; back button
  required to return. New tab preserves the dashboard for comparison.

#### DEV-004 — `price_drop_pct` on `ItemOut` Not on `ProductOut`
- **Rationale:** `ProductOut` is shared by all endpoints including the Streamlit
  integration. `price_drop_pct` is a dashboard-specific computed field — adding it to
  `ItemOut` only keeps the change additive and Streamlit-safe.

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp` | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not run | Before Profile page goes live |
| DEF-006 | Domain DNS not configured (`priceping.in` → Vercel, `api.priceping.in` → Railway) | Before production deploy |
| DEF-007 | Product page URL uses `product_id` UUID — no slug column yet | Phase 2 |
| DEF-008 | No rate limiting on preview endpoint | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not built | When auth endpoints implemented |
| DEF-011 | `GET /v1/health` endpoint not implemented — AppShell health check disabled | When endpoint added |
| DEF-012 | Buy recommendation for new products shows generic "insufficient data" message | Next session — needs `recommendation.js` + `SidebarRecommendation.jsx` |
| DEF-013 | `ProductDescription.jsx` and `FullSpecsTable.jsx` are now unused — can be deleted | Cleanup |
| DEF-014 | Flipkart `special_price` fix applies to future scrapes only — existing DB rows not backfilled | Manual re-track or wait for next cron run |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Buy recommendation improvements** | High | New product / insufficient data message; "stable N days → safe to buy"; "dropped N times → consider waiting". Needs `recommendation.js` + `SidebarRecommendation.jsx` |
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **`GET /v1/health`** | Medium | Re-enables AppShell health check banner |
| **`PATCH /v1/subscriptions/{id}`** | Medium | `target_price` persistence — unlocks `TargetPriceInput` |
| **Vercel deploy** | Medium | Connect GitHub repo, set `NEXT_PUBLIC_API_URL=https://api.priceping.in` |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Products slug column** | Low | Phase 2 — slug backfill + `GET /v1/products/by-slug/{slug}` |

---

### Files Modified

| File | Change type | Description |
|---|---|---|
| `app/repositories/product_repo.py` | FEAT | `get_all()` + `get_max_prices()` methods added |
| `app/fastapi/schemas/product.py` | FEAT | `ProductListItem`, `ProductListOut` added |
| `app/fastapi/schemas/subscription.py` | FEAT | `price_drop_pct: Optional[float] = None` on `ItemOut` |
| `app/fastapi/api/v1/products.py` | FEAT | `GET /v1/products` endpoint added |
| `app/fastapi/api/v1/items.py` | FEAT + FIX | `get_max_prices()` batch call; `price_drop_pct` computation; 1% threshold |
| `app/scraper_v2/engine.py` | FIX | Flipkart `special_price` → `current_price` with recalculated `discount_pct` |
| `src/components/layout/Sidebar.jsx` | FEAT | Offers `phase: 2` flag removed |
| `src/components/landing/Navbar.jsx` | FEAT | "Deals" → "Offers"; real `<Link>` |
| `src/app/(app)/dashboard/page.jsx` | FEAT | Beacon loading; portal tabs; 4-col grid; full-width layout |
| `src/components/dashboard/ProductCard.jsx` | FEAT | Vertical card; new tab; drop badge; `useRouter` removed |
| `src/components/product/SidebarPriceBox.jsx` | FIX | `useItems` fetch + `isCheckingStatus` guard |
| `src/app/(app)/track/TrackPageClient.jsx` | FEAT | Beacon loading; `PreviewSkeleton` removed |
| `src/components/product/OffersSection.jsx` | FEAT | Collapsible with count badge |
| `src/components/product/ProductDetailTabs.jsx` | FEAT + FIX | New — tabbed layout; plain heading for no-specs portals |
| `src/app/products/[slug]/page.jsx` | FEAT | `ProductDetailTabs` replaces `ProductDescription` + `FullSpecsTable` |
| `src/hooks/useProducts.js` | FEAT | New — `GET /v1/products` TanStack Query hook |
| `src/components/offers/ProductListCard.jsx` | FEAT | New — vertical offer card with Monitor button |
| `src/app/(app)/offers/page.jsx` | FEAT | New — Suspense wrapper |
| `src/app/(app)/offers/OffersPageClient.jsx` | FEAT | New — offers page with platform tabs |

---

*Archive this file to `docs/changelog/v4_4-offers-dashboard-product-improvements.md` when the next phase begins.*
