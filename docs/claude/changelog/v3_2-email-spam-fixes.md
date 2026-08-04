# PriceMonitor — Changelog

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

## [v3.2] — Email Spam Fixes + Preview Crash Fix — August 2026

This phase fixes two independent issues discovered in production:

**1. Price drop and confirmation emails going to spam** — subject lines contained
price-centric phrasing and rupee symbols that spam filters flag, and both email
types were missing the `List-Unsubscribe` header that Gmail requires to treat
mail as managed rather than unsolicited. Four content files updated across both
email types.

**2. `preview_product` 500 crash on PATH B (new product)** — a redundant local
`import ScraperEngine` inside the function body caused Python to treat
`ScraperEngine` as a local variable throughout the entire function, making the
earlier top-level usage at `with ScraperEngine() as engine:` raise
`UnboundLocalError`. Same latent bug present in `_background_scrape_and_store`.

No database migrations. No new dependencies. Five files changed.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/notifications/email_sender.py` | Subject line changed; `List-Unsubscribe` header added to both email methods; unused imports removed |
| `app/notifications/content/price_drop.py` | `get_subject()` updated; `PLATFORM_LABEL`/`PLATFORM_ICON` extended for Myntra; unused `Decimal` import removed |
| `app/notifications/templates/price_drop.txt` | Header and opening line softened |
| `app/notifications/templates/price_drop.html` | Header tagline softened; footer broken-sentence bug fixed |
| `app/fastapi/api/v1/products.py` | Two redundant local `ScraperEngine` imports removed — fixes `UnboundLocalError` crash on PATH B |

---

### Fixes

#### FIX-001 — Price Drop and Confirmation Emails Going to Spam

**Affects:** `app/notifications/email_sender.py`, `app/notifications/content/price_drop.py`,
`app/notifications/templates/price_drop.txt`, `app/notifications/templates/price_drop.html`

**Root causes (three independent signals):**

1. **Subject line** — `"Price drop: {product_name} is now ₹{price}"` leads with
   price-centric phrasing and a rupee symbol. Spam filters are trained on
   promotional mail patterns; this subject closely matched them.

2. **Missing `List-Unsubscribe` header** — Gmail and other providers require this
   header to classify mail as a managed subscription rather than unsolicited bulk
   mail. Without it, any recurring alert pattern is treated with suspicion
   regardless of content.

3. **Plain text ALL CAPS header** — `"PRICEMONITOR — TRACKING CONFIRMED"` and
   `"PRICEMONITOR — PRICE DROP ALERT"` in the plain-text body. ALL CAPS words
   are a classic spam signal in plain-text email.

**Fixes applied:**

- **Subject line** — changed from `"Price drop: {name} is now ₹{price}"` to
  `"Your tracked item dropped — {name}"`. Leads with context, no price, no
  currency symbol. Built inline in `send_price_drop()` — `get_subject()` import
  removed from `email_sender.py` as it was no longer called there.

- **`List-Unsubscribe` header** — added to both `send_price_drop()` and
  `send_subscription_confirmation()` via the SendGrid `Header` object:
  ```python
  from sendgrid.helpers.mail import Mail, Header
  message.header = Header("List-Unsubscribe", f"<{settings.dashboard_url}>")
  ```
  Points to the dashboard where users can remove tracked items.

- **Plain text headers softened** — `price_drop.txt`: `"PRICE DROP ALERT"` →
  `"PRICE ALERT"`, opening line reworded. `send_subscription_confirmation()`
  plain body: `"PRICEMONITOR — TRACKING CONFIRMED"` → `"Pricemonitor — Tracking
  confirmed"`.

- **HTML tagline softened** — `price_drop.html` Block 1: `"Price Drop Alert"` →
  `"Price Alert"`.

**Confirmed:** Emails no longer going to spam after changes. Domain authentication
(SPF + DKIM + DMARC) remains the highest-impact remaining action — requires DNS
access to `pricewatch.app` domain, no code change.

---

#### FIX-002 — Footer Broken Sentence in HTML Email Template

**Affects:** `app/notifications/templates/price_drop.html`

**Symptom:** Footer rendered as: *"...visit your dashboard and remove the item.
[dashboard]."* — the word "dashboard" appeared twice, once from
`{{footer_unsubscribe}}` and once from a hardcoded `<a>dashboard</a>` link that
was meant to be the clickable word inside the sentence.

**Root cause:** `{{footer_unsubscribe}}` expanded to the full sentence *"To stop
tracking, visit your dashboard and remove the item."* The template then appended
a separate hardcoded `<a href="{{dashboard_url}}">dashboard</a>.` fragment,
producing a grammatically broken duplicate.

**Fix:** Replaced `{{footer_unsubscribe}}` + hardcoded fragment with a single
clean sentence directly in the template:
```html
To stop tracking, visit your
<a href="{{dashboard_url}}" style="color:#4b5563;">dashboard</a>
and remove the item.
```
`{{footer_unsubscribe}}` placeholder removed from template. The `FOOTER_UNSUBSCRIBE`
constant and its entry in `email_sender.py`'s `replacements` dict both removed.

---

#### FIX-003 — `UnboundLocalError: ScraperEngine` on Preview PATH B

**Affects:** `app/fastapi/api/v1/products.py`

**Symptom:**
```
[ERROR] Unexpected error — url=https://www.amazon.in/dp/B0FK22FSZ4
error=cannot access local variable 'ScraperEngine' where it is not associated with a value
POST /v1/products/preview HTTP/1.1" 500 Internal Server Error
```
Every PATH B preview (new product, DB miss) crashed with a 500.

**Root cause:** Python's scoping rule — when a name is **assigned anywhere inside
a function** (including via `import`), Python treats it as a **local variable
throughout the entire function**, even on lines before the assignment.

`ScraperEngine` is imported at module level (line 24). During v3.1, two
local `from app.scraper_v2.engine import ScraperEngine` imports were added inside
function bodies:
- Line 127 — inside `_background_scrape_and_store()`, inside an `if` block
- Line 576 — inside `preview_product()`, inside the `else` branch of the PATH B
  existing-product update block

The one at line 576 made Python treat `ScraperEngine` as a local for the entire
`preview_product()` function. Line 330 (`with ScraperEngine() as engine:`) runs
before the `else` branch — at that point the local variable has never been
assigned, so Python raises `UnboundLocalError`.

`_background_scrape_and_store()` had the same latent bug at line 127 but did not
crash yet because no code in that function uses `ScraperEngine` before the local
import line executes.

**Fix:** Removed both redundant local imports. The module-level import at line 24
is sufficient — `ScraperEngine` is available everywhere in the file without any
local re-import.

**Confirmed:** PATH B preview working for Amazon URL `B0FK22FSZ4` after fix.

---

### Deviations from Design

#### DEV-001 — `get_subject()` No Longer Called by `email_sender.py`

- **Affects:** `app/notifications/content/price_drop.py`, `app/notifications/email_sender.py`
- **Original design:** `email_sender.py` calls `get_subject(product_name, new_price_fmt)`
  from `price_drop.py` to build the subject line.
- **Actual:** Subject built inline in `send_price_drop()`. `get_subject()` updated
  to match the new wording and its unused `new_price_fmt` parameter removed, but
  the function is no longer called by `email_sender.py`.
- **Reason:** Subject is now a single f-string — routing through a helper added
  no value. `get_subject()` retained in `price_drop.py` as a content-layer
  reference in case other callers are added in future.

---

### Files Modified

| File | Change |
|---|---|
| `app/notifications/email_sender.py` | FIX-001: subject built inline; `List-Unsubscribe` header added to both methods via `Header` object; `get_subject`, `get_preheader`, `FOOTER_UNSUBSCRIBE` imports removed; `Header` added to sendgrid imports; confirmation plain text header softened |
| `app/notifications/content/price_drop.py` | FIX-001: `get_subject()` updated to new wording, unused `new_price_fmt` param removed; `from decimal import Decimal` unused import removed; `"myntra"` added to `PLATFORM_LABEL` and `PLATFORM_ICON` |
| `app/notifications/templates/price_drop.txt` | FIX-001: header `"PRICE DROP ALERT"` → `"PRICE ALERT"`; opening line reworded |
| `app/notifications/templates/price_drop.html` | FIX-001: Block 1 tagline `"Price Drop Alert"` → `"Price Alert"`; FIX-002: footer broken sentence replaced with single clean sentence; `{{footer_unsubscribe}}` placeholder removed |
| `app/fastapi/api/v1/products.py` | FIX-003: two redundant local `from app.scraper_v2.engine import ScraperEngine` imports removed from `_background_scrape_and_store()` and `preview_product()` |

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Orphaned products (zero subscribers) still scraped every cron run — wastes ScraperAPI credits | `app/repositories/product_repo.py` — `get_all_for_scraping()` | Next phase |
| DEF-002 | `--reload` flag in local uvicorn wipes in-memory `PreviewCache` on file save | `app/services/preview_cache.py` | Replace with Redis |
| DEF-003 | `social_share` query param not stripped from Amazon canonical URLs | `app/services/url_validator.py` | Next phase |
| DEF-004 | UTM params not stripped from Myntra URLs | `app/services/url_validator.py` | Next phase |
| DEF-005 | Amazon PA-API stub — `AmazonAffiliateClient` excluded until credentials configured | `app/scraper_v2/affiliate/amazon.py` | When PA-API access received |
| DEF-006 | Amazon specs table selector misses some product types | `app/scraper_v2/scrapers/generic_scraper.py` | Future phase |
| DEF-007 | Myntra JS state extraction not working for all products | `app/scraper_v2/scrapers/generic_scraper.py` | Future phase |
| DEF-008 | `product_metadata` not shown in price drop email | `app/notifications/email_sender.py` | Future phase |
| DEF-009 | `mrp`/`offers` enrichment not shown in price drop email | `app/notifications/email_sender.py` | Carried from v3.0 |
| DEF-010 | Adaptive layer ordering not yet active — needs 2+ months production data | `app/scraper_v2/scrapers/layer_selector.py` | Automatic |
| DEF-011 | Domain authentication (SPF + DKIM + DMARC) not yet configured for `pricewatch.app` — highest-impact remaining spam fix | DNS for `pricewatch.app` | Requires domain DNS access — no code change |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| Domain authentication | **High** | SPF + DKIM + DMARC DNS records for `pricewatch.app` via SendGrid Sender Authentication — no code change, DNS only |
| Strip dirty URL params | High | `social_share` from Amazon, UTM params from Myntra |
| Skip orphaned products in cron | Medium | Filter `get_all_for_scraping()` to products with ≥1 subscriber |
| Notification preferences | Medium | Per-subscription `notify_on_drop`/`notify_on_rise`/pause/threshold controls — full schema design already written |
| All-time low/high badges | Low | Visual badge when current price equals all-time low |
| Activate Amazon PA-API | When credentials arrive | Implement `_authenticate()` and `_fetch()` in `amazon.py` only |
| Show metadata in price drop email | Low | Pass `product_metadata` through `NotificationJob` to email template |
| Redis PreviewCache | Low | Replace in-memory dict — eliminates `--reload` restart issue |
| Myntra JS state extraction hardening | Low | Investigate correct state key for current Myntra app version |

---

*Archive this file to `docs/changelog/v3_2-email-spam-fixes.md` when the next phase begins.*
