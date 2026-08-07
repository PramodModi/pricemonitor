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

## [v4.3] — Track Flow Fixes + Navigation Shell + Landing Cleanup — August 2026

This phase fixes three bugs in the Track page flow discovered during end-to-end testing,
adds the missing `(app)` route group layout (which caused Sidebar and TopBar to never
render), completes the Navbar user dropdown, and cleans up the landing page for
production readiness.

**Scope of this phase:** Track page infinite loop fix, stale preview fix, subscription
status check fix, `amzn.in` URL validation fix, missing AppShell layout file created,
Sidebar Home link and Offers disabled state, TopBar dropdown, Navbar user dropdown with
switch email, Dashboard header cleanup, health check removed, landing page sections
hidden for Phase 1, Footer cleanup.

---

### Summary of Changes

| Area | Change |
|---|---|
| `src/app/(app)/layout.jsx` | **Created** — missing file that wires AppShell to the route group |
| `src/app/(app)/track/TrackPageClient.jsx` | Three bug fixes + useItems prefetch on mount |
| `src/components/track/PreviewCard.jsx` | isAlreadyTracking rewritten using useItems + isCheckingStatus guard |
| `src/lib/utils.js` | amzn.in short URL support added to isSupportedPlatformUrl |
| `src/components/layout/AppShell.jsx` | Health check removed (GET /v1/health returns 404) |
| `src/components/layout/Sidebar.jsx` | Home link added; Offers rendered as non-clickable div |
| `src/components/layout/TopBar.jsx` | Title fixed; email avatar opens dropdown with Switch email |
| `src/components/landing/Navbar.jsx` | User dropdown (State A/B); nav links disabled; Switch email navigates to /dashboard |
| `src/app/(app)/dashboard/page.jsx` | Header simplified — New item and Switch email buttons removed; subtitle shows count only |
| `src/app/page.jsx` | TrustBar, CategoryPills, DealsPlaceholder, BankOffersRow, StatsSection hidden |
| `src/components/landing/Footer.jsx` | Categories column removed; affiliate disclosure removed |

---

### Features

#### FEAT-001 — Missing `(app)` Route Group Layout Created
- **File:** `src/app/(app)/layout.jsx`
- **Change:** File was never created. Without it, Dashboard, Track, and Profile pages
  rendered with no AppShell — no Sidebar, TopBar, or MobileNav. Created a minimal
  Server Component that wraps children in `AppShell`.
- **Impact:** Sidebar, TopBar, and MobileNav now render on all app pages.

#### FEAT-002 — Sidebar Home Link + Offers Disabled
- **File:** `src/components/layout/Sidebar.jsx`
- **Change:** Home link added as first nav item (`href: '/'`, `icon: Home`). Exact-match
  active logic used for Home so it only highlights on `/` not all routes. Phase 2 items
  (`phase: 2`) now render as a non-clickable `<div>` with `cursor-not-allowed` instead
  of `<Link>` — Offers is visually present but cannot be clicked.

#### FEAT-003 — TopBar Email Dropdown
- **File:** `src/components/layout/TopBar.jsx`
- **Change:** Dashboard title corrected from "My Tracked Items" to "My Monitored Items".
  Email avatar in top-right is now a button that opens a dropdown with "Switch email".
  Click-outside closes the dropdown. Calling `setUserEmail(null)` returns the user to
  the email gate.

#### FEAT-004 — Navbar User Dropdown (State A / State B)
- **File:** `src/components/landing/Navbar.jsx`
- **Change:** Nav links (Deals, Coupons, Blog) rendered as non-clickable `<span>` with
  `cursor-not-allowed` and "Coming soon" tooltip. Right side has two states:
  - **State A** (no email): "Track a price →" button
  - **State B** (email stored): Avatar chip opens dropdown — My Items, Track new item,
    Set a password (with "Protect your dashboard" subtext), Switch email.
  Switch email calls `setUserEmail(null)` then `router.push('/dashboard')` so the user
  lands on the dashboard email gate rather than staying on the landing page. ChevronDown
  rotates when open. Mobile drawer mirrors the same options.

#### FEAT-005 — Dashboard Header Simplified
- **File:** `src/app/(app)/dashboard/page.jsx`
- **Change:** "New item" Link button removed (sidebar has Track Item). "Switch email"
  button removed (moved to TopBar dropdown). Email removed from subtitle — now shows
  "{count} items monitored". Only the Refresh button remains in the header actions area.
  Unused imports (`Link`, `PlusCircle`) cleaned up.

#### FEAT-006 — Landing Page Phase 1 Cleanup
- **File:** `src/app/page.jsx`
- **Change:** TrustBar, CategoryPills, DealsPlaceholder, BankOffersRow, StatsSection
  hidden. Landing page now renders: Hero → How it works → Recommendation preview →
  Footer CTA → Footer. These sections remain in `components/landing/` and will be
  re-enabled in Phase 2 when real data endpoints exist.

#### FEAT-007 — Footer Cleanup
- **File:** `src/components/landing/Footer.jsx`
- **Change:** "Categories" column removed (links to /offers?category= pages not yet built).
  Affiliate disclosure paragraph removed from the bottom bar. Footer grid updated from
  3 columns to 2 (PricePing + Track prices on). Copyright line retained.

---

### Fixes

#### FIX-001 — Track Page Infinite Loop on Scrape Failure
- **File:** `src/app/(app)/track/TrackPageClient.jsx`
- **Symptom:** When a URL failed to scrape, the page continuously retried the scrape
  without user action — visible as repeated `POST /v1/products/preview` calls in logs.
- **Root cause:** `initialUrl` was read directly from `searchParams` on every render.
  After a scrape failure, `onError` set `trackStep = 'input'`, causing `UrlInputForm`
  to re-mount. Its auto-submit `useEffect` saw the same non-empty `initialUrl` from
  `searchParams` and re-triggered the fetch — looping indefinitely.
- **Fix:** `initialUrl` moved into `useState` (reads `searchParams` only once on mount).
  `setInitialUrl('')` called inside `onSubmit` so re-mounts after failure see an empty
  string and the auto-submit does not re-fire.

#### FIX-002 — Stale Preview Showing on Re-visit
- **File:** `src/app/(app)/track/TrackPageClient.jsx`
- **Symptom:** Navigating back to the landing page and submitting a new URL from the
  hero input box caused the previous product's preview to flash briefly before the new
  one loaded.
- **Root cause:** `trackStep` and `previewResult` remained in Zustand from the previous
  session. When `TrackPageClient` re-mounted, `trackStep` was still `'preview'`, so the
  old product rendered immediately while the new fetch was still in-flight.
- **Fix:** `resetTrack()` called in `useEffect([])` on every mount of `TrackPageClient`.

#### FIX-003 — Loading Branch State Race
- **File:** `src/app/(app)/track/TrackPageClient.jsx`
- **Symptom:** After a scrape failure, the loading skeleton briefly showed instead of
  the error state.
- **Root cause:** Loading branch condition was `trackStep === 'loading' || isLoadingPreview`.
  TanStack Query's `isPending` stays `true` briefly after `onError` fires and sets
  `trackStep = 'input'`, causing the wrong branch to render.
- **Fix:** Loading branch now driven by `trackStep` only — `isLoadingPreview` removed
  from the condition entirely.

#### FIX-004 — `amzn.in` Short URLs Rejected by Frontend Validation
- **File:** `src/lib/utils.js`
- **Symptom:** Pasting `https://amzn.in/d/0dR9klG` into the track URL input showed
  "Only Amazon India, Flipkart, and Myntra URLs are supported."
- **Root cause:** `isSupportedPlatformUrl` checked `hostname.includes('amazon.in') &&
  (... || hostname.includes('amzn.in'))`. For `amzn.in` URLs, the outer `&&` condition
  fails immediately since `hostname` is `amzn.in` not `amazon.in`, so the `amzn.in`
  check inside is never reached.
- **Fix:** `isAmazonShort = hostname.includes('amzn.in')` extracted as a separate
  top-level condition. No path check — short URLs have unpredictable paths; the backend
  resolves the redirect authoritatively.

#### FIX-005 — `isAlreadyTracking` Wrong Signal in PreviewCard
- **File:** `src/components/track/PreviewCard.jsx`
- **Symptom:** For any product that existed in the DB (tracked by any user), the
  "Already tracking" banner and "View in dashboard →" button showed — preventing
  subscription even when the current user had never tracked the product.
- **Root cause:** `isAlreadyTracking` was computed from `!!catalog_data && email ===
  storedEmail`. `catalog_data` is present whenever the product exists in the DB for
  any user — it is not specific to the current user.
- **Fix:** `useItems(email)` called reactively inside `PreviewCard`. `isAlreadyTracking`
  now checks `itemsData?.items?.some(item => item.product.product_id === productId)` —
  mirrors Streamlit's `_is_already_tracking()` exactly.

#### FIX-006 — Wrong Button Flashing Before Subscription Check Completes
- **File:** `src/components/track/PreviewCard.jsx`
- **Symptom:** For existing products (PATH A, ~200ms), "Yes, track it" button showed
  briefly before "Already tracking" replaced it once `useItems` completed (~400-500ms).
- **Root cause:** `useItems` fetch completes after the preview renders, so on first
  render `itemsData` is undefined and `isAlreadyTracking = false`.
- **Fix:** `isCheckingStatus = !!productId && hasValidEmail && isCheckingSubscription`
  computed from `isLoading` returned by `useItems`. While checking, a disabled "Checking…"
  spinner button is shown — neither "Yes, track it" nor "Already tracking" appears until
  the correct state is known. For new products (`productId = null`), `isCheckingStatus`
  is always `false` — button shows immediately.

#### FIX-007 — Health Check Calling Non-existent Endpoint
- **File:** `src/components/layout/AppShell.jsx`
- **Symptom:** `GET /v1/health` returning 404 on every page load; warning banner
  "PricePing is experiencing issues" always showing.
- **Root cause:** `GET /v1/health` endpoint does not exist on the FastAPI backend.
- **Fix:** Health check `useEffect`, `apiDown` state, warning banner, and `api` import
  all removed from `AppShell`. Re-enable when `/v1/health` is implemented.

---

### Deviations from UI Design Document

#### DEV-001 — Product Page `[slug]` is `product_id` UUID in Phase 1
- Carried forward from v4.1 — unchanged.

#### DEV-002 — TargetPriceInput Saves Locally Only in Phase 1
- Carried forward from v4.1 — unchanged.

#### DEV-003 — Landing Page Sections Deferred to Phase 2
- **Original design:** TrustBar, CategoryPills, BankOffersRow, StatsSection shown in
  Phase 1 with static data.
- **Actual:** All four sections hidden. Static numbers were directionally inaccurate
  for a new deployment. Will be re-enabled with real DB-driven data in Phase 2.

#### DEV-004 — Navbar State C (JWT / password user) Deferred
- **Original design:** Full auth flow in Phase 1 including JWT dropdown state.
- **Actual:** State B (email-only) implemented. State C (JWT) deferred to when
  `auth/check`, `auth/login` endpoints are built (DEF-003).

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not yet implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp`, `products/{id}/track` | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not yet run | Before Profile page goes live |
| DEF-006 | Domain DNS not configured (`priceping.in` → Vercel, `api.priceping.in` → Railway) | Before production deploy |
| DEF-007 | `GET /v1/items` response has no `slug` field — product page navigation uses UUID | Phase 2 slug column |
| DEF-008 | Rate limiting not added to FastAPI preview endpoint (`slowapi` — 30/hour) | Phase 2 |
| DEF-009 | Footer "Track prices on" links point to `/offers?platform=` pages not yet built | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not yet built | When auth endpoints are implemented |
| DEF-011 | `/v1/health` endpoint not implemented — AppShell health check disabled | When endpoint is added to FastAPI |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **`GET /v1/products` listing endpoint** | High | Public endpoint returning all products filterable by platform. Powers `/offers` page and Footer platform links. |
| **`/offers` page** | High | Public product listing page with platform filter tabs. Track button with subscription state detection. |
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **`PATCH /v1/subscriptions/{id}`** | Medium | Add `target_price` field — unlocks TargetPriceInput persistence |
| **`GET /v1/health`** | Medium | Add health endpoint to FastAPI — re-enables AppShell health check |
| **Vercel deploy** | Medium | Connect GitHub repo, set `NEXT_PUBLIC_API_URL=https://api.priceping.in`, add custom domain |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Products slug column** | Low | Phase 2 — `products.slug` column + backfill + `GET /v1/products/by-slug/{slug}` |

---

*Archive this file to `docs/changelog/v4_3-track-flow-fixes-navigation.md` when the next phase begins.*
