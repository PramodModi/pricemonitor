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

## [v2.6] — Price History Chart — July 2026

This phase adds a price history chart to the product details page. The
`price_history` table has been accumulating data since v1.0 — this phase
exposes it in the UI. No new migrations or dependencies are required.

---

### Summary of Changes

| Area | Change |
|---|---|
| `price_history_repo.py` | `get_for_product()` method added — queries successful price rows oldest-first for charting |
| `app/fastapi/schemas/product.py` | `PricePoint` model added; `price_history` field added to `ProductOut`; `coerce_price_history` validator added |
| `app/fastapi/api/v1/products.py` | `get_product()` now populates `price_history` via `PriceHistoryRepository.get_for_product()` |
| `streamlit_app/pages/product.py` | Price history chart rendered below stats metrics; "Back to My Items" button moved to top |

---

### Features

#### FEAT-001 — Price History Chart on Product Details Page
- **Affects:** `streamlit_app/pages/product.py`
- **Change:** A line chart of price over time is rendered below the All-Time
  Low / All-Time High / Price Drops metrics on the product details page.
  Uses Streamlit's built-in `st.line_chart` — no new frontend dependency.
- **X-axis:** Date formatted as `"D MMM"` (e.g. `"14 Jul"`) — full datetime
  is preserved in the DataFrame so multiple readings on the same date remain
  as separate data points and are not dropped or averaged.
- **Data source:** `price_history` rows with `scrape_status='success'` and
  `price IS NOT NULL`, last 90 entries, ordered oldest → newest.
- **Guards:**
  - `len(history) >= 2` — chart only renders when at least two points exist;
    a single point renders a caption instead.
  - `history` absent from response — silently skipped (backward-compatible
    with any cached API responses).
- **Loading state:** `st.spinner("Loading price chart...")` wraps DataFrame
  preparation. `st.line_chart` is called outside the spinner so it appears
  cleanly after the spinner dismisses.

#### FEAT-002 — `get_for_product()` on PriceHistoryRepository
- **Affects:** `app/repositories/price_history_repo.py`
- **Change:** New read method alongside the existing `insert()`. Returns up
  to `limit` (default 90) successful price rows for a product, ordered
  oldest-first for direct use in chart rendering.
- **Filter:** `scrape_status='success'` AND `price IS NOT NULL` — excludes
  failed and blocked scrape rows which carry `price=None`.

#### FEAT-003 — `price_history` Field on `ProductOut`
- **Affects:** `app/fastapi/schemas/product.py`, `app/fastapi/api/v1/products.py`
- **Change:** `ProductOut` gains a `price_history: list[PricePoint] = []`
  field. `PricePoint` is a new two-field Pydantic model (`checked_at`,
  `price`). Default is an empty list — fully backward-compatible with any
  existing callers that do not use this field.
- **Router:** `get_product()` populates the field via
  `PriceHistoryRepository.get_for_product()`.

#### FEAT-004 — "Back to My Items" Button Moved to Top
- **Affects:** `streamlit_app/pages/product.py`
- **Change:** Button repositioned from the bottom of the page to immediately
  below the page title — visible without scrolling. Bottom divider and
  duplicate button removed.

---

### Fixes

#### FIX-001 — `model_validate` on ORM Object Fails with `PriceHistory` ORM Rows
- **Affects:** `app/fastapi/schemas/product.py`
- **Symptom:** `GET /v1/items` returned 500:
  ```
  pydantic_core._pydantic_core.ValidationError: 2 validation errors for ProductOut
  price_history.0
    Input should be a valid dictionary or instance of PricePoint
  ```
- **Root cause:** `items.py` builds `ProductOut` via
  `ProductOut.model_validate(sub.product)` — passing a raw ORM `Product`
  object. Pydantic's `from_attributes=True` reads the `price_history` ORM
  relationship, returning a list of `PriceHistory` ORM objects. Pydantic
  could not coerce these into `PricePoint`.
- **Fix:** `coerce_price_history` `@field_validator(mode="before")` added to
  `ProductOut`. Converts ORM objects to `{"checked_at": ..., "price": ...}`
  dicts before Pydantic validates them. Plain dicts (from the `get_product`
  handler path) pass through unchanged.

#### FIX-002 — `price=None` Rows Crash `PricePoint` Validation via `model_validate`
- **Affects:** `app/fastapi/schemas/product.py`
- **Symptom:** `GET /v1/items` returned 500 after FIX-001:
  ```
  pydantic_core._pydantic_core.ValidationError: 1 validation error for ProductOut
  price_history.1.price
    Decimal input should be an integer, float, string or Decimal object
    input_value=None, input_type=NoneType
  ```
- **Root cause:** The ORM relationship returns all `price_history` rows
  including those with `price=None` (failed/blocked scrapes). The
  `coerce_price_history` validator from FIX-001 was passing these through —
  `PricePoint.price` is non-optional and cannot accept `None`.
- **Fix:** Validator now skips any item where `price` is `None` — both in
  the ORM path (`item.price is not None`) and the dict path
  (`item.get("price") is not None`). Mirrors the SQL filter in
  `get_for_product()`.

#### FIX-003 — Missing `select` Import in `price_history_repo.py`
- **Affects:** `app/repositories/price_history_repo.py`
- **Symptom:** Would have raised `NameError: name 'select' is not defined`
  on first call to `get_for_product()`.
- **Root cause:** `get_for_product()` uses SQLAlchemy `select()` but the
  import was not added when the method was written.
- **Fix:** `from sqlalchemy import select` added to imports.

---

### Deviations from Design

#### DEV-001 — `price_history` Embedded in `ProductOut` Instead of Separate Endpoint
- **Original plan:** A new `GET /v1/products/{product_id}/price-history`
  endpoint was considered.
- **Actual:** `price_history` added as a field on the existing `ProductOut`
  response from `GET /v1/products/{product_id}`.
- **Reason:** Avoids a second HTTP round-trip from Streamlit. The dashboard
  (`GET /v1/items`) also uses `ProductOut` — the field defaults to `[]` there
  since `items.py` does not call `get_for_product()`, keeping that path
  unaffected.

#### DEV-002 — `coerce_price_history` Validator Handles Two Distinct Call Paths
- **Affects:** `app/fastapi/schemas/product.py`
- **Context:** `ProductOut` is constructed in two different ways across the
  codebase:
  1. `get_product()` — explicit field passing with `PricePoint` dicts
  2. `items.py` — `ProductOut.model_validate(orm_product)` reads ORM relationship
- **Actual:** The validator handles both paths in a single `@field_validator`
  using `isinstance` and `hasattr` checks. Neither call site was modified.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | `%-d` date format (day without leading zero) is Linux/macOS only — would need `%#d` on Windows. Streamlit Cloud runs Linux so this is a non-issue in production. | `streamlit_app/pages/product.py` | Non-issue for current deployment |
| DEF-002 | Chart x-axis shows duplicate date labels when multiple readings exist on the same day (e.g. `"29 Jul"` appears twice). Data points are correct — only the label repeats. | `streamlit_app/pages/product.py` | Phase 3 UI polish |
| DEF-003 | `price_history` is loaded for every `GET /v1/products/{product_id}` call even when the caller (e.g. post-subscription confirm flow) does not need it. Acceptable for current volume. | `app/fastapi/api/v1/products.py` | Low priority |

---

### Files Modified

| File | Change |
|---|---|
| `app/repositories/price_history_repo.py` | `get_for_product()` method added; `from sqlalchemy import select` import added |
| `app/fastapi/schemas/product.py` | `PricePoint` model added; `price_history` field added to `ProductOut`; `coerce_price_history` validator added; `field_validator` added to pydantic imports |
| `app/fastapi/api/v1/products.py` | `PricePoint` added to schema import; `PriceHistoryRepository` import added; `get_product()` populates `price_history` |
| `streamlit_app/pages/product.py` | Price history chart added; "Back to My Items" button moved to top; bottom divider removed |

---

### Next Phase

| Item | Priority | Description |
|---|---|---|
| Monitor ScraperAPI credits | **Immediate** | Free tier (1,000/month) may exhaust quickly. Monitor dashboard and upgrade plan if needed. |
| Clean Flipkart search URLs | High | Strip search params from Flipkart URLs at subscription time — reduces ScraperAPI credit usage |
| Wall-clock timeout guard | High | Add a max cascade duration (~25s) so preview never 504s on Railway's 30s limit |
| Notification preferences | Medium | Per-subscription notify_on_drop / notify_on_rise / pause controls with dashboard UI |
| All-time low/high badges | Medium | Visual badges on dashboard cards when current price equals all-time low |
| LLM extraction layer | Low | Layer 6b via Groq free API — handles CSS drift cases |
| Redis PreviewCache | Low | Replace in-memory cache with Redis for multi-instance deployments |
| Auth | Low | User login / session management |

---

*Archive this file to `docs/changelog/v2.6-price-history-chart.md` when the next phase begins.*
