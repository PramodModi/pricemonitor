# PricePing — UI Design Document

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Version     | 1.1                                        |
| Status      | Approved — reference document              |
| Date        | August 2026                                |
| Project     | PricePing (formerly PriceWatch/PriceMonitor)|
| Domain      | priceping.in                               |
| Author      | Pramod Modi                                |
| Depends on  | API Specification v3.0, SAD v1.0, LLD v3.2 |
| Changes in v1.1 | Landing page fully redesigned (10 sections, affiliate-ready). Product page restructured to two-column layout with sticky sidebar. Breadcrumb navigation replaces browser back-button dependency. New components: `Breadcrumb.jsx`, `ProductSidebar.jsx`, `TargetPriceInput.jsx`, `KeySpecsGrid.jsx`, `FullSpecsTable.jsx`. Landing page sections documented in detail. Navigation model clarified. |

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Authentication System](#4-authentication-system)
5. [Route Map and Rendering Strategy](#5-route-map-and-rendering-strategy)
6. [File and Folder Structure](#6-file-and-folder-structure)
7. [Global State Management](#7-global-state-management)
8. [API Client Layer](#8-api-client-layer)
9. [Page: Landing (/)](#9-page-landing-)
10. [Page: Dashboard (/dashboard)](#10-page-dashboard-dashboard)
11. [Page: Track New Item (/track)](#11-page-track-new-item-track)
12. [Page: Product Detail (/products/[slug])](#12-page-product-detail-productsslug)
13. [Page: Offers (/offers)](#13-page-offers-offers)
14. [Page: Coupons (/coupons)](#14-page-coupons-coupons)
15. [Page: Blog (/blog and /blog/[slug])](#15-page-blog-blog-and-blogslug)
16. [Page: Profile (/profile)](#16-page-profile-profile)
17. [Page: Login (/login)](#17-page-login-login)
18. [Shared Layout Components](#18-shared-layout-components)
19. [Shared UI Components](#19-shared-ui-components)
20. [AI Buying Recommendation — Design Contract](#20-ai-buying-recommendation--design-contract)
21. [Navigation Model — No Browser Back Button Dependency](#21-navigation-model--no-browser-back-button-dependency)
22. [Error Handling](#22-error-handling)
23. [Hosting and Deployment](#23-hosting-and-deployment)
24. [New Database Columns Required](#24-new-database-columns-required)
25. [New FastAPI Endpoints Required](#25-new-fastapi-endpoints-required)
26. [Phase Summary](#26-phase-summary)
27. [Design Decisions and Rationale](#27-design-decisions-and-rationale)

---

## 1. Purpose and Scope

This document is the single authoritative reference for the PricePing frontend. It covers
every page, every component, every API call, every rendering strategy, and every phase of
development. It is written to be unambiguous — any developer reading this document should
be able to build any part of the UI without needing to ask questions or infer intent.

### What this document covers
- Technology choices and the reasoning behind each one
- The complete Next.js application structure
- All pages across all three development phases
- The product detail page in full detail including all future features
- The authentication model (progressive auth — optional password)
- The AI buying recommendation design contract (rule-based now, ML later)
- Hosting, DNS, and deployment setup
- All new FastAPI endpoints and database columns the frontend requires

### What this document does not cover
- FastAPI backend internals (see API Specification v3.0)
- Scraper implementation (see LLD v3.2)
- Database schema in full (see SAD v1.0)
- Email templates (see Email Template Design Spec)

### Relationship to the existing Streamlit UI Design document
The existing `Streamlit_UI_Design.md` is superseded by this document for all UI decisions
from this point forward. The Streamlit app (`streamlit_app/`) remains in the repository
and continues to function until the Next.js frontend is fully deployed and validated.
Migration is additive — the backend does not change.

---

## 2. Technology Stack

### Frontend

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Framework | Next.js | 14 | App Router, SSG, ISR, SSR, Client Components |
| Language | JavaScript (JSX) | ES2022+ | No TypeScript in initial phases — added later if needed |
| Styling | Tailwind CSS | 3 | Utility-first responsive layout and spacing |
| Component library | shadcn/ui | Latest | Cards, dialogs, skeletons, badges, accordions, carousels, toasts |
| Data fetching | TanStack Query | 5 | Server state, caching, loading/error states, background refetch |
| HTTP client | Axios | 1 | Configured instance with base URL and interceptors |
| Global state | Zustand | 4 | Minimal client state — email, track step, preview result |
| Charts | Recharts | 2 | Price history line chart, prediction overlay |
| Icons | Lucide React | 0.400 | Consistent icon set used throughout |
| Toast notifications | Sonner | 1 | Success/error toasts — part of shadcn ecosystem |
| Hosting | Vercel | — | Free tier. Auto-deploy on git push. SSG and ISR natively supported |

### Backend (unchanged — reference only)

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI | Railway. No changes required for Phase 1 |
| Database | PostgreSQL (Supabase) | No changes required for Phase 1 |
| Scraping | Playwright + ScraperAPI | No changes |
| Email | SendGrid | No changes |
| Scheduler | GitHub Actions | No changes |

### Why Next.js over plain React + Vite

Plain React (SPA) cannot be indexed by search engines. For PricePing, the following
features require server-side or statically-rendered HTML to function correctly:

- `priceping.in/products/iphone-17-pro` — Google must index this with product name and
  price for organic search traffic
- `priceping.in/offers` — a publicly discoverable deals page
- `priceping.in/blog/best-phones-under-20000` — content marketing, fully indexed
- WhatsApp/Telegram link previews — require OG tags in server-rendered HTML
- Affiliate link attribution — links must be in crawlable HTML

The dashboard, track, and profile pages are pure Client Components and feel identical to
writing plain React. The difference becomes visible only when Phase 2 public pages are
added — and because the codebase is Next.js from the start, those pages are added as new
files with no migration.

### Why shadcn/ui over MUI or Ant Design

shadcn/ui components are copied into `src/components/ui/` at install time. You own the
source code. There is no black-box npm package to fight when overriding styles. Adding a
new component (e.g. carousel) runs `npx shadcn@latest add carousel`, which drops the code
into your project. All components are built on Radix UI primitives — accessible, keyboard
navigable, and focus-trapped by default.

### Why Zustand over Redux or React Context

Zustand is a 1KB library with no boilerplate. Any component imports `useAppStore` and
reads or writes state in one line. No Provider wrappers, no reducers, no action creators.
For an application of this size, Redux is significant overhead with no benefit.

---

## 3. Architecture Overview

```
Browser
  │
  ├── Next.js App (Vercel — priceping.in)
  │     ├── Static pages (SSG): Landing, Login, Blog posts
  │     ├── ISR pages: Products/[slug], Offers, Coupons  ← rebuilt every N minutes
  │     └── Client Components: Dashboard, Track, Profile  ← call FastAPI directly
  │
  └── FastAPI Backend (Railway — api.priceping.in)
        └── PostgreSQL (Supabase)
```

**Data flow for Client Component pages (Dashboard, Track, Profile):**
```
User action → React state update → TanStack Query → Axios → FastAPI → PostgreSQL
                                         ↑
                              Cached response served instantly on repeat calls
                              Background refetch keeps data fresh
```

**Data flow for ISR pages (Products, Offers, Coupons):**
```
Vercel build / revalidation → Next.js server → FastAPI → PostgreSQL
                                    ↓
                             Pre-rendered HTML served to all visitors
                             Rebuilt every N minutes in background
```

**Key architectural constraint (unchanged from v3.2):**
The `scraper_v2` module remains self-contained on the backend. The frontend never calls
scraper internals directly. All frontend interactions go through FastAPI endpoints.

---

## 4. Authentication System

### 4.1 Design Philosophy — Progressive Auth

Authentication is optional and progressive. A user can track products using only their
email address. They may optionally set a password to protect their dashboard. This design
removes the friction of forced registration while allowing users who want privacy to
secure their account.

There are no redirect walls on public pages. The product page is accessible to everyone.
Auth state controls which sections and actions are available on each page — not whether
the page loads.

### 4.2 Three User States

| State | DB condition | How they access dashboard | What they can do |
|---|---|---|---|
| **Public visitor** | No user record | N/A | View all public pages, product pages, offers, blog |
| **Email-only user** | `users.password_hash IS NULL` | Enter email → loads immediately | Track products, view dashboard, set target price |
| **Password user** | `users.password_hash IS NOT NULL` | Enter email → password prompt appears | All of above, dashboard protected from others |

### 4.3 Auth Flow on Dashboard

```
User enters email in dashboard
          │
          ▼
GET /v1/auth/check?email=user@example.com
          │
          ├── { requires_password: false }
          │         → Load dashboard immediately
          │
          └── { requires_password: true }
                    → Show password field
                    → POST /v1/auth/login { email, password }
                              │
                              ├── 200 OK → JWT stored in Zustand + localStorage
                              │            → Load dashboard with JWT in headers
                              └── 401 → Show "Incorrect password" error
```

### 4.4 JWT Token Handling

- JWT issued by `POST /v1/auth/login`
- Stored in Zustand store (`authToken`) and persisted to `localStorage`
- Attached by Axios request interceptor as `Authorization: Bearer <token>` on all
  requests that require auth
- Token expiry: 7 days. On 401 from any authenticated endpoint, clear token and
  redirect to dashboard with email pre-filled
- For email-only users (no password), no JWT is issued — email is passed as a query
  parameter as per current API design

### 4.5 Setting a Password (Profile Page)

A user who has never set a password can do so from the Profile page. The flow:

1. User enters desired password (+ confirmation)
2. Frontend calls `POST /v1/auth/set-password` with `{ email, new_password, otp }`
3. Backend sends a one-time code to the email address (via SendGrid — already on stack)
4. User enters OTP — backend verifies and sets `password_hash = bcrypt(new_password)`
5. From this point forward, the dashboard requires password on login

Changing an existing password requires the current password, not OTP.

### 4.6 What Auth Does NOT Require

- No Supabase Auth in Phase 1 or Phase 2
- No OAuth (Google/GitHub login) until Phase 3 if ever needed
- No session cookies — stateless JWT only
- No server-side session storage

### 4.7 New Database Column for Auth

```sql
ALTER TABLE users ADD COLUMN password_hash TEXT;  -- NULL = no password set
```

This is a single Alembic migration. All existing users have `password_hash = NULL` and
are unaffected — their dashboard continues to work by email-only as before.

---

## 5. Route Map and Rendering Strategy

### 5.1 Rendering Mode Definitions

| Mode | What it means | When used |
|---|---|---|
| **SSG** (Static Site Generation) | HTML built at deploy time, served as static file | Pages with no dynamic data or data that never changes |
| **ISR** (Incremental Static Regeneration) | HTML pre-built, rebuilt in background every N minutes | Pages with data that changes periodically (prices, offers) |
| **SSR** (Server Side Rendering) | HTML built fresh on every request | Not used in Phase 1 or 2 |
| **CC** (Client Component) | Rendered in the browser, calls FastAPI directly | Auth-required pages, interactive state machines |

### 5.2 Complete Route Table

| URL | File | Mode | Phase | Notes |
|---|---|---|---|---|
| `priceping.in/` | `app/page.jsx` | SSG | P1 | Landing page. No user data. Google-indexed. |
| `priceping.in/dashboard` | `app/(app)/dashboard/page.jsx` | CC | P1 | Requires email. Calls `GET /v1/items`. |
| `priceping.in/track` | `app/(app)/track/page.jsx` | CC | P1 | 3-step state machine. |
| `priceping.in/login` | `app/login/page.jsx` | SSG | P1 | Static shell. Supabase/bcrypt runs client-side. |
| `priceping.in/profile` | `app/(app)/profile/page.jsx` | CC | P1 | Notification prefs, password setting. |
| `priceping.in/products/[slug]` | `app/products/[slug]/page.jsx` | ISR 60m | P2 | Public product page. Google-indexed. OG image. |
| `priceping.in/offers` | `app/offers/page.jsx` | ISR 30m | P2 | Top price drops. Organic search traffic. |
| `priceping.in/coupons` | `app/coupons/page.jsx` | ISR 30m | P2 | Bank offers / coupon listing. |
| `priceping.in/blog` | `app/blog/page.jsx` | SSG | P3 | Blog index. MDX-driven. |
| `priceping.in/blog/[slug]` | `app/blog/[slug]/page.jsx` | SSG | P3 | Individual blog posts from MDX files. |

### 5.3 The `(app)` Route Group

The folder `app/(app)/` uses Next.js route groups. Parentheses mean the folder name does
not appear in the URL — it exists only to share a layout. All pages inside `(app)/` share
the `AppShell` layout (sidebar navigation + top bar). Pages outside this group (landing,
login, blog) have their own minimal layouts.

`app/(app)/dashboard/page.jsx` resolves to `priceping.in/dashboard` — not
`priceping.in/app/dashboard`.

---

## 6. File and Folder Structure

```
priceping-ui/
│
├── next.config.js              ← image domains (media-amazon.com, etc), env vars
├── tailwind.config.js          ← custom colours, font, breakpoints
├── .env.local                  ← NEXT_PUBLIC_API_URL=http://localhost:8001
├── .env.production             ← NEXT_PUBLIC_API_URL=https://api.priceping.in
├── package.json
│
└── src/
    │
    ├── app/                             ← Next.js App Router root
    │   ├── layout.jsx                   ← Root layout: <html>, fonts, QueryProvider, Toaster
    │   ├── page.jsx                     ← priceping.in/ (Landing — SSG)
    │   ├── globals.css                  ← Tailwind @base @components @utilities
    │   ├── not-found.jsx                ← Custom 404
    │   │
    │   ├── (app)/                       ← Route group — shares AppShell layout
    │   │   ├── layout.jsx               ← AppShell: Sidebar + TopBar + {children}
    │   │   ├── dashboard/
    │   │   │   └── page.jsx             ← /dashboard (CC)
    │   │   ├── track/
    │   │   │   └── page.jsx             ← /track (CC)
    │   │   └── profile/
    │   │       └── page.jsx             ← /profile (CC)
    │   │
    │   ├── login/
    │   │   └── page.jsx                 ← /login (SSG shell)
    │   │
    │   ├── products/                    ← Phase 2
    │   │   └── [slug]/
    │   │       ├── page.jsx             ← /products/[slug] (ISR 60m)
    │   │       └── opengraph-image.jsx  ← Auto OG image with name + price
    │   │
    │   ├── offers/                      ← Phase 2
    │   │   └── page.jsx                 ← /offers (ISR 30m)
    │   │
    │   ├── coupons/                     ← Phase 2
    │   │   └── page.jsx                 ← /coupons (ISR 30m)
    │   │
    │   ├── blog/                        ← Phase 3
    │   │   ├── page.jsx                 ← /blog index (SSG)
    │   │   └── [slug]/
    │   │       └── page.jsx             ← /blog/[slug] (SSG from MDX)
    │   │
    │   └── sitemap.js                   ← Phase 2: auto-generated from products table
    │
    ├── components/
    │   │
    │   ├── layout/
    │   │   ├── AppShell.jsx             ← Sidebar + TopBar + page content area
    │   │   ├── Sidebar.jsx              ← Nav links: Dashboard / Track / Offers / Profile
    │   │   ├── TopBar.jsx               ← Logo, mobile hamburger, user email display
    │   │   └── MobileNav.jsx            ← Bottom nav bar on mobile
    │   │
    │   ├── landing/                     ← Landing page sections (app/page.jsx imports these)
    │   │   ├── Navbar.jsx               ← Shared with product page — logo, nav links, CTA
    │   │   ├── HeroSection.jsx          ← URL input box + headline + trust chips
    │   │   ├── TrustBar.jsx             ← Social proof numbers (static P1, DB-driven P2)
    │   │   ├── CategoryPills.jsx        ← Horizontal scrollable category links
    │   │   ├── TopDeals.jsx             ← Phase 2: today's biggest drops with platform tabs
    │   │   ├── PopularProducts.jsx      ← Phase 2: most watched products grid
    │   │   ├── BankOffersRow.jsx        ← Horizontal scroll offer cards from DB
    │   │   ├── HowItWorks.jsx           ← 3-step static explainer
    │   │   ├── RecommendationPreview.jsx← Static example buy/wait verdict cards
    │   │   ├── StatsSection.jsx         ← 3 metric tiles (static P1, DB-driven P2)
    │   │   ├── BlogPreview.jsx          ← Phase 3: 3 MDX blog post cards
    │   │   ├── FooterCTA.jsx            ← Repeats URL input at bottom of page
    │   │   └── Footer.jsx               ← 3-column links + affiliate disclosure
    │   │
    │   │
    │   ├── dashboard/
    │   │   ├── ProductCard.jsx          ← Tracked item card with remove button
    │   │   ├── ProductCardSkeleton.jsx  ← Animated loading placeholder
    │   │   ├── EmptyState.jsx           ← "No tracked items" with CTA
    │   │   └── DeleteDialog.jsx         ← shadcn AlertDialog confirmation modal
    │   │
    │   ├── track/
    │   │   ├── UrlInputForm.jsx         ← Step 1: URL input + Fetch button
    │   │   ├── PreviewCard.jsx          ← Step 2: Product preview with catalog context
    │   │   ├── CatalogContext.jsx       ← Watcher count / drop count / all-time low section
    │   │   ├── PreviewSkeleton.jsx      ← Animated skeleton during 10–20s scrape
    │   │   └── SuccessScreen.jsx        ← Step 3: Tracking confirmed
    │   │
    │   ├── product/
    │   │   ├── Breadcrumb.jsx           ← Home → Category → Brand → Product nav (no back button)
    │   │   ├── ProductHero.jsx          ← Image gallery + name, brand, badges, spec chips
    │   │   ├── KeySpecsGrid.jsx         ← 2-column key spec table from product_metadata.specs
    │   │   ├── PriceHistoryChart.jsx    ← Recharts LineChart with period toggle
    │   │   ├── PlatformComparison.jsx   ← Phase 2: cross-platform price table
    │   │   ├── OffersSection.jsx        ← Bank offers from offers JSONB — inline cards
    │   │   ├── ProductDescription.jsx   ← Description paragraph + features bulleted list
    │   │   ├── FullSpecsTable.jsx       ← All specs grouped by category, collapsible
    │   │   ├── SimilarProducts.jsx      ← Phase 2: horizontal scroll carousel from DB
    │   │   ├── ProductSidebar.jsx       ← Right column wrapper (sticky, position: sticky)
    │   │   ├── SidebarPriceBox.jsx      ← Price, MRP, buy btn, track CTA, refresh, share
    │   │   ├── SidebarRecommendation.jsx← AI verdict card in sidebar
    │   │   ├── SidebarPriceStats.jsx    ← All-time low/high/drops/tracked-since box
    │   │   ├── TargetPriceInput.jsx     ← Target price input + Set button
    │   │   ├── MobileBottomBar.jsx      ← Mobile: sticky bottom bar (price + buy + track)
    │   │   └── MiniProductCard.jsx      ← Phase 2: compact card used in similar carousel
    │   │
    │   ├── offers/                      ← Phase 2
    │   │   ├── OfferCard.jsx
    │   │   └── OfferCardSkeleton.jsx
    │   │
    │   └── ui/                          ← shadcn auto-generated — DO NOT edit manually
    │       ├── button.jsx
    │       ├── card.jsx
    │       ├── dialog.jsx               ← Delete confirmation popup
    │       ├── alert-dialog.jsx
    │       ├── skeleton.jsx             ← Loading placeholders
    │       ├── badge.jsx                ← In Stock / platform / discount tags
    │       ├── sonner.jsx               ← Toast notifications
    │       ├── accordion.jsx            ← Offers / specs collapsible sections
    │       ├── carousel.jsx             ← Similar products / image gallery
    │       ├── separator.jsx
    │       ├── input.jsx
    │       └── label.jsx
    │
    ├── hooks/                           ← TanStack Query wrappers (one per API endpoint)
    │   ├── useItems.js                  ← GET /v1/items
    │   ├── useProduct.js                ← GET /v1/products/:id
    │   ├── useProductHistory.js         ← GET /v1/products/:id/history
    │   ├── useProductCompare.js         ← GET /v1/products/:id/compare (Phase 2)
    │   ├── useSimilarProducts.js        ← GET /v1/products/:id/similar (Phase 2)
    │   ├── usePreview.js                ← POST /v1/products/preview (mutation)
    │   ├── useSubscribe.js              ← POST /v1/subscriptions (mutation)
    │   ├── useTrackProduct.js           ← POST /v1/products/:id/track (mutation)
    │   ├── useDeleteSubscription.js     ← DELETE /v1/subscriptions/:id (mutation)
    │   ├── useAuthCheck.js              ← GET /v1/auth/check
    │   └── useLogin.js                  ← POST /v1/auth/login (mutation)
    │
    ├── lib/
    │   ├── api.js                       ← Axios instance: baseURL, auth interceptor, error interceptor
    │   ├── errors.js                    ← Error code → user-facing message map
    │   ├── recommendation.js            ← computeRecommendation(priceStats) → verdict object
    │   └── utils.js                     ← formatPrice, formatTimeAgo, formatDate (IST), slugify
    │
    ├── store/
    │   └── useAppStore.js               ← Zustand store: userEmail, authToken, trackStep,
    │                                       previewResult, deleteTarget
    │
    └── content/                         ← Phase 3
        └── blog/
            ├── best-phones-under-20000.mdx
            └── when-to-buy-iphone.mdx
```

---

## 7. Global State Management

### 7.1 Zustand Store — `src/store/useAppStore.js`

All client-side global state lives in a single Zustand store. This replaces every
`st.session_state` key from the Streamlit implementation.

| Key | Type | Persisted | Description |
|---|---|---|---|
| `userEmail` | `string \| null` | `localStorage` | Email entered by user. Survives page refresh. |
| `authToken` | `string \| null` | `localStorage` | JWT for password-protected accounts. `null` for email-only users. |
| `trackStep` | `"input" \| "preview" \| "success"` | No | Current step in Track page state machine. Resets on navigate. |
| `previewResult` | `object \| null` | No | Full response from `POST /v1/products/preview`. Cleared on confirm or back. |
| `deleteTarget` | `object \| null` | No | `{ subscriptionId, productName }` when delete dialog is open. `null` = dialog closed. |

### 7.2 Mapping from Streamlit `session_state`

| Streamlit key | Zustand equivalent | Change |
|---|---|---|
| `user_email` | `userEmail` | Same purpose. Now persisted to localStorage. |
| `track_step` | `trackStep` | Same values: `"input"`, `"preview"`, `"success"`. |
| `preview_result` | `previewResult` | Same object shape from API. |
| `delete_confirm` | `deleteTarget` | Renamed for clarity. Same purpose. |
| `view_product_id` | — | **Eliminated.** Product ID now lives in the URL as `/products/[slug]`. No session state needed. |

### 7.3 Server State — TanStack Query

All data fetched from the FastAPI backend is server state managed by TanStack Query.
Server state is never stored in Zustand. The distinction:

- **Zustand** = UI state that belongs to the user's session (email, auth token, current step)
- **TanStack Query** = data fetched from the server (product list, product detail, price history)

TanStack Query handles: loading states, error states, background refetch, cache
invalidation, and retry on failure. Components receive `{ data, isLoading, isError,
refetch }` from hooks and render accordingly.

---

## 8. API Client Layer

### 8.1 Axios Instance — `src/lib/api.js`

```js
import axios from 'axios'
import { useAppStore } from '@/store/useAppStore'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 35000,   // 35s — preview endpoint runs a live Playwright scrape (10–20s)
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT to every request when user has one
api.interceptors.request.use((config) => {
  const token = useAppStore.getState().authToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Map HTTP errors to error code strings consumed by components
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const code = error.response?.data?.error?.code ?? 'CONNECTION_ERROR'
    return Promise.reject({ code, message: ERROR_MESSAGES[code] ?? 'Something went wrong.' })
  }
)

export default api
```

### 8.2 Error Code Map — `src/lib/errors.js`

Directly mirrors `USER_FACING_ERRORS` from the Streamlit `api_client.py`.

| Code | User-facing message |
|---|---|
| `INVALID_URL` | That URL doesn't look like a product page. Use a direct product URL from Amazon, Flipkart, or Myntra. |
| `UNSUPPORTED_PLATFORM` | Only Amazon India, Flipkart, and Myntra are supported right now. |
| `SCRAPE_FAILED` | Couldn't fetch product details. Please check the URL and try again. |
| `SCRAPE_BLOCKED` | The marketplace blocked our request. Try again in a few minutes. |
| `PREVIEW_NOT_FOUND` | Your preview expired. Please search for the product again. |
| `SUBSCRIPTION_NOT_FOUND` | That item wasn't found in your list. |
| `INVALID_EMAIL` | Please enter a valid email address. |
| `PRODUCT_NOT_FOUND` | Product not found. |
| `CONNECTION_ERROR` | Cannot reach the server. Check your connection. |
| `TIMEOUT` | The request timed out. Please try again. |
| `UNAUTHORIZED` | Session expired. Please log in again. |

### 8.3 Timeout Rationale

The `POST /v1/products/preview` endpoint triggers a live Playwright scrape which can take
10–20 seconds depending on portal and proxy. The Axios timeout is set to 35 seconds to
comfortably accommodate this. All other endpoints respond in under 2 seconds. The same
35-second timeout applies to all requests for simplicity.

### 8.4 Utility Functions — `src/lib/utils.js`

| Function | Input | Output | Notes |
|---|---|---|---|
| `formatPrice(n)` | `67999` | `"₹67,999"` | Indian number formatting with ₹ symbol |
| `formatTimeAgo(isoStr)` | ISO timestamp | `"2h ago"`, `"3d ago"` | IST-aware relative time |
| `formatDateIST(isoStr)` | ISO timestamp | `"14 Aug 2026, 10:30 AM"` | Full IST formatted date |
| `formatDateShort(isoStr)` | ISO timestamp | `"14 Aug"` | Chart axis labels |
| `slugify(name, id)` | `"Apple iPhone 15", "B0CHX"` | `"apple-iphone-15-B0CHX"` | URL slug generation |
| `getPlatformLabel(platform)` | `"amazon"` | `"Amazon India"` | Display name |
| `getPlatformIcon(platform)` | `"flipkart"` | `"🛍️"` | Emoji icon |

---

## 9. Page: Landing (/)

### Phase: 1 (core) → Phase 2 (deals + popular products) → Phase 3 (blog) | Rendering: SSG / ISR per section

### Purpose
Public-facing home page. Serves three audiences simultaneously: first-time visitors
discovering PricePing, returning users checking today's deals, and public visitors
arriving from Google or a shared product link. Must load instantly, clearly explain the
product's value, and surface live deal content that drives affiliate clicks.

The landing page is designed to be extensible. Each section below is an independent
component — new sections (flash sales, top brands, curated collections) can be inserted
between any existing sections without redesigning the page.

### Navigation bar

The navbar appears on the landing page and on the product detail page. It is the same
`Navbar.jsx` component used across both pages.

Contents:
- Left: PricePing logo — links to `/`
- Centre: navigation links — Deals (`/offers`), Coupons (`/coupons`), Blog (`/blog`)
- Right: "Track a price" CTA button → `/track`

On mobile: logo left, hamburger right. Tapping hamburger opens a full-screen drawer with
all nav links. "Track a price" remains visible as a fixed bottom button on mobile.

If `userEmail` exists in Zustand (returning user), the right side shows "My Items →"
linking to `/dashboard` instead of "Track a price".

### Section 1 — Hero (Phase 1 · SSG)

The URL input box is the hero. No rotating banner or carousel. One clear value
proposition, one action.

Layout:
```
┌──────────────────────────────────────────────────┐
│  🔔 Never miss a price drop                       │  ← tag pill
│                                                  │
│  Smart price tracking for                        │  ← h1
│  Amazon, Flipkart & Myntra                       │
│                                                  │
│  Paste any product URL. We track the price and   │  ← subheadline
│  alert you the moment it drops.                  │
│                                                  │
│  ┌────────────────────────────────┐ [Track price]│  ← URL input + button
│  │ Paste Amazon, Flipkart URL...  │              │
│  └────────────────────────────────┘              │
│                                                  │
│  ✅ Free  ✅ No app  ✅ Email alerts              │  ← trust chips
└──────────────────────────────────────────────────┘
```

Implementation notes:
- No API call — fully static HTML
- Submit → navigate to `/track?url={encodedUrl}` — the track page reads the URL from
  query params and pre-fills the input field, triggering the fetch automatically
- If `userEmail` in Zustand: replace "Track a price" button with "Go to Dashboard →"
- Mobile: input and button stack vertically

### Section 2 — Trust bar (Phase 1 · static placeholder → Phase 2 · DB-driven)

A single horizontal bar with four social proof numbers. Phase 1: static hardcoded
numbers. Phase 2: driven by a lightweight `GET /v1/stats` endpoint called at ISR
revalidation.

```
[2,400+ products tracked]  [₹3.2Cr saved]  [18,000+ alerts sent]  [Amazon · Flipkart · Myntra]
```

### Section 3 — Shop by category (Phase 1 · SSG)

Horizontally scrollable pill row. Each pill is a link to `/offers?category={slug}`.
No backend call — static links. Adding a new category requires only a new pill in the
component array.

Categories (extensible list):
Mobiles · Laptops · Audio · Fashion · TVs · Appliances · Footwear · Watches · Tools

Desktop: all pills visible in one row. Mobile: horizontally scrollable, no wrapping.
Pills use Lucide icons. Active category (when coming from `/offers`) is highlighted.

### Section 4 — Today's biggest price drops (Phase 2 · ISR 30min)

The main deal-discovery section. Platform filter tabs. Deal cards with discount badges.

Data source: `GET /v1/offers?limit=8` — sorted by `drop_percentage DESC`.

Platform filter tabs: All · Amazon · Flipkart · Myntra
Tabs filter client-side from the already-fetched data — no additional API call on tab
switch.

Each deal card displays:
- Product image (placeholder icon if no image)
- Product name (truncated at 2 lines)
- Platform badge
- Current price (large, bold)
- MRP with strikethrough
- Drop percentage badge (e.g. "↓ 29% off") in red
- "View Deal →" link → `/products/[slug]`

Grid: 2 columns on mobile, 4 columns on desktop. Maximum 8 cards shown.
"View all drops →" link navigates to `/offers`.

In Phase 1, this section is hidden. A placeholder "Coming soon — deals will appear
here as products are tracked" message is shown instead.

### Section 5 — Most watched products (Phase 2 · ISR 60min)

Products from the DB with the highest `watcher_count`. Shows that real users are
actively tracking these items — social proof + affiliate opportunity.

Data source: `GET /v1/products?sort=watcher_count&limit=6`

Each product card displays:
- Product image
- Product name (2-line truncation)
- Platform + watcher count (e.g. "Amazon · 89 watching")
- Current price + MRP strikethrough
- All-time low badge (shown if `current_price ≤ all_time_low × 1.05`)
- "Track" button → calls `POST /v1/products/{id}/track` inline or navigates to `/track`

Grid: 2 columns mobile, 3 columns desktop. "View all →" links to `/offers`.

In Phase 1, this section is hidden (same placeholder as Section 4).

### Section 6 — Bank offers & coupons (Phase 1 · from DB)

Horizontally scrollable cards. Data comes from the `offers` JSONB field already stored
on products in the DB, populated by the Flipkart Affiliate API as of v3.0.

No new endpoint required. FastAPI aggregates unique offers across all products at
`GET /v1/coupons?limit=8` (Phase 2). In Phase 1, this can use static hardcoded example
offers until real data is available.

Each offer card displays:
- Bank / card name with bank icon
- Offer description (1–2 lines)
- Platform + expiry date tag

"All coupons →" links to `/coupons`.
If no offers are available, this section is hidden.

### Section 7 — How it works (Phase 1 · SSG)

Three-step explainer. Static. Always present.

```
[1] Paste the URL          [2] We track the price     [3] Get alerted instantly
Copy any product link      PricePing checks every      The moment price drops,
from Amazon, Flipkart,     few hours automatically     you get an email with the
or Myntra and paste it.    — no action needed.         new price and buy link.
```

Desktop: three columns side by side. Mobile: stacked vertically.

### Section 8 — PricePing recommendation preview (Phase 1 · SSG)

Two static example recommendation cards demonstrating the intelligence of PricePing
before a visitor has tracked anything. Shows the "buy" and "wait" verdicts with
plausible product names and price data. All static content — no API call.

Purpose: the recommendation feature is a key differentiator. Showing it on the landing
page communicates value immediately.

Two cards shown:
- "Great time to buy" example (near all-time low product)
- "Consider waiting" example (price dropping frequently product)

Each card: verdict icon + label + one-sentence explanation + price context.
Labelled "Example — PricePing recommendation".

### Section 9 — Stats (Phase 1 · static → Phase 2 · DB)

Three metric tiles in a horizontal grid:
- Average saving per user: ₹8,400
- Average alert time after drop: 6 hours
- Platforms tracked: 3 (Amazon, Flipkart, Myntra)

Phase 1: static numbers. Phase 2: driven by `GET /v1/stats`.

Below the tiles: three platform chips (Amazon India, Flipkart, Myntra) as visual
confirmation of supported platforms.

### Section 10 — Blog preview (Phase 3 · SSG)

Three blog post cards from MDX files. Hidden in Phase 1 and 2 — only rendered in
Phase 3 when `/content/blog/` files exist.

Each card:
- Category tag + read time
- Post title
- One-line description
- Notes if the post embeds live tracked prices

"Read more →" links to `/blog`.

### Section 11 — Footer CTA (Phase 1 · SSG)

Repeats the URL input box from the hero, positioned at the very bottom of the page.
Captures visitors who scrolled the entire page without acting.

```
┌──────────────────────────────────────────────────┐
│  Start tracking prices — it's free               │
│  Paste any product URL to get started.           │
│                                                  │
│  ┌────────────────────────────┐  [Track price]   │
│  │ Paste product URL...       │                  │
│  └────────────────────────────┘                  │
│  No account required · Free forever              │
└──────────────────────────────────────────────────┘
```

### Section 12 — Footer (Phase 1 · SSG)

Three-column link footer. Affiliate disclosure note (legally required for Indian
affiliate sites using Amazon/Flipkart affiliate programs).

Columns:
- PricePing: About, Blog, How it works, Dashboard
- Track prices on: Amazon India, Flipkart, Myntra, Top deals today
- Categories: Mobiles, Laptops, Fashion, Electronics

Bottom bar: copyright + "Prices updated every 4 hours · Affiliate disclosure" link.

### Component file

`app/page.jsx` — the landing page component. Imports section components from
`components/landing/`. Each section is a separate component file, making it trivial to
reorder, hide, or add new sections.

```
components/landing/
├── Navbar.jsx              ← shared with product page
├── HeroSection.jsx
├── TrustBar.jsx
├── CategoryPills.jsx
├── TopDeals.jsx            ← Phase 2
├── PopularProducts.jsx     ← Phase 2
├── BankOffersRow.jsx
├── HowItWorks.jsx
├── RecommendationPreview.jsx
├── StatsSection.jsx
├── BlogPreview.jsx         ← Phase 3
├── FooterCTA.jsx
└── Footer.jsx
```

### Phase 1 content state

In Phase 1, sections 4 (Top Deals) and 5 (Popular Products) are hidden and replaced
with a single placeholder: "Deal sections will appear here as more products are tracked."
All other sections are fully functional in Phase 1 using static content or data already
in the DB.

---

## 10. Page: Dashboard (/dashboard)

### Phase: 1 | Rendering: Client Component

### Purpose
Shows all products a user is currently tracking. Primary page for returning users.

### Layout

```
┌─────────────────────────────────────────────┐
│  TopBar: PricePing logo    [hamburger]       │
├──────────┬──────────────────────────────────┤
│ Sidebar  │  📋 My Tracked Items             │
│          │                                  │
│ Dashboard│  ┌────────────────────────────┐  │
│ Track    │  │ [you@example.com    ] [Go] │  │
│ Offers   │  └────────────────────────────┘  │
│ Profile  │                                  │
│          │  Showing 3 items for you@...     │
│          │                                  │
│          │  ┌────────────────────────────┐  │
│          │  │ [img] Product Name         │  │
│          │  │       🛒 Amazon  ✅ Stock   │  │
│          │  │       ₹67,999  ⭐4.5       │  │
│          │  │       Last: 2h ago   [🗑️]  │  │
│          │  └────────────────────────────┘  │
│          │  (more cards...)                 │
└──────────┴──────────────────────────────────┘
```

### State Machine

```
No email in store
      │
      ▼
Show email input form
      │
User submits email
      │
      ▼
GET /v1/auth/check?email=
      │
      ├── requires_password: false → GET /v1/items?email=
      └── requires_password: true → Show password input
                                          │
                                    POST /v1/auth/login
                                          │
                                    GET /v1/items (with JWT)
```

### Loading State
Three `ProductCardSkeleton` components shown while `useItems` is fetching. Skeleton
matches the exact dimensions of `ProductCard` to prevent layout shift.

### Empty State
When `items.length === 0`: `EmptyState` component with illustration and
"➕ Track Your First Item" button → navigate to `/track`.

### Delete Flow
1. User clicks 🗑️ on a `ProductCard`
2. `deleteTarget` set in Zustand store with `{ subscriptionId, productName }`
3. `DeleteDialog` (shadcn `AlertDialog`) renders as modal overlay
4. "Remove" → `useDeleteSubscription.mutate()` → on success: invalidate `useItems` cache
   (list auto-refreshes without page reload) + Sonner toast "Removed successfully"
5. "Cancel" or Escape → `deleteTarget` set to `null`, dialog closes

### Product Card — `ProductCard.jsx`

Props: `item` (from `GET /v1/items` response), `onRemove(subscriptionId)`

Displays:
- Product image (72px width, object-fit cover)
- Product name (truncated at 2 lines)
- Platform badge + availability badge
- Current price (bold, large)
- `special_price` if different from `current_price` (offer price in smaller text)
- Rating + review count
- `formatTimeAgo(last_checked_at)`
- 🗑️ remove button (right-aligned, triggers delete flow)

Click on card body (excluding remove button) → navigate to `/products/[slug]`

---

## 11. Page: Track New Item (/track)

### Phase: 1 | Rendering: Client Component

### Purpose
Three-step flow to add a new product to tracking. Identical logic to the Streamlit
`track.py` state machine, implemented with React state.

### State Machine

```
trackStep = "input"
      │ User submits URL
      ▼
trackStep = "loading"  ← PreviewSkeleton shown (10–20s scrape)
      │ API responds
      ├── Error → Show error message, remain on "input"
      └── Success → previewResult stored in Zustand
            │
            ▼
      trackStep = "preview"
            │ User clicks "Yes, track it"
            ▼
      trackStep = "confirming"  ← Spinner on button
            │
            ├── Error → Show error, remain on "preview"
            └── Success
                  │
                  ▼
            trackStep = "success"
```

### Step 1: Input

```
┌───────────────────────────────────────────┐
│  ➕ Track New Item                        │
│                                           │
│  Paste a product URL to see details and   │
│  start tracking the price.                │
│                                           │
│  ┌─────────────────────────────────────┐  │
│  │ https://www.amazon.in/...           │  │
│  └─────────────────────────────────────┘  │
│  [ Fetch Product Details → ]              │
│                                           │
│  ✅ Amazon India · Flipkart · Myntra      │
└───────────────────────────────────────────┘
```

- URL field validates on submit (not on change — avoids premature errors)
- Submit triggers `usePreview.mutate(url)` → immediately sets `trackStep = "loading"`
- `PreviewSkeleton` shown during loading — matches approximate dimensions of `PreviewCard`

### Step 2: Preview — Existing Product

```
┌───────────────────────────────────────────┐
│  Is this the right product?               │
│                                           │
│  ┌─────────────────────────────────────┐  │
│  │ [img] Apple iPhone 15 (128GB)       │  │
│  │       Brand: Apple                  │  │
│  │       🛒 Amazon India  ✅ In Stock   │  │
│  │                                     │  │
│  │       ₹67,999        LIVE PRICE     │  │
│  │       ~~₹69,999~~  ▼ ₹2,000 less   │  │
│  │                                     │  │
│  │       ⭐ 4.5 · 12,483 reviews       │  │
│  │       Sold by: Appario Retail       │  │
│  │                                     │  │
│  │  ── 12 people watching ──────────   │  │
│  │  📉 5 price drops  📊 ₹62,999 low  │  │
│  │  📅 Tracked since May 2026          │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  📧 [you@example.com               ]      │
│                                           │
│  [← Different URL]  [✅ Yes, track it]   │
│                                           │
│  Preview valid for ~10 min               │
└───────────────────────────────────────────┘
```

### Step 2: Preview — New Product (no catalog_data)

Same layout, replace the catalog section with:
```
│  ✨ Be the first to track this product!  │
```

### Step 3: Success

```
┌───────────────────────────────────────────┐
│  ✅ You're now tracking this product!     │
│                                           │
│  We'll email you@example.com when the    │
│  price drops.                             │
│                                           │
│  [ View Product Details → ]               │
│  [ Track Another Item ]                   │
└───────────────────────────────────────────┘
```

"View Product Details" → navigate to `/products/[slug]` using `product_id` from response.
"Track Another Item" → reset `trackStep = "input"`, `previewResult = null`.

### Email Field Handling
- Email field is pre-filled from `userEmail` in Zustand if available
- On successful confirm, update `userEmail` in Zustand with the submitted email
- Email is validated: non-empty + contains `@` + basic format check

---

## 12. Page: Product Detail (/products/[slug])

### Phase: 1 (CC) → Phase 2 (ISR)

### Phase 1 Rendering: Client Component
The page loads by extracting `product_id` from URL params and calling
`GET /v1/products/{id}`. Accessible to all users — no auth required to view.
Served at `/products/[slug]`. In Phase 1, the product_id is passed as a query
parameter from the dashboard until slugs are generated.

### Phase 2 Rendering: ISR — revalidate every 60 minutes
The Next.js server pre-renders the full page HTML including price, stats, and metadata.
Google indexes the complete page. `generateMetadata()` produces OG tags.
Users still get live price data — the sidebar Refresh button triggers a client-side
fetch even on an ISR-rendered page.

### Slug Format
`{name-slugified}-{marketplace_product_id}`

Examples:
- `apple-iphone-15-128gb-black-B0CHX1W1XY`
- `samsung-galaxy-s24-ultra-256gb-titanium-violet-SM-S928B`

Slug is generated on product creation in FastAPI and stored in `products.slug`.
It is stable — never changed after creation. UNIQUE constraint on the column.

### Breadcrumb Navigation

The product page must be a fully independent standalone page. It does not depend on
the browser back button to navigate users back to the landing page or any other page.
Navigation is provided entirely by the breadcrumb component mounted below the navbar.

```
Home → Mobiles → Apple → Apple iPhone 15 (128GB) Black
```

Each crumb is a link:
- "Home" → `/`
- Category (e.g. "Mobiles") → `/offers?category=mobiles`
- Brand (e.g. "Apple") → `/offers?brand=apple`
- Product name → current page (not a link — current location indicator)

The breadcrumb uses `product_metadata.category` and `product_metadata.brand` to build
the intermediate crumbs. If category or brand is unavailable, those crumbs are omitted.

Component: `Breadcrumb.jsx` in `components/product/`.

### Two-Column Layout

The product page uses a persistent two-column layout on desktop. The right column is a
sticky sidebar that remains visible as the user scrolls through the long left column.

```
┌────────────────────────────────────────────────────────┐
│ Navbar                                                 │
├────────────────────────────────────────────────────────┤
│ Breadcrumb: Home → Mobiles → Apple → iPhone 15         │
├───────────────────────────────────┬────────────────────┤
│ LEFT COLUMN (main, scrollable)    │ RIGHT COLUMN       │
│                                   │ (sticky sidebar)   │
│  ① Hero (image + identity)        │ Price + Buy btn    │
│  ② Key Specs Grid                 │ Track CTA          │
│  ③ Price History Chart            │ AI Recommendation  │
│  ④ Price Comparison (P2)          │ Price stats box    │
│  ⑤ Bank Offers & Coupons          │ Target price input │
│  ⑥ Description + Features        │ Platform compare   │
│  ⑦ Full Specifications            │   mini (P2)        │
│  ⑧ Similar Products (P2)         │                    │
│                                   │                    │
└───────────────────────────────────┴────────────────────┘
```

Column widths: left = `1fr`, right = `280px`. Gap: `24px`.
Right column: `position: sticky; top: 80px` (accounts for navbar height).

On mobile: the right sidebar collapses to a sticky bottom bar showing only price +
buy button + track button. All sidebar boxes (recommendation, stats, target price) move
into the left column at their logical positions between sections.

### Component files for product page

```
components/product/
├── Breadcrumb.jsx          ← Navigation breadcrumb — no browser back dependency
├── ProductHero.jsx         ← Image gallery + identity + spec chips
├── KeySpecsGrid.jsx        ← 2×N key spec table from product_metadata.specs
├── PriceHistoryChart.jsx   ← Recharts LineChart with period toggle
├── PlatformComparison.jsx  ← Cross-platform price table (Phase 2)
├── OffersSection.jsx       ← Bank offers from offers JSONB
├── ProductDescription.jsx  ← description + features bulleted list
├── FullSpecsTable.jsx      ← Grouped full spec table, collapsible by category
├── SimilarProducts.jsx     ← Horizontal scroll carousel (Phase 2)
├── ProductSidebar.jsx      ← Right column wrapper (sticky)
├── SidebarPriceBox.jsx     ← Price + buy btn + track btn + refresh + share
├── SidebarRecommendation.jsx ← AI verdict card in sidebar
├── SidebarPriceStats.jsx   ← All-time low/high/drops/tracked-since
├── TargetPriceInput.jsx    ← Target price input field + Set button
└── MobileBottomBar.jsx     ← Mobile sticky bottom: price + buy + track
```

---

### Left Column — Section ① Hero (`ProductHero.jsx`)

**Phase: 1 | Data: `GET /v1/products/{id}`**

Left sub-column: image gallery.
- Main product image: 200×200px fixed, `object-fit: contain`, border, rounded.
- Thumbnail row below: up to 3 thumbnails (80px wide each). Click to swap main image.
- In Phase 1, only one image is shown (no gallery switching).
- Phase 2: multiple images from `product_metadata.images[]`.

Right sub-column: product identity.
- Platform badge — "Amazon India" / "Flipkart" / "Myntra"
- Availability badge — "In Stock" (green) / "Out of Stock" (red)
- Near all-time low badge — shown if `current_price ≤ all_time_low × 1.05`
- Product name as `<h1>` — full name, not truncated (SEO in Phase 2)
- Brand name + seller name in muted text
- Star rating + review count (from `product_metadata`)
- Watcher count — "👥 14 people watching"
- Quick spec chips — key specs from `product_metadata.specs` displayed as pills
  (e.g. "6.1″ OLED", "A16 Bionic", "128 GB", "48 MP camera")
  Only the top 5–6 most important specs are shown as chips.
  Spec chips are rendered generically — the same component works for mobiles,
  laptops, ACs, and apparel.

---

### Left Column — Section ② Key Specs Grid (`KeySpecsGrid.jsx`)

**Phase: 1 | Data: `product_metadata.specs` JSONB**

A 2-column key-value table showing the top 6–8 specs. Visually clear, no accordion —
always visible.

Rendered as a bordered grid: left cell = spec label (muted), right cell = spec value
(bold). Two columns of pairs side by side on desktop, one column on mobile.

Example for a mobile:
```
Display    │ 6.1″ Super AMOLED    │  Processor  │ A16 Bionic
RAM        │ 6 GB                 │  Storage    │ 128 GB
Battery    │ 3,349 mAh            │  OS         │ iOS 17
Camera     │ 48 + 12 MP           │  Connector  │ USB-C
```

"View full specifications ↓" anchor link scrolls to Section ⑦.

This section is product-type agnostic — the spec keys and values come from
`product_metadata.specs` directly. No hardcoded spec categories.

---

### Left Column — Section ③ Price History Chart (`PriceHistoryChart.jsx`)

**Phase: 1 | Data: `GET /v1/products/{id}/history?period=3m`**

Built with Recharts `LineChart`.

**Period toggle:** 1M · 3M · 6M · All (default: 3M)
Toggle state: `useState` local to the component. Changing period calls the endpoint
with the new period parameter — one API call per toggle.

**Chart configuration:**
- X-axis: date formatted as "14 Aug" via `formatDateShort()` (IST)
- X-axis sort: by actual `checked_at` datetime column, not by string label
- Y-axis: ₹, `domain: ['auto', 'auto']`, `allowDataOverflow: false`
- Line: `type="monotone"`, smooth, accent colour
- Dots: shown at each data point
- Tooltip: full IST date + formatted ₹ price
- Grid: subtle horizontal lines only
- Responsive: `<ResponsiveContainer width="100%" height={200}>`
- All-time low marker: dashed horizontal `<ReferenceLine>` at `all_time_low`

**Phase 1 addition (authenticated user):**
If user is tracking this product (`userEmail` in Zustand + subscription check), a
second dashed `<ReferenceLine>` at their target price (if set), labelled "Your target".

**Phase 2 addition — price prediction overlay:**
A dashed line extending 14 days forward, from linear regression on last 30 price
points. Confidence band (±1 SD) as `<ReferenceArea>`. Labelled "Estimated trend —
not guaranteed".

---

### Left Column — Section ④ Price Comparison (`PlatformComparison.jsx`)

**Phase: 2 | Data: `GET /v1/products/{id}/compare`**

A table showing the same product's current price on all platforms where it is tracked
in the DB. No live scraping — DB lookup only.

| Platform | Price | Status | Action |
|---|---|---|---|
| Amazon India ✅ Cheapest | ₹67,999 | In Stock | Buy → |
| Flipkart | ₹69,999 | In Stock | Buy → |
| Myntra | Not available | — | — |

Cheapest platform row has green background. Unavailable platforms shown in muted style.

If only one platform has this product tracked (the most common case in Phase 1), this
section is hidden entirely — no "not available on other platforms" message.

---

### Left Column — Section ⑤ Bank Offers & Coupons (`OffersSection.jsx`)

**Phase: 1 | Data: `offers` JSONB from `GET /v1/products/{id}`**

Each offer shown as an inline card (not accordion — the product page has enough
vertical space to show offers expanded by default):
- Bank / card name with icon
- Offer description
- Expiry date tag

No-cost EMI is shown if available (from `offers` JSONB).

If `offers` is null or empty array, this section is hidden.

---

### Left Column — Section ⑥ Description & Features (`ProductDescription.jsx`)

**Phase: 1 | Data: `product_metadata.description`, `product_metadata.features`**

Description paragraph (2–3 sentences, from `product_metadata.description`).

Features bulleted list (from `product_metadata.features[]`), showing first 6 items.
"Show all features ↓" expands to full list (client-side toggle, no API call).

If description is null, this section is hidden.

---

### Left Column — Section ⑦ Full Specifications (`FullSpecsTable.jsx`)

**Phase: 1 | Data: `product_metadata.specs` JSONB**

All specs from `product_metadata.specs`, grouped by category (e.g. Display, Camera,
Battery, Connectivity, General). Category groups are defined by keys in the specs JSONB.

Each category rendered as a section header + key-value rows. One full-width column.
Alternating row backgrounds for readability.

"Show all specifications" at the bottom of Section ② links via anchor to this section.

---

### Left Column — Section ⑧ Similar Products (`SimilarProducts.jsx`)

**Phase: 2 | Data: `GET /v1/products/{id}/similar?limit=6`**

Horizontally scrollable card row. Same logic as the landing page Popular Products
section but filtered to the same brand + platform.

Each mini card: thumbnail image, product name (2-line truncation), current price.
Click → navigate to `/products/[slug]` of that product.

Lazy loaded — `enabled: isInView` (IntersectionObserver). Only fetches when user
scrolls to this section.

If 0 results: section is hidden.

---

### Right Column — Sticky Sidebar (`ProductSidebar.jsx`)

**Phase: 1 | position: sticky | top: 80px**

The sidebar contains five boxes stacked vertically. On desktop, all five are always
visible as the user scrolls. On mobile, only the price+buy+track elements appear in the
sticky bottom bar — the rest appear inline in the left column.

#### Sidebar Box 1 — Price, Buy, Track (`SidebarPriceBox.jsx`)

**Phase: 1**

```
┌─────────────────────────────────────┐
│  ₹67,999                            │  ← current price (large)
│  ~~₹79,900~~   15% off             │  ← MRP + discount badge
│                                     │
│  Special price: ₹65,499 with HDFC  │  ← special_price (if different)
│                                     │
│  ✅ In stock on Amazon India        │  ← availability
│                                     │
│  [  Buy on Amazon →  ]              │  ← affiliate link button
│  [  🔔 Track · Get drop alerts  ]   │  ← track CTA (state-aware, see below)
│                                     │
│  Last checked: 14 Aug, 10:30 AM IST │
│  🔄 Refresh                         │
│                                     │
│  [Copy link]  [WhatsApp]  [Tweet]   │  ← share row
└─────────────────────────────────────┘
```

Track CTA states (same three states as before):
- **State A** (not tracking, no email): shows email input + Track button inline
- **State B** (not tracking, email known): shows single "Track · Get drop alerts" button
- **State C** (currently tracking): shows "✅ Tracking · Get drop alerts" in green,
  with "Stop tracking" link below

"Buy on Amazon →" is the affiliate link. Opens `product.url` in a new tab.

🔄 Refresh: calls `useProduct.refetch()`. The price and last-checked timestamp update
in place. The rest of the page is unaffected. Sonner toast: "Price updated" or "Price
unchanged since last check."

Share row: Copy link / WhatsApp / Tweet. On mobile Web Share API is used if available.

#### Sidebar Box 2 — AI Recommendation (`SidebarRecommendation.jsx`)

**Phase: 1 (rule-based) → Phase 3 (ML)**

See Section 20 for the full design contract.

```
┌─────────────────────────────────────┐
│  ✅ Good time to buy                │  ← verdict icon + label
│                                     │
│  Price is near the all-time low.   │  ← one-sentence explanation
│  We've tracked this since May 2026. │
│                                     │
│  PricePing recommendation · P1      │  ← attribution label
└─────────────────────────────────────┘
```

Verdict colours: green (buy), amber (wait), red (high price), grey (neutral/insufficient).

#### Sidebar Box 3 — Price Stats (`SidebarPriceStats.jsx`)

**Phase: 1 | Data: `price_stats` from `GET /v1/products/{id}`**

```
┌─────────────────────────────────────┐
│  Current price     ₹67,999          │
│  All-time low      ₹62,999  [Low ✅]│
│  All-time high     ₹79,900  [High ❌]│
│  Price drops       6 times          │
│  Tracked since     May 2026         │
└─────────────────────────────────────┘
```

Each row is a label-value pair. All-time low and high have coloured badges.

#### Sidebar Box 4 — Target Price Input (`TargetPriceInput.jsx`)

**Phase: 1 | Auth-aware**

Shown only if user has email in Zustand (email-only or password user).

```
┌─────────────────────────────────────┐
│  🎯 Set target price                │
│  ┌──────────────────┐  [Set]        │
│  │ e.g. ₹60,000    │               │
│  └──────────────────┘               │
│  Alert me when price drops below    │
└─────────────────────────────────────┘
```

On submit: `PATCH /v1/subscriptions/{id}` with `{target_price: value}`.
After set: displays "Target: ₹60,000 · Edit" in place of input.
Clears target: "Remove target" link.

If user is not tracking this product, this box is hidden.

#### Sidebar Box 5 — Platform Comparison Mini (Phase 2)

**Phase: 2 | Data: `GET /v1/products/{id}/compare`**

A compact version of Section ④ for the sidebar.

```
┌─────────────────────────────────────┐
│  Prices on other platforms          │
│  Amazon ✅ Best    ₹67,999          │
│  Flipkart          ₹69,999          │
└─────────────────────────────────────┘
```

Each row links to the product on that platform.
Shown only when comparison data has ≥1 result. Hidden in Phase 1.

---

### Mobile Layout

On screens narrower than 768px, the two-column layout collapses to a single column.

The sidebar boxes are redistributed into the left column flow:
- After Section ①: SidebarPriceBox content appears inline (price block)
- After Section ①: SidebarRecommendation appears inline
- After Section ③ (chart): SidebarPriceStats appears inline
- TargetPriceInput appears below SidebarPriceStats inline

A **sticky bottom bar** (`MobileBottomBar.jsx`) is pinned to the bottom of the
viewport on mobile. It contains only three elements:

```
|  ₹67,999  |  Buy on Amazon →  |  🔔 Track  |
```

Tapping "Buy" opens the affiliate link in a new tab.
Tapping "Track" either tracks immediately (State B) or opens a bottom sheet email
input (State A). State C shows "✅ Tracking" in muted colour.

---

### Full Section Render Order (Desktop)

```
┌────────────────────────────────────────────────────────────┐
│ Navbar                                                     │
├────────────────────────────────────────────────────────────┤
│ Breadcrumb: Home → Mobiles → Apple → Apple iPhone 15       │
├───────────────────────────────────────┬────────────────────┤
│ ① Hero                                │                    │
│   [img gallery]  name, brand,         │ SidebarPriceBox    │
│   badges, watcher, spec chips         │ (price, buy, track,│
├───────────────────────────────────────┤  refresh, share)   │
│ ② Key Specs Grid                      │                    │
│   2×4 spec table                      ├────────────────────┤
├───────────────────────────────────────┤ SidebarRecomm.     │
│ ③ Price History Chart                 │ (verdict card)     │
│   period toggle + recharts line       ├────────────────────┤
├───────────────────────────────────────┤ SidebarPriceStats  │
│ ④ Price Comparison (Phase 2)          │ (low/high/drops)   │
│   cross-platform price table          ├────────────────────┤
├───────────────────────────────────────┤ TargetPriceInput   │
│ ⑤ Bank Offers & Coupons               │ (set alert price)  │
│   inline offer cards                  ├────────────────────┤
├───────────────────────────────────────┤ Platform mini (P2) │
│ ⑥ Description + Features             │                    │
│   paragraph + bulleted features       │                    │
├───────────────────────────────────────┤                    │
│ ⑦ Full Specifications                 │                    │
│   grouped spec table, collapsible     │                    │
├───────────────────────────────────────┤                    │
│ ⑧ Similar Products (Phase 2)         │                    │
│   horizontal scroll card row          │                    │
└───────────────────────────────────────┴────────────────────┘
```

---

## 13. Page: Offers (/offers)

### Phase: 2 | Rendering: ISR — revalidate every 30 minutes

### Purpose
Publicly discoverable page listing the biggest price drops across all tracked products.
Drives organic search traffic ("best deals today India"). Fully indexed by Google.

### Data Source
New FastAPI endpoint: `GET /v1/offers?limit=50`
Returns products sorted by `drop_percentage DESC` where `current_price < price 24h ago`.

### Sections
1. **Hero** — "Today's Best Deals" heading, last updated timestamp
2. **Filter bar** — By platform (All / Amazon / Flipkart / Myntra), by category (coming from metadata)
3. **Offer cards grid** — 2 cols on mobile, 3 cols on desktop. Each `OfferCard.jsx` shows:
   - Product image
   - Product name (truncated at 2 lines)
   - Platform badge
   - Current price (large)
   - MRP strikethrough + discount % badge
   - Drop amount — "↓ ₹3,000 cheaper than yesterday"
   - "View Deal →" → `/products/[slug]`

### SEO
`generateMetadata()` returns:
```js
{
  title: "Best Deals Today — PricePing",
  description: "Top price drops on Amazon, Flipkart, and Myntra. Updated every 30 minutes.",
}
```

---

## 14. Page: Coupons (/coupons)

### Phase: 2 | Rendering: ISR — revalidate every 30 minutes

### Purpose
Lists current bank offers and coupon codes across all tracked products.
Populated from the `offers` JSONB field stored on each product.

### Data Source
New FastAPI endpoint: `GET /v1/coupons?limit=100`
Aggregates and deduplicates bank offers across all products. Groups by bank/card.

### Sections
1. **Grouped by bank** — HDFC / SBI / ICICI / Axis / Others
2. Each group shows the offer text and which products it applies to
3. "View Product →" links to the relevant product page

---

## 15. Page: Blog (/blog and /blog/[slug])

### Phase: 3 | Rendering: SSG

### Purpose
Content marketing. Long-form articles about buying guides, product comparisons, and when
to buy specific categories. Drives organic search traffic. Google indexes every post.

### Implementation
Blog posts are written as MDX files in `src/content/blog/`. Each file exports:
- `title`
- `description`
- `publishedAt`
- `category`
- `slug`

MDX allows embedding live React components inside blog post content. This means a blog
post like "Best Phones Under ₹20,000" can embed a live `MiniProductCard` showing the
current tracked price — automatically updated when the ISR page rebuilds.

### File naming
`src/content/blog/best-phones-under-20000.mdx`
→ resolves to `priceping.in/blog/best-phones-under-20000`

### No CMS required in Phase 3
Files are authored directly in the repository. A CMS (Contentful, Sanity) can be added
later without restructuring the blog system.

---

## 16. Page: Profile (/profile)

### Phase: 1 | Rendering: Client Component

### Purpose
User's personal settings. Notification preferences and password management.

### Sections

**1. Account**
- Email display (read-only)
- Password section:
  - If no password set: "Set a password to protect your dashboard" → set password form
  - If password set: "Change password" form (requires current password)

**2. Notification Preferences** (schema designed in v3.2 — UI placeholder in Phase 1)
- Master notifications toggle — pause all alerts
- Per-subscription settings link (Phase 2 when implemented)
- Email digest frequency (Phase 2)

**3. Danger Zone**
- "Delete my account" — removes user + all subscriptions. Products remain in catalog.

---

## 17. Page: Login (/login)

### Phase: 1 | Rendering: SSG shell (auth logic runs client-side)

### Purpose
Entry point for users who have set a password. Also serves as the redirect target when
a JWT expires.

### Flow
Same as dashboard auth flow. Email field → auth check → conditionally show password.

### Notes
- If user arrives with a valid JWT in localStorage, redirect to `/dashboard` immediately
- If user arrives from a JWT expiry redirect, show "Your session expired, please log in again"
- "Continue without password" link for users who have not set one → goes to `/dashboard`

---

## 18. Shared Layout Components

### `AppShell.jsx`
Wraps all pages inside the `(app)` route group. Renders:
- `Sidebar` (desktop) — left column, fixed
- `TopBar` — top bar on all screen sizes
- `MobileNav` — bottom navigation bar on mobile (hidden on desktop)
- `{children}` — the page content

Health check: on mount, calls `GET /v1/health`. If response is not `200 ok`, shows a
dismissible banner: "⚠️ PricePing is experiencing issues. Some features may not work."

### `Sidebar.jsx`
Navigation links with active state highlighting:
- 📋 Dashboard → `/dashboard`
- ➕ Track Item → `/track`
- 🏷️ Offers → `/offers` (Phase 2)
- ⚙️ Profile → `/profile`

Shows user email at the bottom if `userEmail` is in store.

### `TopBar.jsx`
- PricePing logo (links to `/`)
- Page title (current route name)
- Hamburger menu button on mobile (toggles `Sidebar` drawer)
- User email display on desktop (top right)

### `MobileNav.jsx`
Bottom navigation bar visible only on mobile (`block md:hidden`). Same links as sidebar.
Uses Lucide icons. Active link highlighted with accent colour.

---

## 19. Shared UI Components

### `DeleteDialog.jsx`

shadcn `AlertDialog`. Reads `deleteTarget` from Zustand.

Props: none — reads from global store directly.

Renders when `deleteTarget !== null`.

```
┌─────────────────────────────────┐
│  Remove product?                │
│                                 │
│  Remove "Apple iPhone 15" from  │
│  your tracking list?            │
│                                 │
│  [Cancel]  [Yes, Remove]        │
└─────────────────────────────────┘
```

- Modal has backdrop overlay
- Escape key → cancel (shadcn handles this)
- Focus trapped inside dialog while open (shadcn handles this)
- "Yes, Remove" → calls `useDeleteSubscription.mutate()`, closes dialog, shows toast

### `PreviewSkeleton.jsx`

Shown during the 10–20 second scrape on the Track page.
Matches the approximate dimensions of `PreviewCard` using shadcn `Skeleton` elements.
The rest of the page remains interactive while skeleton is shown.

### `ProductCardSkeleton.jsx`

Matches the dimensions of `ProductCard` on the Dashboard.
Three skeletons shown while `useItems` is loading.

---

## 20. AI Buying Recommendation — Design Contract

This section defines a permanent contract between the recommendation data and the
`BuyingRecommendation.jsx` component. The contract ensures the component never needs
to change when the data source changes from rule-based (Phase 1) to ML (Phase 3).

### 20.1 Output Shape (locked from Phase 1)

```js
{
  verdict:    string,   // "buy" | "wait" | "high" | "neutral" | "insufficient"
  message:    string,   // One sentence. User-facing. Max 100 chars.
  confidence: number | null,  // 0.0–1.0. null in Phase 1.
  reasoning:  string | null,  // Explanation. null in Phase 1.
}
```

### 20.2 Phase 1 — Rule-based (Frontend Only)

Source: `src/lib/recommendation.js`
Input: `price_stats` object from `GET /v1/products/{id}`
No API call. No backend involvement.

```
avg_price = (all_time_low + all_time_high) / 2
```

Rules evaluated in priority order (first match wins):

| Priority | Condition | Verdict | Message |
|---|---|---|---|
| 1 | `current_price ≤ all_time_low × 1.05` | `buy` | "Near the lowest price we've ever recorded. Strong buy signal." |
| 2 | `current_price ≤ avg_price × 0.90` | `buy` | "Price is more than 10% below average. Good time to buy." |
| 3 | `current_price ≥ all_time_high × 0.92` | `high` | "Price is near its all-time high. Consider waiting." |
| 4 | `drop_count ≥ 3 AND last_drop_within_45_days` | `wait` | "Price has dropped {drop_count} times recently. Another drop may follow." |
| 5 | `avg_price × 0.90 < current_price < avg_price × 1.10` | `neutral` | "Price is around its historical average. No strong signal either way." |
| 6 | `drop_count < 3 OR price_history < 3 points` | `insufficient` | "We're still collecting price history. Check back in a few days." |

`last_drop_within_45_days` is computed from `first_tracked_at` and `drop_count` as a
proxy — full drop timestamp is not in `price_stats`. Phase 2 adds `last_drop_at` to the
price_stats response when the field is available.

### 20.3 Phase 3 — ML/AI (Backend)

Source: `GET /v1/products/{id}/recommendation` (new FastAPI endpoint)

FastAPI calls the ML model or an external API (OpenAI, internal model) and returns the
same shape defined in 20.1 — with `confidence` and `reasoning` now populated.

**Change required in frontend:** One line in `hooks/useRecommendation.js` — swap the
local function call with an Axios request. The `BuyingRecommendation.jsx` component
renders identically.

### 20.4 Component Rendering

```
verdict = "buy"     → Green card, ✅ icon, bold "Great time to buy" label
verdict = "wait"    → Yellow card, ⏳ icon, bold "Consider waiting" label
verdict = "high"    → Red card, ⛔ icon, bold "Price is high" label
verdict = "neutral" → Grey card, 📊 icon, bold "Average price" label
verdict = "insufficient" → Grey card, 📈 icon, italic message

confidence (Phase 3):
  ≥ 0.80 → "High confidence"
  0.60–0.79 → "Moderate confidence"
  < 0.60 → "Low confidence" (shown with subtle warning)

reasoning (Phase 3):
  Shown in a collapsible "Why?" section below the verdict
```

Label: "PricePing Recommendation" in Phase 1 and 2.
Label: "AI Recommendation" in Phase 3 when ML model is active.

---

## 21. Navigation Model — No Browser Back Button Dependency

### 21.1 Design Principle

The product page and the landing page are two fully independent pages. Neither depends
on the browser back button to navigate the user back to a previous location. This is a
deliberate design decision: product pages must be shareable, bookmarkable, and
directly openable from Google search results without requiring the landing page to
have been visited first.

PriceDekho's model (for reference): clicking a product from the homepage replaces the
homepage in the same tab. Browser back → homepage. Product page depends on prior
navigation state.

PricePing's model: each URL is its own standalone page. A user can open
`priceping.in/products/apple-iphone-15-B0CHX1W1XY` directly, share it, or receive
it via WhatsApp — and the page is fully functional and self-contained.

### 21.2 Two Standalone Pages

| Page | URL | Navigates from | Back navigation |
|---|---|---|---|
| Landing | `priceping.in/` | Google, direct, shared links | N/A (homepage) |
| Product detail | `priceping.in/products/[slug]` | Dashboard, landing, Google, shared links | Breadcrumb (see below) |
| Dashboard | `priceping.in/dashboard` | Navbar link, post-tracking success | Navbar link home |

Both pages share the same `Navbar.jsx` component. The navbar provides top-level
navigation on both pages — no conceptual difference between them.

### 21.3 Breadcrumb as Primary Back Navigation

The product page mounts a `Breadcrumb.jsx` component immediately below the navbar.
This breadcrumb is the authoritative navigation for going "up" in the hierarchy. The
browser back button still works as expected (takes the user wherever they were before),
but it is never needed — the breadcrumb provides explicit, labelled navigation.

```
Home → Mobiles → Apple → Apple iPhone 15 (128GB) Black
```

- "Home" → `<Link href="/">` — pushes a new history entry, does not go back
- "Mobiles" → `<Link href="/offers?category=mobiles">`
- "Apple" → `<Link href="/offers?brand=apple">`
- Product name → current page — rendered as `<span>` (not a link)

Breadcrumb crumbs are built from `product_metadata.category` and
`product_metadata.brand`. If either is null, the relevant crumb is skipped.

### 21.4 Product Navigation from Landing Page

When a user clicks a product card on the landing page (Top Deals, Popular Products),
the navigation uses Next.js `<Link href="/products/[slug]">`. This pushes a new entry
to the browser history. The user arrives on the product page which is fully
self-contained — the breadcrumb replaces the need to use browser back to return to
the landing page.

### 21.5 Product Navigation from Dashboard

When a user clicks a `ProductCard` on the dashboard, the navigation uses Next.js
`<Link href="/products/[slug]">`. The same principle applies — product page is
standalone, breadcrumb navigates back.

---

## 22. Error Handling

### 22.1 API Error Display

Errors from TanStack Query mutations are caught and displayed via:
1. **Inline error messages** — shown below the relevant form field or section
2. **Sonner toast** — for background operations (refresh, delete)

Pattern in every component that calls an API:
```jsx
const { mutate, isError, error } = useMutation(...)

// Inline:
{isError && <p className="text-red-500 text-sm">{error.message}</p>}

// Toast (for background ops):
onError: (error) => toast.error(error.message)
```

### 22.2 Page-Level Errors

If `GET /v1/products/{id}` returns 404, the product detail page renders a full-page
`not-found` state with a "Go to Dashboard" button. Next.js `notFound()` is called to
serve a proper 404 HTTP status.

### 22.3 Network Errors

Axios interceptor catches connection errors and timeout. Sets `code = "CONNECTION_ERROR"`
or `code = "TIMEOUT"`. Components receive the user-facing message from `errors.js`.

### 22.4 Preview Expiry Handling

If `POST /v1/subscriptions` returns `PREVIEW_NOT_FOUND` (preview TTL expired):
- Reset `trackStep = "input"`
- Clear `previewResult`
- Show toast: "Your preview expired. Please search for the product again."
- User is back on the URL input form — no data lost

---

## 23. Hosting and Deployment

### 23.1 Frontend — Vercel

- **Plan:** Free (Hobby)
- **Deploy:** Automatic on `git push` to `main` branch
- **Domain:** `priceping.in` — add in Vercel project settings → Domains
- **SSL:** Automatic, renews itself
- **Environment variables set in Vercel:**
  - `NEXT_PUBLIC_API_URL` = `https://api.priceping.in`

### 23.2 Backend — Railway (unchanged)

- FastAPI running at `pricemonitor-production-21cc.up.railway.app`
- Add custom domain in Railway: `api.priceping.in`
- **CORS update required in FastAPI** — add `https://priceping.in` to allowed origins:
  ```python
  allow_origins=["https://priceping.in", "http://localhost:3000"]
  ```
- **Rate limiting** — add `slowapi` to FastAPI:
  ```python
  @limiter.limit("30/hour")  # on preview endpoint — prevents abuse
  ```

### 23.3 DNS Configuration

All DNS records set at domain registrar (wherever `priceping.in` is registered):

| Record | Name | Value |
|---|---|---|
| A | `@` (priceping.in) | Vercel IP (provided by Vercel) |
| CNAME | `www` | `cname.vercel-dns.com` |
| CNAME | `api` | Railway-provided CNAME URL |

### 23.4 Local Development

```bash
# Start Next.js dev server
cd priceping-ui
npm run dev
# Runs at http://localhost:3000

# Backend already running
python -m uvicorn app.main:app --port 8001
# Runs at http://localhost:8001

# .env.local:
NEXT_PUBLIC_API_URL=http://localhost:8001
```

---

## 24. New Database Columns Required

These columns are additions to the existing schema. Each requires a separate Alembic
migration. Migrations follow the existing convention: 12-character hex revision hash.

| Table | Column | Type | Nullable | Default | Phase | Purpose |
|---|---|---|---|---|---|---|
| `users` | `password_hash` | `TEXT` | Yes | `NULL` | P1 | bcrypt hash. NULL = no password. |
| `products` | `slug` | `TEXT` | Yes | `NULL` | P2 | SEO URL slug. UNIQUE constraint. |

Migration for `password_hash`:
```python
def upgrade():
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))
```

Migration for `slug`:
```python
def upgrade():
    op.add_column('products', sa.Column('slug', sa.Text(), nullable=True))
    op.create_unique_constraint('uq_products_slug', 'products', ['slug'])
```

Slug backfill: on first request for a product that has no slug, FastAPI generates and
saves it. No bulk backfill script needed — slugs populate organically as products are
accessed.

---

## 25. New FastAPI Endpoints Required

These endpoints are additions to the existing API. All follow the existing conventions:
JSON responses, error format with `code` and `message`, UUID IDs.

### Phase 1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/auth/check?email=` | Returns `{requires_password: bool, user_exists: bool}` |
| `POST` | `/v1/auth/login` | `{email, password}` → `{token, email}` |
| `POST` | `/v1/auth/set-password` | `{email, new_password, otp}` → sets password_hash |
| `POST` | `/v1/auth/send-otp` | `{email}` → sends OTP via SendGrid |
| `GET` | `/v1/products/{id}/history?period=` | `[{price, checked_at}]` — period: 1m\|3m\|6m\|all |
| `POST` | `/v1/products/{id}/track` | `{email}` → creates subscription. Skips scrape. |

### Phase 2 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/products/by-slug/{slug}` | Resolves slug → full product response |
| `GET` | `/v1/products/{id}/compare` | Same product on other platforms from DB |
| `GET` | `/v1/products/{id}/similar?limit=` | Similar products from DB by brand + platform |
| `GET` | `/v1/offers?limit=` | Top price drops today, sorted by drop % |
| `GET` | `/v1/coupons?limit=` | Aggregated bank offers across all products |

### Phase 3 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/products/{id}/recommendation` | ML-based verdict: `{verdict, message, confidence, reasoning}` |

---

## 26. Phase Summary

### Phase 1 — MVP Frontend (Start Here)

**Goal:** Replace Streamlit UI completely. All existing functionality working on
`priceping.in`. Deploy to Vercel.

**Pages built:** Landing (`/`) — 12 sections including static deal placeholders,
category pills, bank offers row, how-it-works, recommendation preview, footer CTA.
Dashboard (`/dashboard`), Track (`/track`), Profile (`/profile`), Login (`/login`).

**Product page (Phase 1):** Two-column layout with sticky sidebar. Left column: Hero
(image + identity + spec chips), Key Specs Grid, Price History Chart, Bank Offers,
Description + Features, Full Specifications. Right sidebar: price box (price, buy btn,
track CTA, refresh, share), AI recommendation card, price stats box, target price input.
Breadcrumb navigation. Mobile bottom bar. Client Component rendering.

**Navigation model:** Breadcrumb replaces browser back button. Product page and landing
page are independent standalone pages sharing the same Navbar.

**Auth:** Progressive auth — email only by default, optional password via Profile.

**New FastAPI endpoints:** auth/check, auth/login, auth/set-password, auth/send-otp,
products/{id}/history, products/{id}/track

**New DB columns:** `users.password_hash`

**Hosting:** Vercel (free). Domain: `priceping.in`. API: `api.priceping.in`.

---

### Phase 2 — SEO & Public Pages

**Goal:** Make PricePing discoverable on Google. Product pages, offers, and coupons
indexed. Shareable product URLs with OG images. Landing page deal sections live.

**Pages built:** `/products/[slug]` upgrades to ISR, `/offers` (ISR 30min),
`/coupons` (ISR 30min).

**Landing page additions (Phase 2):** Top Deals section (live, platform filter tabs),
Popular Products section (DB-driven watcher_count), Stats bar DB-driven.

**Product page additions (Phase 2):** Platform Comparison section (left column),
Similar Products carousel (left column), Platform mini comparison (sidebar box 5),
OG image generation (`opengraph-image.jsx`), `generateMetadata()` for SEO.

**New features:** Slug generation, sitemap.xml auto-generation, WhatsApp/social link
previews with product image + price.

**New FastAPI endpoints:** products/by-slug/{slug}, products/{id}/compare,
products/{id}/similar, offers, coupons, stats

**New DB columns:** `products.slug`

---

### Phase 3 — Content, Growth, and AI

**Goal:** Content marketing via blog. Real AI recommendation engine. User review system.

**Pages built:** `/blog` (SSG), `/blog/[slug]` (SSG from MDX)

**Product page additions:** ML-based buying recommendation (swap rule-based function for
API call), user reviews (requires `product_reviews` table).

**New FastAPI endpoints:** products/{id}/recommendation (ML model)

**No new DB columns for blog** — MDX files in repo, no CMS.

---

## 27. Design Decisions and Rationale

### Why Next.js App Router over Pages Router

App Router allows mixing SSG, ISR, and Client Components in the same application at the
per-file level. Dashboard and Track are `'use client'` components. Product pages are ISR
Server Components. This would require significant workarounds in the Pages Router.

### Why ISR over SSR for product pages

SSR rebuilds the HTML on every request, which means a server must be running 24/7. ISR
pre-builds the HTML and serves it as a static file, rebuilding in the background every
60 minutes. For a price-tracking application where prices change every 4 hours (cron
schedule), 60-minute ISR is more than sufficient and costs nothing on Vercel's free tier.

### Why the product detail page starts as a Client Component in Phase 1

In Phase 1, the product page is accessed only by logged-in users navigating from their
dashboard — not by Google. There is no SEO value yet (no slug, no public URL). Starting
as a Client Component means zero new backend work for Phase 1 and allows fast iteration.
The upgrade to ISR in Phase 2 requires adding `export const revalidate = 3600` and
`generateMetadata()` — roughly 30 lines of change to the page file.

### Why the recommendation logic is in `lib/recommendation.js` not in the component

A pure function with no side effects is trivially unit-testable without rendering a
component. When Phase 3 upgrades it to an API call, the change is in `hooks/useRecommendation.js`
(one line), not in the component. The component never knows or cares where the data
came from.

### Why Zustand instead of React Context for global state

React Context triggers a re-render of every component that consumes the context whenever
any value in the context changes. For a store that holds `userEmail`, `trackStep`, and
`deleteTarget`, this would cause unnecessary re-renders across the app. Zustand components
subscribe to specific slices — a component that reads `userEmail` does not re-render when
`deleteTarget` changes.

### Why `product_id` is eliminated from session state

In Streamlit, `session_state.view_product_id` was required because Streamlit has no URL
routing — the product page could not know which product to show without state. In Next.js,
the product ID or slug is in the URL. `ProductDetail.jsx` reads it with `useParams()`.
This makes product pages bookmarkable, shareable, and directly linkable for the first time.

### Why progressive auth instead of mandatory registration

Mandatory registration is the single highest drop-off point in any web application.
PricePing's core value is delivered without an account — paste URL, enter email, done.
A user who has tracked 5 products and received 3 price drop alerts has already experienced
the product's value before being asked to set a password. Conversion to a secured account
at that point is far higher than mandatory upfront registration.

### Why no TypeScript in Phase 1

TypeScript adds significant setup overhead and requires type definitions for every API
response, component prop, and utility function. For a solo developer moving fast in Phase 1,
the compilation errors slow iteration without proportionate benefit. TypeScript can be
added in Phase 3 when the codebase is stable and the API shapes are locked.

### Why a URL input box as hero instead of a banner carousel

Banner carousels are visually busy, slow to load, and convert poorly — they were a
UX pattern from 2012. PricePing's entire value proposition is "paste a URL and track
the price." Making the URL input box the hero of the page communicates that value
instantly and removes one navigation step: the user can begin tracking without clicking
through to `/track` first.

### Why a two-column layout with sticky sidebar on the product page

On a price-tracking product page, the primary actions (buy, track, set target price) must
remain accessible at all times — even when the user has scrolled deep into the specifications
table or the price history chart. PriceDekho puts the buy button at the top of the left
column; once you scroll past it, you have to scroll back. The sticky sidebar solves this:
the buy button and track CTA are always visible without any scroll. On mobile, the sidebar
collapses to a bottom bar for the same reason.

### Why breadcrumb replaces browser back button

A user who arrives at a product page from Google or a WhatsApp link has no browser history
entry for the PricePing landing page — their back button goes to Google, not to
`priceping.in/`. Designing navigation around the back button excludes this entire class of
user. The breadcrumb provides explicit, labelled navigation that works regardless of how the
user arrived at the page.

### Why the landing page sections are independent components

Each section in `components/landing/` is a completely self-contained React component.
Adding a new section (e.g. "Top Brands", "Flash Sale Countdown") requires only creating
a new file and importing it in `app/page.jsx`. Removing a section requires removing one
import. No restructuring of surrounding code. This design anticipates the affiliate
content roadmap — new content types slot in as new components without touching existing
ones.

### Why the `GET /v1/stats` endpoint is deferred to Phase 2

The trust bar numbers in Phase 1 (products tracked, savings, alerts sent) are static
hardcoded values. Making them dynamic requires a `GET /v1/stats` endpoint that runs
aggregate DB queries on every ISR rebuild. Phase 1 avoids this complexity — the static
numbers are directionally accurate and serve the same social proof purpose. Phase 2
makes them accurate with a single new read-only endpoint.
