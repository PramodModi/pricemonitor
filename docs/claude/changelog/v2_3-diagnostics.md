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

## [v2.3] — Diagnostics & UI Fixes — July 2026

This phase fixes the `scrape_diagnostics` write path (was silently failing since
v2.1 cutover), adds trigger/triggered_by observability columns, and adds a
"Track Another Item" button to the Streamlit UI.

---

### Summary of Changes

| Area | Change |
|---|---|
| `scraper_worker.py` | Fixed `_write_diagnostic()` — wrong argument names passed to `repo.insert()` |
| `scraper_worker.py` | `_write_diagnostic()` now accepts `trigger` and `triggered_by` params |
| `scraper_worker.py` | Cron path passes `trigger="scheduler"`, `triggered_by="Github"` |
| `products.py` (preview route) | Diagnostic write added after v2 scrape — was never written in preview path |
| `products.py` (preview route) | `db.rollback()` added to diagnostic except block to protect shared session |
| `models.py` | Primary key renamed `id` → `diagnostic_id` to match migration |
| `models.py` | Added `trigger` and `triggered_by` columns |
| `repository.py` | Added `trigger`, `triggered_by`, `url`, `price_found` params to `insert()` |
| `streamlit_app/pages/track.py` | "Track Another Item" button added to success screen |
| Alembic | Three new migrations run against Supabase |

---

### Features

#### FEAT-001 — Scrape Diagnostics Now Writing in Both Paths
- **Affects:** `app/workers/scraper_worker.py`, `app/fastapi/api/v1/products.py`
- **Change:** `scrape_diagnostics` rows are now written on every scrape attempt —
  both from the scheduled cron path (`ScraperWorker._write_diagnostic()`) and from
  the user preview path (`POST /v1/products/preview`).
- **Previously:** Cron path had `_write_diagnostic()` defined but passing wrong
  argument names — all writes failed silently. Preview path had no diagnostic write
  at all.

#### FEAT-002 — Trigger and Triggered-By Observability
- **Affects:** `scrape_diagnostics` table, `models.py`, `repository.py`, `scraper_worker.py`, `products.py`
- **Change:** Two new columns added to `scrape_diagnostics`:
  - `trigger` — `"scheduler"` for GitHub Actions cron runs, `"preview"` for user-initiated previews
  - `triggered_by` — `"Github"` for cron runs, user email if available, `null` if not
- **Query to monitor:**
  ```sql
  SELECT scraped_at, portal, trigger, triggered_by, status,
         extraction_method, total_duration_ms, error_type
  FROM scrape_diagnostics
  ORDER BY scraped_at DESC
  LIMIT 20;
  ```

#### FEAT-003 — "Track Another Item" Button on Success Screen
- **Affects:** `streamlit_app/pages/track.py`
- **Change:** Success screen previously had two buttons ("View Product Details" and
  "Back to Dashboard") with no way to add another product without navigating away.
  A third button "➕ Track Another Item" added — resets `track_step` to `"input"`
  and reruns, returning the user directly to the URL input form.
- **Implementation:** Three-column layout replaces two-column layout on success screen.

---

### Fixes

#### FIX-001 — `_write_diagnostic()` Passing Wrong Argument Names
- **Affects:** `app/workers/scraper_worker.py`
- **Symptom:** `scrape_diagnostics` table had zero rows despite cron jobs running
  successfully. Warning log `"Failed to write scrape diagnostic"` was suppressed
  since `_write_diagnostic()` swallows all exceptions.
- **Root cause:** `_write_diagnostic()` called `repo.insert()` with:
  - `success=response.success` (boolean) — but `insert()` expects `status: str`
  - Missing `scrape_job_id` (non-nullable in ORM model)
  - Missing `url`
  - `layers_attempted` and `layers_failed` passed as pre-joined strings — but
    `repo.insert()` already does the join internally, causing double-joining
- **Fix:** Corrected all argument names and types. Added `status` derivation logic
  from `response.success` and `response.error_type`.

#### FIX-002 — Preview Route Never Wrote Diagnostic Row
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** Preview scrapes (user-initiated) produced no rows in `scrape_diagnostics`
- **Root cause:** `_write_diagnostic()` only exists on `ScraperWorker`. The preview
  route calls `GenericScraper` directly and had no diagnostic write at all.
- **Fix:** Diagnostic write added inline in the preview route after `_scraper_v2.scrape()`
  returns, with its own `try/except` and `db.rollback()` on failure.

#### FIX-003 — Diagnostic Failure Poisoned Shared DB Session
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** When diagnostic insert failed (column mismatch), the shared `db`
  session was left in `PendingRollbackError` state — crashing the rest of the
  request including the product lookup and preview cache write.
- **Root cause:** Failed `db.commit()` inside diagnostic block left the session
  in a broken transaction state. No `db.rollback()` was called.
- **Fix:** `db.rollback()` added to the diagnostic `except` block. Diagnostic
  failures are now fully isolated — preview continues normally regardless.

#### FIX-004 — ORM Primary Key Name Mismatch
- **Affects:** `app/scraper_v2/diagnostics/models.py`
- **Symptom:** `column "id" of relation "scrape_diagnostics" does not exist`
- **Root cause:** ORM model defined primary key as `id` but Alembic migration
  created the column as `diagnostic_id`.
- **Fix:** Renamed `id` → `diagnostic_id` in ORM model to match the migration.

#### FIX-005 — `status` Column Did Not Exist in DB
- **Affects:** `scrape_diagnostics` table, `models.py`, `repository.py`
- **Symptom:** `column "status" of relation "scrape_diagnostics" does not exist`
- **Root cause:** Original migration created `success` (boolean). During the
  diagnostic write rewrite, the column was renamed to `status` (string) in the
  ORM model and repository — but no migration was run to rename it in the DB.
- **Fix:** Alembic migration renamed `success → status` with type conversion:
  `CASE WHEN success THEN 'success' ELSE 'failed' END`.

---

### Deviations from Design

#### DEV-001 — Diagnostic Write Uses Shared Request DB Session in Preview Route
- **Affects:** `app/fastapi/api/v1/products.py`
- **Original intent:** Diagnostic writes open their own `SessionLocal()` (as in
  `ScraperWorker._write_diagnostic()`)
- **Actual:** Preview route reuses the existing `db` session from `Depends(get_db)`
- **Reason:** Preview route is a FastAPI endpoint — `db` is already open and
  managed by the request lifecycle. Opening a second session is unnecessary overhead.
  `db.rollback()` on failure ensures isolation.

---

### Migrations Run

| Migration | Change |
|---|---|
| `<hash>_add_trigger_columns_to_scrape_diagnostics.py` | Added `trigger` (VARCHAR 50) and `triggered_by` (VARCHAR 255) |
| `<hash>_add_url_and_price_found_to_scrape_diagnostics.py` | Added `url` (TEXT) and `price_found` (NUMERIC 12,2) |
| `<hash>_rename_success_to_status_in_scrape_diagnostics.py` | Renamed `success` BOOLEAN → `status` VARCHAR with data migration |

---

### Files Modified

| File | Change |
|---|---|
| `app/workers/scraper_worker.py` | Fixed `_write_diagnostic()` argument names; added `trigger`/`triggered_by` params; cron path passes `trigger="scheduler"`, `triggered_by="Github"` |
| `app/fastapi/api/v1/products.py` | Diagnostic write added to preview route; `db.rollback()` on diagnostic failure |
| `app/scraper_v2/diagnostics/models.py` | Primary key renamed `id` → `diagnostic_id`; added `trigger`, `triggered_by`, `url`, `price_found` columns |
| `app/scraper_v2/diagnostics/repository.py` | Added `trigger`, `triggered_by`, `url`, `price_found` params to `insert()`; updated debug log |
| `streamlit_app/pages/track.py` | Three-column success screen with "Track Another Item" button |

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | `triggered_by` is always `null` for preview scrapes — email not available until confirm step | `app/fastapi/api/v1/products.py` | Phase 3 — backfill on confirm |
| DEF-002 | Cron path `triggered_by` hardcoded as `"Github"` — not linked to actual GitHub Actions run ID | `app/workers/scraper_worker.py` | Low priority |
| DEF-003 | Residential proxy fallback (ScraperAPIFallback) still not implemented — Railway IP blocks remain a risk | `app/scraper_v2/scrapers/base.py` | Phase 3 |

---

*Archive this file to `docs/changelog/v2.3-diagnostics.md` when Phase 3 begins.*
