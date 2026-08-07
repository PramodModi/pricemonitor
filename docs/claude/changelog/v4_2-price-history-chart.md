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

## [v4.2] — Price History Chart + Bug Fixes — August 2026

This phase implements the `GET /v1/products/{id}/history` FastAPI endpoint,
connects the Next.js price history chart to live data, and fixes several
bugs discovered during end-to-end testing of the Track and Product Detail flows.

**Scope of this phase:** New FastAPI history endpoint, price history chart live
data, drop count fix (LAG window function), missing utils functions, already-tracking
detection on Track page and Product Detail sidebar, X-axis deduplication on chart,
Streamlit compatibility fixes, CORS middleware, SidebarPriceBox State C messaging.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/fastapi/api/v1/products.py` | `GET /{product_id}/history` endpoint added; `PricePoint` → `PriceHistoryPoint` rename; `Query`, `timedelta`, `Optional` imports added |
| `app/fastapi/schemas/product.py` | `PriceHistoryPoint` alias, `PriceHistoryOut` class, and `price_history` field added to `ProductOut`; `coerce_price_history` validator added to skip null-price rows |
| `app/repositories/product_repo.py` | `drop_count` query replaced with LAG window function — counts actual price drops not total scrapes; `text` added to SQLAlchemy import |
| `app/repositories/price_history_repo.py` | `get_for_product()` extended with `since` parameter for period filtering; existing `limit` behaviour preserved |
| `app/fastapi/main.py` | `CORSMiddleware` added — allows `localhost:3000` and `priceping.in` |
| `src/lib/utils.js` | `formatDiscount()` added — formats MRP savings amount |
| `src/lib/utils.js` | `formatTrackedSince()` added — formats first_tracked_at as "Month Year" |
| `src/hooks/useProductHistory.js` | Normalises API response — handles both array and `{history:[]}` shapes |
| `src/components/product/PriceHistoryChart.jsx` | Connected to live endpoint; X-axis uses numeric timestamp with per-day tick labels to avoid duplicate date labels |
| `src/components/track/PreviewCard.jsx` | `isAlreadyTracking` detection — shows "already tracking" banner and "View in dashboard" link when stored email matches and product is in catalog |
| `src/components/product/SidebarPriceBox.jsx` | `isTracking` detection via TanStack Query cache — State C shows "✅ Watching this / We'll notify you when the price drops." |

---

### Features

#### FEAT-001 — `GET /v1/products/{id}/history` Endpoint
- **File:** `app/fastapi/api/v1/products.py`
- **Change:** New endpoint returning `{product_id, period, count, history:[{price, checked_at}]}`.
  Period filter: `1m`=30d, `3m`=90d, `6m`=180d, `all`=no cutoff.
  Only `scrape_status='success'` rows with non-null price included.
  Returns 200 + empty list when product exists but has no history yet.
  Returns 404 when product_id not found.
  Period validated by `Query(pattern=...)` — 422 on invalid value.
- **Resolves:** DEF-011 from v4.1.

#### FEAT-002 — Price History Chart Live Data
- **File:** `src/components/product/PriceHistoryChart.jsx`
- **Change:** Chart now fetches from `GET /v1/products/{id}/history` via
  `useProductHistory`. Period toggle (1M/3M/6M/All) triggers a new fetch.
  All-time low reference line rendered as dashed green horizontal line.
  Empty state shown when no data yet. X-axis uses numeric timestamps so
  multiple scrapes on the same day render as separate points with correct
  spacing — one `"5 Aug"` label per day via `dayTicks` array.

#### FEAT-003 — Already-Tracking Detection (Track Page)
- **File:** `src/components/track/PreviewCard.jsx`
- **Change:** `isAlreadyTracking` computed from `storedEmail === typedEmail`
  AND `catalog_data` exists. When true: green banner "✅ You're already
  tracking this product" replaces confirm button; "View in dashboard →" link
  shown. Changing email clears the state — user can track with a different email.

#### FEAT-004 — Already-Tracking Detection (Product Detail Sidebar)
- **File:** `src/components/product/SidebarPriceBox.jsx`
- **Change:** `isTracking` reads from TanStack Query cache at key
  `['items', userEmail]` — no extra API call. State C shows
  "✅ Watching this / We'll notify you when the price drops."
  instead of the active Monitor button.

---

### Fixes

#### FIX-001 — `drop_count` Counting Total Scrapes Instead of Price Drops
- **File:** `app/repositories/product_repo.py`
- **Symptom:** `drop_count` in `price_stats` showed total successful scrape
  count, not the number of times price actually decreased.
- **Root cause:** Original query counted all `scrape_status='success'` rows.
- **Fix:** Replaced with LAG window function subquery — counts rows where
  `price < LAG(price) OVER (ORDER BY checked_at ASC)`.

#### FIX-002 — `PriceHistoryPoint.price` Validation Crash on Dashboard
- **File:** `app/fastapi/schemas/product.py`
- **Symptom:** `ValidationError: Decimal input should be an integer, float,
  string or Decimal object [input_value=None]` on `GET /v1/items`.
- **Root cause:** `ProductOut.price_history` was added without a validator.
  `model_validate(orm_product)` loaded the ORM relationship including
  failed/blocked rows where `price=None`. `PricePoint.price: Decimal`
  rejected null values.
- **Fix:** `coerce_price_history` validator added to `ProductOut` — skips
  ORM rows where `price is None` before Pydantic validation runs.

#### FIX-003 — `formatDiscount` Not Defined in `utils.js`
- **File:** `src/lib/utils.js`
- **Symptom:** `TypeError: formatDiscount is not a function` in `PreviewCard.jsx`.
- **Fix:** `formatDiscount(currentPrice, mrp)` added — returns formatted
  savings string when `mrp > currentPrice`, otherwise `null`.

#### FIX-004 — `formatTrackedSince` Not Defined in `utils.js`
- **File:** `src/lib/utils.js`
- **Symptom:** `TypeError: formatTrackedSince is not a function` in `CatalogContext.jsx`.
- **Fix:** `formatTrackedSince(isoStr)` added — delegates to `formatMonthYear`.

#### FIX-005 — `PricePoint` Import Name Mismatch
- **File:** `app/fastapi/api/v1/products.py`
- **Symptom:** `ImportError: cannot import name 'PricePoint' from schemas.product`
  on server start after schema changes.
- **Root cause:** Schema defined `PriceHistoryPoint`; router imported `PricePoint`.
- **Fix:** Import updated to `PriceHistoryPoint`; alias `PriceHistoryPoint = PricePoint`
  added in schema for backward compatibility.

#### FIX-006 — Price History Chart X-Axis Duplicate Date Labels
- **File:** `src/components/product/PriceHistoryChart.jsx`
- **Symptom:** X-axis showed `"5 Aug"` repeated 5–6 times when multiple
  scrapes occurred on the same day.
- **Root cause:** `dataKey="dateLabel"` used formatted string as X value.
  Recharts treated equal strings as the same position, bunching points.
- **Fix:** `dataKey="timestamp"` (milliseconds), `scale="time"`, `type="number"`.
  `dayTicks` array computed from data — one tick per unique calendar day (IST)
  placed at day boundary. Each scrape retains its unique X position.

---

### Deviations from UI Design Document

#### DEV-001 — Product Page `[slug]` is `product_id` UUID in Phase 1
- Carried forward from v4.1 — unchanged.

#### DEV-002 — TargetPriceInput Saves Locally Only in Phase 1
- Carried forward from v4.1 — unchanged.

---

### Configuration

#### CFG-001 — CORS Added to FastAPI
- **File:** `app/fastapi/main.py`
- Added `CORSMiddleware` allowing `http://localhost:3000` (dev) and
  `https://priceping.in` (production).

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not yet implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp`, `products/{id}/track` | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not yet run | Before Profile page goes live |
| DEF-006 | Domain DNS not configured (`priceping.in` → Vercel, `api.priceping.in` → Railway) | Before production deploy |
| DEF-007 | `GET /v1/items` response has no `slug` field — product page navigation uses `product_id` UUID | Phase 2 slug column |
| DEF-008 | Rate limiting not added to FastAPI preview endpoint (`slowapi` — 30/hour) | Phase 2 |
| DEF-009 | TopDeals and PopularProducts sections show placeholder | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not yet built | When auth endpoints are implemented |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **`PATCH /v1/subscriptions/{id}`** | Medium | Add `target_price` field — unlocks TargetPriceInput persistence |
| **Vercel deploy** | Medium | Connect GitHub repo, set `NEXT_PUBLIC_API_URL=https://api.priceping.in`, add custom domain |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Products slug column** | Low | Phase 2 — `products.slug` column + backfill + `GET /v1/products/by-slug/{slug}` |

---

*Archive this file to `docs/changelog/v4_2-price-history-chart.md` when the next phase begins.*
