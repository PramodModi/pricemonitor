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

## [v4.1] — Dashboard + Product Detail Pages — August 2026

This phase connects the Dashboard page to the live FastAPI backend and builds the
complete Product Detail page (`/products/[slug]`). Both pages are fully functional
with real data. The `cn` utility omission from the previous session was also fixed,
resolving a landing page crash.

**Scope of this phase:** Dashboard live data connection, delete flow, Product Detail
two-column layout with sticky sidebar, all left-column sections (Hero, KeySpecs,
PriceHistory, Offers, Description, FullSpecs), all sidebar boxes (PriceBox,
Recommendation, PriceStats, TargetPriceInput), MobileBottomBar, Breadcrumb with
back-navigation, CORS fix in FastAPI, and brand language audit.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/main.py` | `CORSMiddleware` added — allows `localhost:3000` and `priceping.in` |
| `src/lib/utils.js` | `cn` utility (clsx + tailwind-merge) added — was missing, broke landing page Navbar |
| `src/lib/utils.js` | All PricePing utilities added: `formatPrice`, `formatTimeAgo`, `formatDateIST`, `formatDateShort`, `formatMonthYear`, `slugify`, `getPlatformLabel`, `getPlatformBadgeClass`, `getPlatformIcon`, `isValidEmail`, `isSupportedPlatformUrl` |
| `src/lib/recommendation.js` | Rule-based buying recommendation engine — 6-rule priority chain, locked output shape for Phase 3 ML upgrade, `VERDICT_CONFIG` visual map |
| `src/store/useAppStore.js` | Complete Zustand store — `userEmail`, `authToken` (persisted), `trackStep`, `previewResult`, `deleteTarget` (session-only) |
| `src/hooks/useItems.js` | `GET /v1/items` TanStack Query wrapper |
| `src/hooks/useDeleteSubscription.js` | `DELETE /v1/subscriptions/{id}` mutation with cache invalidation |
| `src/hooks/useProduct.js` | `GET /v1/products/{id}` TanStack Query wrapper |
| `src/hooks/useProductHistory.js` | `GET /v1/products/{id}/history` with graceful 404 fallback (endpoint not yet built) |
| `src/app/(app)/dashboard/page.jsx` | Dashboard page — email gate, items list, delete flow, refresh, switch email |
| `src/components/dashboard/ProductCard.jsx` | Tracked item card — image, name, platform badge, availability, price, offer price, rating, last-checked, remove + external link buttons |
| `src/components/dashboard/ProductCardSkeleton.jsx` | Animated loading placeholder |
| `src/components/dashboard/EmptyState.jsx` | Empty state with "Monitor Your First Item" CTA |
| `src/components/dashboard/DeleteDialog.jsx` | Delete confirmation modal — reads from Zustand store |
| `src/app/products/[slug]/page.jsx` | Product Detail page — two-column sticky layout, loading skeleton, error state |
| `src/components/product/Breadcrumb.jsx` | Breadcrumb nav with "← My Items" back link for logged-in users |
| `src/components/product/ProductHero.jsx` | Image gallery + identity + badges + spec chips |
| `src/components/product/KeySpecsGrid.jsx` | 2-column key spec table from `product_metadata.specs` |
| `src/components/product/PriceHistoryChart.jsx` | Recharts LineChart with period toggle; graceful empty state when endpoint absent |
| `src/components/product/OffersSection.jsx` | Bank offers from `offers` JSONB — normalises string and object offer shapes |
| `src/components/product/ProductDescription.jsx` | Description + features with show-more toggle |
| `src/components/product/FullSpecsTable.jsx` | Full spec table — handles both flat and grouped spec shapes |
| `src/components/product/SidebarPriceBox.jsx` | Price, MRP, offer price, availability, Buy button, Monitor CTA, refresh, share |
| `src/components/product/SidebarRecommendation.jsx` | Rule-based verdict card |
| `src/components/product/SidebarPriceStats.jsx` | All-time low/high/drops/tracked-since with range-gated badges |
| `src/components/product/TargetPriceInput.jsx` | Target price input — local state in Phase 1, PATCH endpoint stub |
| `src/components/product/MobileBottomBar.jsx` | Sticky mobile bottom bar — price + Buy + Monitor |

---

### Features

#### FEAT-001 — Dashboard Live Data Connection
- **File:** `src/app/(app)/dashboard/page.jsx`, `src/hooks/useItems.js`
- **Change:** Dashboard connects to `GET /v1/items?email=` and renders real tracked
  products. Email gate shows on first visit; `userEmail` persists to localStorage via
  Zustand so returning users skip the gate.
- **Verified:** 30 items loaded for test account with correct names, prices, images,
  offer prices, platform badges, and last-checked timestamps.

#### FEAT-002 — Delete Flow
- **File:** `src/components/dashboard/DeleteDialog.jsx`, `src/hooks/useDeleteSubscription.js`
- **Change:** Trash icon → Zustand `deleteTarget` → modal confirmation →
  `DELETE /v1/subscriptions/{id}?email=` → cache invalidation → Sonner toast.
  Cancel or Escape closes without action.

#### FEAT-003 — Product Detail Page
- **File:** `src/app/products/[slug]/page.jsx` + 14 component files
- **Change:** Full two-column sticky layout. In Phase 1 the `[slug]` param is the
  `product_id` UUID — slug column is a Phase 2 addition. Left column: Hero, KeySpecs,
  PriceHistory, Offers, Description, FullSpecs. Right sidebar (desktop): PriceBox,
  Recommendation, PriceStats, TargetPriceInput. Mobile: sidebar boxes appear inline,
  sticky MobileBottomBar at bottom.
- **Verified:** Product renders with real data from `GET /v1/products/{id}` including
  `product_metadata` fields (description, features, specs, category, brand) from v3.1.

#### FEAT-004 — Rule-Based Buying Recommendation
- **File:** `src/lib/recommendation.js`
- **Change:** 6-rule priority chain computing `buy/wait/high/neutral/insufficient`
  verdict from `price_stats`. Output shape is locked — Phase 3 swaps the local
  function call for a `GET /v1/products/{id}/recommendation` API call with no
  component changes required.

#### FEAT-005 — Breadcrumb Back Navigation
- **File:** `src/components/product/Breadcrumb.jsx`
- **Change:** Breadcrumb row has "← My Items" link on the right side, visible only
  when `userEmail` is in the Zustand store. Public visitors (arriving from Google)
  see only the category/brand breadcrumb trail. No browser back button dependency.

---

### Fixes

#### FIX-001 — `cn` Missing from `utils.js` — Landing Page Crash
- **File:** `src/lib/utils.js`
- **Symptom:** `TypeError: cn is not a function` in `Navbar.jsx` on every page load.
  Landing page returned 500.
- **Root cause:** The v4.0 session replaced the shadcn scaffold `utils.js` (which
  exports only `cn`) with PricePing utilities — but forgot to include `cn` itself.
  All shadcn components and `Navbar.jsx` import `cn` from `@/lib/utils`.
- **Fix:** Added `cn` using `clsx` + `tailwind-merge` at the top of `utils.js`.

#### FIX-002 — CORS Blocking All API Requests
- **File:** `app/main.py`
- **Symptom:** `ERR_FAILED 200 (OK)` — browser blocked responses from
  `localhost:8001` despite the backend returning 200.
- **Root cause:** `CORSMiddleware` was never added to the FastAPI app.
- **Fix:** Added `CORSMiddleware` with `allow_origins=["http://localhost:3000",
  "https://priceping.in"]` inside `create_app()`.

#### FIX-003 — `rating.toFixed is not a function`
- **Files:** `src/components/dashboard/ProductCard.jsx`,
  `src/components/product/ProductHero.jsx`
- **Symptom:** Runtime crash when rendering any item with a rating.
- **Root cause:** FastAPI returns `rating` and `review_count` as strings (Pydantic
  `Decimal` type serialised without coercion). `.toFixed()` and `.toLocaleString()`
  are number methods.
- **Fix:** Wrapped all rating/review_count usages with `Number()` before calling
  numeric methods.

#### FIX-004 — All-Time Low/High Badges Both Showing on Single Price Point
- **File:** `src/components/product/SidebarPriceStats.jsx`
- **Symptom:** Products with only one price recorded showed both ✅ Low and ❌ High
  badges simultaneously (all_time_low === all_time_high).
- **Fix:** Badges gated behind `hasRange` — only shown when
  `Number(all_time_low) < Number(all_time_high)`.

#### FIX-005 — Brand Language Violations
- **Files:** `src/components/product/SidebarPriceBox.jsx`,
  `src/components/product/MobileBottomBar.jsx`,
  `src/components/dashboard/EmptyState.jsx`
- **Change:** "Track · Get drop alerts" → "Monitor · Get drop pings",
  "Track this price" → "Monitor this price", "🔔 Track" → "🔔 Monitor",
  "Track Your First Item" → "Monitor Your First Item".

---

### Deviations from UI Design Document

#### DEV-001 — Product Page `[slug]` is `product_id` UUID in Phase 1
- **Original design:** `/products/{name-slugified}-{marketplace_product_id}`
- **Actual:** `/products/{product_id}` — UUID used as slug parameter
- **Reason:** `products.slug` column is a Phase 2 addition (requires Alembic
  migration + slug backfill). In Phase 1, `ProductCard` navigates to
  `/products/{product_id}` and the page reads `params.slug` as the product ID.
- **Impact:** URLs are not human-readable in Phase 1. No SEO impact — product page
  is a Client Component (not indexed) until Phase 2 ISR upgrade.

#### DEV-002 — TargetPriceInput Saves Locally Only in Phase 1
- **Original design:** `PATCH /v1/subscriptions/{id}` with `{ target_price }`
- **Actual:** Target price saved to local React state; Sonner toast confirms to user.
  No API call made.
- **Reason:** `PATCH /v1/subscriptions/{id}` endpoint not yet built (DEF-003).
- **Impact:** Target price resets on page refresh. Full persistence requires the
  backend endpoint.

---

### Configuration

#### CFG-001 — CORS Added to FastAPI
- **File:** `app/main.py`
- Added `CORSMiddleware` allowing `http://localhost:3000` (dev) and
  `https://priceping.in` (production). Resolves DEF-005 for local development.
  Production CORS is pre-configured for when DNS is pointed.

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | New FastAPI endpoints not yet implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp`, `products/{id}/history`, `products/{id}/track` | Before auth + history features go live |
| DEF-004 | `users.password_hash` Alembic migration not yet run | Before Profile page goes live |
| DEF-006 | Domain DNS not configured (`priceping.in` → Vercel, `api.priceping.in` → Railway) | Before production deploy |
| DEF-007 | `GET /v1/items` response has no `slug` field — product page navigation uses `product_id` UUID | Resolved in Phase 2 when slug column is added |
| DEF-008 | Rate limiting not added to FastAPI preview endpoint (`slowapi` — 30/hour) | Phase 2 |
| DEF-009 | TopDeals and PopularProducts sections (Phase 2) show placeholder in Phase 1 | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not yet built | When DEF-003 auth endpoints are implemented |
| DEF-011 | Price history chart shows empty state — `GET /v1/products/{id}/history` not yet built on FastAPI | Next session (FastAPI work) |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **`GET /v1/products/{id}/history`** | High | FastAPI endpoint returning `[{price, checked_at}]` with period filter (`1m/3m/6m/all`). Unlocks price history chart on product page. |
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **`PATCH /v1/subscriptions/{id}`** | Medium | Add `target_price` field — unlocks TargetPriceInput persistence |
| **Vercel deploy** | Medium | Connect GitHub repo, set `NEXT_PUBLIC_API_URL=https://api.priceping.in`, add custom domain |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Products slug column** | Low | Phase 2 — `products.slug` column + backfill + `GET /v1/products/by-slug/{slug}` endpoint |

---

*Archive this file to `docs/changelog/v4_1-dashboard-product-detail.md` when the next phase begins.*
