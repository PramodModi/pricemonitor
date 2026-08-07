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

## [v4.0] — Next.js Frontend Foundation + Landing Page — August 2026

This phase introduces the complete Next.js frontend (`priceping-ui/`) to replace the
existing Streamlit UI. The backend (FastAPI on Railway) is unchanged. The frontend is
deployed to Vercel at `priceping.in`.

**Scope of this phase:** Project scaffold, design system, all shared infrastructure
(lib, hooks, store, layout), and the complete Landing page (`/`). Dashboard, Track,
Profile, and Product Detail pages are scaffolded but not yet validated in production.

**Project renamed:** PriceMonitor / PriceWatch → **PricePing**. Domain: `priceping.in`.
API: `api.priceping.in`. Brand language updated throughout: "tracking" → "monitoring",
"alert/notify" → "ping".

---

### Summary of Changes

| Area | Change |
|---|---|
| `priceping-ui/` | New Next.js 15.3.5 project created at `code/priceping-ui/` |
| `package.json` | Next.js 15.3.5, React 19.1.0, Tailwind 3, Zustand 4, TanStack Query 5, Recharts 3, Axios 1, Lucide React, Sonner |
| `tailwind.config.js` | Custom design system: indigo primary, amber accent, Sora display font, Inter body font, custom shadows and animations |
| `globals.css` | Tailwind directives + Google Fonts import + full CSS component classes (`.btn-*`, `.card`, `.badge-*`, `.hero-input`, `.skeleton`, etc.) |
| `src/app/layout.jsx` | Root Server Component layout (Next.js 15 requirement) |
| `src/app/providers.jsx` | Client wrapper for QueryClient + Sonner Toaster (split from layout per Next.js 15) |
| `src/app/page.jsx` | Landing page — assembles 10 section components |
| `src/app/not-found.jsx` | Custom 404 page |
| `src/app/(app)/layout.jsx` | Route group layout wrapping Dashboard, Track, Profile in AppShell |
| `src/app/(app)/dashboard/page.jsx` | Dashboard page — email gate + items list + delete flow |
| `src/app/(app)/track/page.jsx` | Track page — Suspense wrapper (Next.js 15 useSearchParams requirement) |
| `src/app/(app)/track/TrackPageClient.jsx` | Track page client logic — 3-step state machine |
| `src/app/(app)/profile/page.jsx` | Profile page — account, notification prefs placeholder, danger zone |
| `src/components/layout/` | AppShell, Sidebar, TopBar, MobileNav |
| `src/components/landing/` | Navbar, HeroSection, TrustBar, CategoryPills, BankOffersRow, HowItWorks, RecommendationPreview, StatsSection, DealsPlaceholder, FooterCTA, Footer |
| `src/components/dashboard/` | ProductCard, ProductCardSkeleton, EmptyState, DeleteDialog |
| `src/components/track/` | UrlInputForm, PreviewCard, PreviewSkeleton, CatalogContext, SuccessScreen |
| `src/hooks/` | useItems, useProduct, useProductHistory, usePreview, useSubscribe, useDeleteSubscription, useTrackProduct, useAuthCheck, useLogin |
| `src/lib/api.js` | Axios instance with 35s timeout, JWT auth interceptor, error normalisation |
| `src/lib/errors.js` | API error code → user-facing message map |
| `src/lib/utils.js` | formatPrice, formatTimeAgo, formatDateIST, formatDateShort, slugify, getPlatformLabel/Icon/BadgeClass, isValidEmail, isSupportedPlatformUrl |
| `src/lib/recommendation.js` | Rule-based buying recommendation engine (Phase 1); locked output shape for Phase 3 ML upgrade |
| `src/store/useAppStore.js` | Zustand store: userEmail + authToken persisted to localStorage; trackStep, previewResult, deleteTarget session-only |
| `jsconfig.json` | `@/` path alias → `src/` |

---

### Features

#### FEAT-001 — Next.js 15 Project Scaffold
- **Location:** `code/priceping-ui/`
- **Stack:** Next.js 15.3.5, React 19.1.0, Tailwind CSS 3, shadcn/ui (Radix UI), Zustand 4, TanStack Query 5, Axios 1, Recharts 3, Lucide React 0.400, Sonner 1
- **Hosting:** Vercel (free tier). Auto-deploy on `git push` to `main`.
- **Rendering modes used:** SSG (Landing, Login), Client Component (Dashboard, Track, Profile), ISR planned for Phase 2 (Product pages, Offers, Coupons)

#### FEAT-002 — Custom Design System
- **Location:** `tailwind.config.js`, `src/app/globals.css`
- **Palette:** Deep indigo (`#4f46e5`) as primary (trust/intelligence), warm amber (`#f59e0b`) as accent (deal urgency/CTAs)
- **Typography:** Sora (display headlines), Inter (body). Both loaded from Google Fonts.
- **Signature element:** Hero URL input box with animated indigo border pulse on focus — the central design element of the landing page
- **CSS component classes:** `.btn-primary`, `.btn-accent`, `.btn-ghost`, `.btn-outline`, `.card`, `.hero-input`, `.badge-amazon/flipkart/myntra`, `.badge-in-stock/out-of-stock`, `.price-large/medium/strike/drop-badge`, `.skeleton`, `.section`, `.section-sm`

#### FEAT-003 — Global State (Zustand)
- **Location:** `src/store/useAppStore.js`
- **Persisted to localStorage:** `userEmail`, `authToken`
- **Session-only (reset on reload):** `trackStep`, `previewResult`, `deleteTarget`
- **Eliminates:** `st.session_state.view_product_id` — product ID now lives in the URL

#### FEAT-004 — API Client Layer
- **Location:** `src/lib/api.js`, `src/lib/errors.js`
- **Timeout:** 35 seconds (accommodates 10–20s Playwright scrape on preview endpoint)
- **Auth interceptor:** Attaches JWT as `Authorization: Bearer` when present in store
- **Error interceptor:** Maps HTTP status codes and API error codes to user-facing messages from `errors.js`

#### FEAT-005 — Rule-Based Buying Recommendation Engine
- **Location:** `src/lib/recommendation.js`
- **Input:** `price_stats` from `GET /v1/products/{id}`
- **Output shape is locked** — same interface when Phase 3 upgrades to ML API call
- **6 rules** evaluated in priority order: near all-time low → buy, >10% below avg → buy, near all-time high → high, frequent drops → wait, around average → neutral, insufficient data → insufficient

#### FEAT-006 — Landing Page (/)
- **Location:** `src/app/page.jsx` + `src/components/landing/`
- **Rendering:** SSG (no API calls, fully static in Phase 1)
- **10 sections:** Navbar, Hero (URL input box), TrustBar (4 stats), CategoryPills (9 scrollable categories), DealsPlaceholder (Phase 2 slot), BankOffersRow (5 static bank offer cards), HowItWorks (3-step explainer), RecommendationPreview (2 example verdict cards), StatsSection (3 metrics on dark background), FooterCTA (repeat URL input), Footer (3-column links + affiliate disclosure)
- **Hero design:** URL input box is the page hero — no carousel. Submit → `/track?url=...`
- **Returning user detection:** Navbar shows "My Items →" when `userEmail` in Zustand store

#### FEAT-007 — Dashboard (/dashboard)
- **Location:** `src/app/(app)/dashboard/page.jsx`
- **Rendering:** Client Component
- **Email gate:** Shows email input if no `userEmail` in store
- **Items list:** `ProductCard` with image, name, platform badge, availability, price, offer price, rating, last-checked time, remove button
- **Delete flow:** Zustand `deleteTarget` → `DeleteDialog` modal → `useDeleteSubscription` mutation → cache invalidation → Sonner toast
- **Loading state:** 3× `ProductCardSkeleton` animated placeholders
- **Empty state:** `EmptyState` component with CTA to `/track`

#### FEAT-008 — Track Page (/track)
- **Location:** `src/app/(app)/track/TrackPageClient.jsx`
- **Rendering:** Client Component (Suspense wrapper for `useSearchParams`)
- **5-state machine:** `input` → `loading` → `preview` → `confirming` → `success`
- **PreviewCard:** Shows scraped product data + `CatalogContext` (watcher count, drop count, all-time low, tracked-since) from `catalog_data`
- **Landing page integration:** `/track?url=...` pre-fills and auto-triggers the scrape

#### FEAT-009 — Profile Page (/profile)
- **Location:** `src/app/(app)/profile/page.jsx`
- **Sections:** Account (email display, set/change password), Notification preferences (placeholder for v3.x full implementation), Danger zone (delete account)

#### FEAT-010 — Shared Layout
- **AppShell:** Sidebar (desktop fixed) + TopBar + MobileNav (bottom tab bar on mobile) + health check banner
- **Sidebar:** Active link highlighting, user email at bottom, "Soon" badge on Phase 2 links
- **MobileNav:** Bottom tab bar with Lucide icons, hidden on desktop

---

### Deviations from UI Design Document

#### DEV-001 — Root Layout Split into layout.jsx + providers.jsx
- **Original design:** Single `layout.jsx` with `'use client'`
- **Actual:** Root `layout.jsx` is a Server Component (Next.js 15 requirement). `QueryClient` and `Toaster` moved to `providers.jsx` client wrapper.
- **Reason:** Next.js 15 requires the root layout to be a Server Component. `'use client'` on the root layout causes a build error.

#### DEV-002 — Track Page Split into page.jsx + TrackPageClient.jsx
- **Original design:** Single `track/page.jsx` with `useSearchParams()`
- **Actual:** `page.jsx` is a Suspense wrapper; `TrackPageClient.jsx` contains the actual logic
- **Reason:** Next.js 15 requires `useSearchParams()` to be wrapped in `<Suspense>`.

#### DEV-003 — Brand Language Updated Throughout
- **Original design docs:** "tracking", "alert/notify"
- **Actual:** "monitoring", "ping" — applied to all landing page copy
- **Reason:** Product decision. Better fits the brand name PricePing.

#### DEV-004 — Hero Headline Simplified
- **Original design:** "Smart price tracking for Amazon, Flipkart & Myntra"
- **Actual:** "Smart price monitoring — we ping you when prices drop"
- **Reason:** Removes platform names from headline (they appear in subheadline and category pills). Headline now leads with the value proposition and brand verb.

#### DEV-005 — DealsPlaceholder Added
- **Original design:** TopDeals and PopularProducts sections hidden in Phase 1
- **Actual:** Single `DealsPlaceholder` component shown in their place with a "Deal sections will appear here" message
- **Reason:** Better UX than a silent gap — communicates that live deals are coming.

---

### Configuration

#### CFG-001 — Environment Variables
- `.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8001`
- `.env.production`: `NEXT_PUBLIC_API_URL=https://api.priceping.in`
- Set `NEXT_PUBLIC_API_URL` in Vercel project settings for production deploy

#### CFG-002 — Image Domains
- **File:** `next.config.js`
- Whitelisted: `m.media-amazon.com`, `*.media-amazon.com`, `rukminim*.flixcart.com`, `assets.myntassets.com`, `*.flixcart.com`

#### CFG-003 — CORS Update Required on FastAPI
- Add `https://priceping.in` and `http://localhost:3000` to FastAPI `allow_origins`
- **Not yet done** — required before production deploy

---

### Fixes

#### FIX-001 — Smart Quote Syntax Error in RecommendationPreview.jsx
- **File:** `src/components/landing/RecommendationPreview.jsx`
- **Symptom:** Build error: `Expected ',' got 've'` at line 17
- **Root cause:** Curly apostrophe (`'`) in `we've` inside a single-quoted JS string. The file was generated with a Unicode smart quote which JSX parser treats as a string terminator.
- **Fix:** Changed surrounding quotes to double quotes: `"Near the lowest price we've ever recorded."`

#### FIX-002 — Rogue `{app` Directory Causing 404 on Root Route
- **Symptom:** `GET / 404` despite `src/app/page.jsx` existing
- **Root cause:** An earlier `mkdir` command with unescaped brace expansion created a directory literally named `{app` inside `src/`. Next.js file-system router was confused by this unexpected entry.
- **Fix:** `rm -rf "src/{app"` — deleted the rogue directory.

#### FIX-003 — `next: command not found` After node_modules Deletion
- **Symptom:** `npm run dev` fails with `sh: next: command not found`
- **Root cause:** `node_modules` deleted without running `npm install` again
- **Fix:** `npm install` reinstalls all dependencies including the `next` binary

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-002 | `src/app/products/[slug]/page.jsx` (Product Detail) not yet built | Next session |
| DEF-003 | New FastAPI endpoints not yet implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp`, `products/{id}/history`, `products/{id}/track` | Before Dashboard goes live |
| DEF-004 | `users.password_hash` Alembic migration not yet run | Before Profile page goes live |
| DEF-005 | CORS not updated on FastAPI for `priceping.in` | Before production deploy |
| DEF-006 | Domain DNS not configured (`priceping.in` → Vercel, `api.priceping.in` → Railway) | Before production deploy |
| DEF-007 | `GET /v1/items` response shape assumed — `slug`, `special_price`, `mrp` fields may need backend additions | Verify against actual API response |
| DEF-008 | Rate limiting not added to FastAPI preview endpoint (`slowapi` — 30/hour) | Phase 2 |
| DEF-009 | TopDeals and PopularProducts sections (Phase 2) show placeholder in Phase 1 | Phase 2 |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Dashboard validation** | High | Connect to live FastAPI backend, verify `GET /v1/items` response shape matches `ProductCard` props |
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **Product Detail page** | High | Two-column sticky layout — Hero, KeySpecs, PriceHistory chart, Offers, Description, FullSpecs, Sidebar (price box, recommendation, stats, target price) |
| **New FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **New FastAPI product endpoints** | High | `GET /v1/products/{id}/history`, `POST /v1/products/{id}/track` |
| **CORS update** | High | Add `priceping.in` to FastAPI `allow_origins` before any production testing |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Vercel deploy** | Medium | Connect GitHub repo, set `NEXT_PUBLIC_API_URL`, add custom domain |

---

*Archive this file to `docs/changelog/v4_0-nextjs-frontend.md` when the next phase begins.*
