# PriceMonitor — Changelog

All notable changes to design documents and implementation are recorded here.
When a phase is complete, this file is archived to `changelog/` and a new one started.

Format:
- **FEAT** — new feature not in original docs
- **DEV** — deviation from original design
- **FIX** — bug fix during implementation
- **CFG** — new configuration added
- **DEF** — known issue deferred to future phase
- **OPS** — operational/deployment note

---

## [v2.8] — Instant Preview + Dashboard Refresh — July 2026

This phase eliminates the 10–20 second scrape wait on the Track page for products
already in the catalog, adds a `🔄 Refresh` button to every product surface so
users can pull the latest data from the database on demand, replaces the
relative "Xh ago" timestamp with an absolute "Last fetched: DD Mon, HH:MM"
timestamp everywhere, and detects when a user tries to track a product they are
already tracking.

**Key principle:** The Refresh button never triggers a scrape. It is a pure
database read everywhere it appears. Scraping continues to happen only via the
cron scheduler (every 4 hours) and when a brand-new product URL is submitted
for the first time.

No new endpoints. No database migrations. No new dependencies.
Six backend + frontend files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/fastapi/schemas/product.py` | `data_source` field added to `PreviewResponse` |
| `app/fastapi/api/v1/products.py` | Preview endpoint split into Path A (DB-first) and Path B (live scrape) |
| `streamlit_app/components/preview_card.py` | Full rewrite — pure Streamlit, `🔄` button inside card next to price |
| `streamlit_app/components/product_card.py` | Full rewrite — pure Streamlit, buttons inside `st.container`, absolute timestamp |
| `streamlit_app/pages/dashboard.py` | `force_items_reload` session flag added |
| `streamlit_app/pages/product.py` | `product_detail_data` session cache, `🔄 Refresh` button, absolute timestamp |
| `streamlit_app/pages/track.py` | Already-tracking detection on preview step |

---

### Features

#### FEAT-001 — Instant Preview for Known Products (Path A)
- **Affects:** `app/fastapi/api/v1/products.py`, `app/fastapi/schemas/product.py`
- **Before:** `POST /v1/products/preview` always ran a live Playwright scrape
  before returning, blocking the user for 10–20 seconds regardless of whether
  the product was already in the database.
- **After:** The DB lookup is performed **before** the scrape. If the product is
  found by `platform + marketplace_product_id`, the endpoint returns DB data
  immediately (< 1 second). The scrape path only runs for genuinely new products.
- **Two paths:**
  - **Path A — DB hit:** Build `LiveData` from the existing `Product` ORM row.
    `live_data.scraped_at` is populated from `product.last_checked_at`.
    `data_source = "database"`. No scrape.
  - **Path B — DB miss:** Live scrape runs as before. `data_source = "live_scrape"`.
    Unchanged in every respect from pre-v2.8.
- **`data_source` field:** Added to `PreviewResponse` schema. Tells the Streamlit
  UI which path was taken. The `🔄` button on the preview card is shown only
  when `catalog_data.product_id` is present (i.e. Path A or a rare Path B with
  ASIN redirect resolution). Not shown for brand-new products.
- **`_build_catalog_data()` helper:** Extracted from the inline Path B logic
  into a shared function called by both paths. Builds `CatalogData` from an
  existing `Product` ORM row. `price_change_indicator` is only computed in
  Path B (live scrape vs stored price); omitted in Path A since no live price
  is available to compare.
- **Files:** `app/fastapi/schemas/product.py`, `app/fastapi/api/v1/products.py`

#### FEAT-002 — Refresh Button on Every Product Surface
- **Affects:** `preview_card.py`, `product_card.py`, `product.py`
- **Behaviour:** Calls `GET /v1/products/{product_id}` — a pure database read,
  no scraping. Updates the display with whatever the DB currently holds.
  The user sees the latest price the cron has written since their last view.
- **Three locations:**
  - **Preview card:** `🔄` button appears next to the price, inside the card
    container. Only rendered when `catalog_data.product_id` is available.
    On click: re-fetches product, updates `live_data` fields in
    `st.session_state.preview_result`, reruns.
  - **Dashboard card:** `🔄 Refresh` button inside the card container between
    View and Remove. On click: sets `st.session_state.force_items_reload = True`,
    reruns. Dashboard re-fetches `GET /items` which returns updated data for
    all cards.
  - **Product Details page:** `🔄 Refresh` button placed below price, next to
    "Last fetched" timestamp. On click: re-fetches product, updates
    `st.session_state.product_detail_data`, reruns. Page re-renders with fresh
    data without navigating away.
- **Files:** `streamlit_app/components/preview_card.py`,
  `streamlit_app/components/product_card.py`, `streamlit_app/pages/product.py`

#### FEAT-003 — Absolute "Last Fetched" Timestamp Everywhere
- **Affects:** `preview_card.py`, `product_card.py`, `product.py`
- **Before:** Dashboard showed relative "Xh ago" via `_format_last_checked()`.
  Preview card showed "Live price from marketplace".
- **After:** All three surfaces show `"Last fetched: 30 Jul, 6:00 AM"` —
  absolute date and time derived from `product.last_checked_at`.
  Relative timestamps removed entirely.
- **Helper:** `_format_last_fetched(ts: str | None) -> str` — formats a UTC
  ISO timestamp as `"%-d %b, %-I:%M %p"` (e.g. `"30 Jul, 6:00 AM"`).
  Returns `"Never fetched"` when `ts` is `None`. Defined identically in all
  three files (no shared module — keeps component files self-contained).
- **Files:** `streamlit_app/components/preview_card.py`,
  `streamlit_app/components/product_card.py`, `streamlit_app/pages/product.py`

#### FEAT-004 — Already-Tracking Detection on Preview Step
- **Affects:** `streamlit_app/pages/track.py`
- **Behaviour:** When the user enters their email in the preview step, the app
  checks whether they already track the previewed product. If yes, the
  `✅ Yes, track it` button is replaced with `st.info("✅ Already in your
  tracking list.")`. The `← Try a different URL` button remains so the user
  can move on.
- **Implementation:** `_is_already_tracking(email, product_id)` helper calls
  `GET /items` for the entered email and checks if `product_id` from
  `catalog_data` appears in the returned subscription list. Returns `False`
  on any API error so the check never blocks the flow.
- **Guard conditions:** Check is skipped when email is empty or has no `@`,
  when `catalog_data` is `None` (new product — cannot be in any tracking list),
  or when `product_id` is empty. Track button always shown for brand-new products.
- **Files:** `streamlit_app/pages/track.py`

---

### Fixes

#### FIX-001 — Refresh Button Rendered Outside Card (Product Details Page)
- **Affects:** `streamlit_app/pages/product.py`
- **Symptom:** The `🔄` button was placed in a `st.columns([5, 1])` split
  inside `col_info`. Streamlit stretched the two columns across the full width
  of `col_info`, pushing the button to the far right edge of the page — visually
  disconnected from the price and timestamp it belongs to.
- **Fix:** Removed the column split. Timestamp rendered as `st.markdown` HTML
  paragraph. Button rendered as a plain `st.button` immediately below it.
  Both left-aligned inside `col_info`, naturally adjacent to the price.
- **Files:** `streamlit_app/pages/product.py`

#### FIX-002 — Refresh Button Rendered Below and Outside Preview Card
- **Affects:** `streamlit_app/components/preview_card.py`
- **Symptom:** The entire preview card was rendered as a single `_render_html()`
  HTML block. The `🔄` button was appended as a separate `st.button()` after
  the HTML block, appearing below and outside the card boundary — not adjacent
  to the price.
- **Root cause:** Streamlit cannot place interactive widgets inside an HTML
  string rendered via `st.markdown`. The button had to be a separate Streamlit
  element, which Streamlit placed in the next available vertical slot.
- **Fix:** Rewrote `preview_card.py` entirely using native Streamlit elements
  inside `st.container(border=True)`. The `🔄` button is placed in a tight
  `st.columns([3, 1, 2])` split inside `col_info`, immediately to the right of
  the price and timestamp. The empty spacer column (`[2]`) prevents the button
  from stretching to the right edge.
- **Files:** `streamlit_app/components/preview_card.py`

#### FIX-003 — Buttons Outside Card on Dashboard, Double Timestamp Prefix
- **Affects:** `streamlit_app/components/product_card.py`
- **Symptom 1:** Dashboard showed `"Last checked: Last fetched: 31 Jul, 8:38 AM"` —
  a doubled prefix. The `product_card.html` template had `"Last checked:"` hardcoded,
  and the Python code replaced `{last_checked}` with `"Last fetched: 31 Jul, ..."`,
  producing both strings concatenated.
- **Symptom 2:** View, Refresh, and Remove buttons were rendered in a separate
  `st.columns([8, 2])` column outside the card HTML, appearing as a detached
  button column to the right of each card.
- **Root cause:** Both symptoms stem from the same architectural issue — the
  card was rendered as an external HTML template (`product_card.html`) with
  Streamlit buttons appended in a separate column outside it.
- **Fix:** Rewrote `product_card.py` entirely using native Streamlit elements
  inside `st.container(border=True)`. HTML template dependency removed.
  All three buttons (View, Refresh, Remove) are rendered inside the container
  in `col_btns`, visually part of the card. Timestamp rendered via `st.caption()`
  with a single `"Last fetched: "` prefix.
- **Files:** `streamlit_app/components/product_card.py`

---

### Deviations from Design

#### DEV-001 — Preview Card and Product Card Rewritten as Pure Streamlit
- **Affects:** `preview_card.py`, `product_card.py`
- **Original design:** Both components used `st.markdown(html, unsafe_allow_html=True)`
  to render a styled HTML card loaded from `static/html/*.html` template files,
  with Streamlit buttons placed in adjacent columns outside the HTML block.
- **Actual:** Both components are now pure Streamlit (`st.container`,
  `st.columns`, `st.markdown`, `st.image`, `st.caption`, `st.button`).
  The `product_card.html` template file is no longer used by `product_card.py`.
  The `_render_html()` and `_load_html()` helpers are removed from both files.
- **Reason:** Streamlit cannot place interactive widgets (`st.button`) inside
  an HTML string. The Refresh button must be a Streamlit widget. Moving the
  button inside the card required the card itself to be a Streamlit container.
  The visual result is equivalent and benefits from Streamlit's built-in
  dark/light theme support.

#### DEV-002 — `product_detail_data` Session Cache on Product Details Page
- **Affects:** `streamlit_app/pages/product.py`
- **Original design:** Product data was fetched fresh on every page render via
  `get_product()` at the top of `product.py`.
- **Actual:** Product data is cached in `st.session_state.product_detail_data`
  on first load and updated by the Refresh button. Subsequent reruns (e.g. from
  button clicks) use the cached value without re-fetching. The cache is cleared
  when `view_product_id` changes (user navigates to a different product).
- **Reason:** Without caching, the Refresh button's `st.rerun()` would trigger
  a fresh `get_product()` call on the rerun, overwriting the just-refreshed data
  with whatever was in the cache before. The session cache ensures the Refresh
  result persists across the rerun cycle.

#### DEV-003 — Spinner Text Updated on Track Page
- **Affects:** `streamlit_app/pages/track.py`
- **Original:** Spinner showed `"Fetching live product details — this may take
  up to 30 seconds..."` — accurate for Path B but misleading for Path A which
  returns in under 1 second.
- **Actual:** Spinner shows `"Fetching product details..."` — neutral wording
  correct for both paths.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Future phase — add `subscriber_count > 0` filter |
| DEF-002 | `--reload` flag in local uvicorn wipes in-memory `PreviewCache` on file save, causing 404 on confirm | `app/services/preview_cache.py` | Replace with Redis |
| DEF-003 | `social_share` query param not stripped from Amazon canonical URLs — stored in DB with trailing junk | `app/services/url_validator.py` — `_AMAZON_STRIP_PARAMS` | Next phase — add `social_share` to strip set |
| DEF-004 | UTM params (`utm_source`, `utm_medium`, `utm_campaign`, `shared`) not stripped from Myntra URLs — stored dirty in DB | `app/services/url_validator.py` — no `_MYNTRA_STRIP_PARAMS` defined | Next phase — add Myntra strip params |
| DEF-005 | `amzn.in` short URL stored as canonical `url` in DB — if same short URL resubmitted, Path A gets `marketplace_product_id=""`, falls to Path B and scrapes unnecessarily | `app/services/product_sync.py` | Future phase — update stored URL to resolved `www.amazon.in/dp/ASIN` after scrape |
| DEF-006 | Wall-clock timeout guard missing — preview Path B can 504 on Railway's 30s HTTP limit if full ScraperEngine cascade runs | `app/fastapi/api/v1/products.py` | Future phase |

---

### Files Modified

| File | Change |
|---|---|
| `app/fastapi/schemas/product.py` | FEAT-001: `data_source: str` added to `PreviewResponse` |
| `app/fastapi/api/v1/products.py` | FEAT-001: Preview endpoint split into Path A (DB hit, instant) and Path B (DB miss, live scrape). `_build_catalog_data()` helper extracted. `data_source` set on all response paths |
| `streamlit_app/components/preview_card.py` | FEAT-002, FEAT-003, FIX-002, DEV-001: Full rewrite as pure Streamlit. `🔄` button inside container next to price. `_format_last_fetched()` replaces "Live price from marketplace". HTML template dependency removed |
| `streamlit_app/components/product_card.py` | FEAT-002, FEAT-003, FIX-003, DEV-001: Full rewrite as pure Streamlit. All three buttons inside `st.container`. `_format_last_fetched()` replaces relative "Xh ago". HTML template dependency removed |
| `streamlit_app/pages/dashboard.py` | FEAT-002: `force_items_reload: False` added to `init_session_state()`. Items re-fetched when flag is set by dashboard card Refresh button |
| `streamlit_app/pages/product.py` | FEAT-002, FEAT-003, FIX-001, DEV-002: `product_detail_data` session cache added. `🔄 Refresh` button placed below price. `_format_last_fetched()` replaces raw ISO timestamp. `PLATFORM_DISPLAY` dict added for consistent platform labels |
| `streamlit_app/pages/track.py` | FEAT-004: `_is_already_tracking()` helper added. Already-tracking detection runs when email is entered. Track button replaced with `st.info` message when product already in user's list. Spinner text updated (DEV-003) |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| Fix `url_validator.py` — strip params | **High** | Add `social_share` to `_AMAZON_STRIP_PARAMS`. Add `_MYNTRA_STRIP_PARAMS` for UTM params. Clean 2 existing dirty Myntra URLs in DB via SQL UPDATE |
| Skip orphaned products in scraper | Medium | Filter `get_all_for_scraping()` to products with at least one subscriber — saves ScraperAPI credits |
| Notification preferences | Medium | Per-subscription `notify_on_drop` / `notify_on_rise` / pause controls. 6 new columns on `subscriptions`, 1 on `users`. Full design already written |
| All-time low/high badges | Low | Visual badge on dashboard card when current price equals all-time low |
| Redis PreviewCache | Low | Replace in-memory cache — eliminates the `--reload` / restart issue permanently |

---

*Archive this file to `docs/changelog/v2.8-instant-preview.md` when the next phase begins.*
