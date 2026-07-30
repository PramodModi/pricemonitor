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

## [v2.7] — Bug Fixes: Email Notifications & Subscription Deletion — July 2026

This phase fixes two bugs discovered post-v2.6:

1. **Price drop emails were never sent** — every `EmailWorker` notification
   was silently failing due to keyword-argument logger calls raising `TypeError`,
   swallowed by an exception handler that itself crashed the same way.
   Confirmed fixed by local end-to-end test: price drop detected → email received.

2. **Product and price history deleted on unsubscribe** — when the last
   subscriber removed a product, the product row and its full `price_history`
   were cascade-deleted. Product catalog and history are now always retained,
   enabling history charts when the same product is re-tracked.

No migrations required. Two files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/workers/email_worker.py` | All logger calls converted to f-strings (DEV-006); `_infer_platform()` extended to handle Myntra |
| `app/services/subscription_service.py` | Product delete-on-last-unsubscribe block removed; product and price history always retained |

---

### Fixes

#### FIX-001 — Price Drop Emails Silently Failing (Root Cause)
- **Affects:** `app/workers/email_worker.py`
- **Symptom:** Price drops detected and logged correctly by `_write_result()`.
  `NotificationJob` enqueued. No email ever received. No error visible in logs.
- **Root cause:** Six logger calls in `EmailWorker` used keyword arguments
  (`logger.info("msg", product_id=..., error=...)`) which raise `TypeError`
  on standard `logging.Logger` (DEV-006 violation). The `TypeError` propagated
  up to `_process_notification()`, which was caught by the `except Exception`
  block in `run()`. That handler also used keyword-arg logger calls — so it
  crashed too. The entire exception chain was swallowed silently. Every price
  drop notification since v1.0 was dropped without a trace.
- **Why not caught earlier:** `_write_result()` correctly enqueued the
  `NotificationJob` and logged success. The failure happened entirely inside
  `EmailWorker` which runs as a separate daemon thread with its own exception
  boundary. No log output meant no signal that anything was wrong.
- **Fix:** All six logger calls converted to f-strings:
  - `run()` — outer `except` handler
  - `_process_notification()` — dispatch log, fan-out complete log, DB error handler
  - `_deliver_with_retry()` — retry warning, permanent failure log
- **Confirmed:** Local end-to-end test — `current_price` inflated to ₹9,999
  in Supabase, `python -m scraper_entrypoint` run locally, price drop detected,
  email received in inbox.
- **Files:** `app/workers/email_worker.py`

#### FIX-002 — Myntra Products Get Wrong Platform in Email
- **Affects:** `app/workers/email_worker.py` — `_infer_platform()`
- **Symptom:** Price drop emails for Myntra products showed Flipkart branding
  (platform label and icon).
- **Root cause:** `_infer_platform()` was a binary check:
  `"amazon" if "amazon.in" in url else "flipkart"`. Any non-Amazon URL
  including Myntra returned `"flipkart"`.
- **Fix:** Extended to three-way check — `amazon.in` → `"amazon"`,
  `myntra.com` → `"myntra"`, else → `"flipkart"`.
- **Files:** `app/workers/email_worker.py`

#### FIX-003 — Product and Price History Deleted on Last Unsubscribe
- **Affects:** `app/services/subscription_service.py`
- **Symptom:** When a user removed the only tracked product (sole subscriber),
  the product row and all its `price_history` rows were permanently deleted via
  `ProductRepository.delete()` cascade. Re-adding the same product showed no
  history chart.
- **Root cause:** `unsubscribe()` checked `count_for_product()` after deleting
  the subscription — if zero subscribers remained, it called
  `product_repo.delete(product)`, which cascades to `price_history`.
  This was the original MVP design (PRD §FR-4) but conflicts with the goal of
  preserving price history for future subscribers.
- **Fix:** The `remaining == 0` block that called `product_repo.delete()` is
  removed entirely. Only the subscription row is deleted. Product and
  `price_history` are always retained.
- **Side effect:** Orphaned products (zero subscribers) remain in the DB and
  continue being scraped every cron run. Acceptable at current scale (17
  products). A `subscriber_count > 0` filter on `get_all_for_scraping()` can
  skip them in a future phase if needed.
- **Files:** `app/services/subscription_service.py`

---

### Deviations from Design

#### DEV-001 — Product Catalog Never Cleaned Up
- **Affects:** `app/services/subscription_service.py`, PRD §FR-4
- **Original PRD:** "Product record is deleted only if no subscribers remain."
- **Actual:** Product record is never deleted, regardless of subscriber count.
- **Reason:** Preserving price history enables the history chart for returning
  subscribers. An orphaned product in the catalog is a minor storage cost
  compared to losing accumulated price data.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) are still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Future phase — add `subscriber_count > 0` filter |
| DEF-002 | `--reload` flag in local uvicorn startup wipes in-memory `PreviewCache` on any file save, causing 404 on subscription confirm | `app/services/preview_cache.py` | Replace with Redis (known DEF from v2.1) |

---

### Files Modified

| File | Change |
|---|---|
| `app/workers/email_worker.py` | FIX-001: six logger calls → f-strings; FIX-002: `_infer_platform()` extended for Myntra; unused `import threading` removed |
| `app/services/subscription_service.py` | FIX-003: product delete-on-last-unsubscribe removed; `product_deleted` always `False`; `ProductRepository` import retained for future use; docstring and log updated |

---

### Next Phase

| Item | Priority | Description |
|---|---|---|
| Monitor ScraperAPI credits | **Immediate** | Free tier (1,000/month) may exhaust — Myntra costs 10 credits per request |
| Skip orphaned products in scraper | Medium | Filter `get_all_for_scraping()` to products with at least one subscriber — saves ScraperAPI credits |
| Notification preferences | Medium | Per-subscription notify_on_drop / notify_on_rise / pause controls with dashboard UI |
| Wall-clock timeout guard | Medium | Add max cascade duration (~25s) so preview never 504s on Railway's 30s HTTP limit |
| Redis PreviewCache | Low | Replace in-memory cache — eliminates the `--reload` / restart issue permanently |
| All-time low/high badges | Low | Visual badge on dashboard card when current price equals all-time low |

---

*Archive this file to `docs/changelog/v2.7-bug-fixes.md` when the next phase begins.*
