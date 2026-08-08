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

## [v4.6] — Email Deliverability, URL Handling — August 2026

This phase fixes email deliverability (spam, 403 rejections, template redesign),
adds support for Myntra and Flipkart mobile share links, and wires MRP through
the full notification pipeline.

**Scope of this phase:** SendGrid domain authentication, transactional email
redesign, `List-Unsubscribe` header removal, MRP in price drop emails, Myntra
multiline share paste handling, Flipkart `dl.flipkart.com/s/` short URL support
with post-redirect affiliate API retry, `.gitignore` DS_Store cleanup.

---

### Summary of Changes

| Area | Change |
|---|---|
| `app/core/config.py` | From address updated to `pings@priceping.in`; brand name to `PricePing` |
| `app/notifications/email_sender.py` | Complete rewrite — transactional design, MRP, image fix, error logging, 403 fix |
| `app/notifications/templates/price_drop.html` | Complete rewrite — clean transactional layout |
| `app/notifications/templates/price_drop.txt` | Updated to match new design |
| `app/services/url_validator.py` | Flipkart `dl.flipkart.com/s/` short URL accepted and resolved |
| `app/workers/scraper_worker.py` | `mrp` added to `NotificationJob` |
| `app/workers/email_worker.py` | `mrp` passed to `send_price_drop()` |
| `app/scraper_v2/scrapers/generic_scraper.py` | Post-redirect affiliate API retry for Flipkart short URLs |
| `code/priceping-ui/src/components/landing/HeroSection.jsx` | Myntra share paste URL extraction |
| `code/priceping-ui/src/lib/utils.js` | No change needed — already accepted `dl.flipkart.com` |
| `code/priceping-ui/src/components/track/UrlInputForm.jsx` | Myntra share paste URL extraction |
| `.gitignore` | `.DS_Store` and `**/.DS_Store` added; tracked files removed from cache |
| Hostinger DNS | SPF, DKIM (via SendGrid), DMARC records added for `priceping.in` |
| SendGrid | Domain authentication verified; single sender `pings@priceping.in` verified |

---

### Features

#### FEAT-001 — Transactional Email Redesign
- **Files:** `app/notifications/email_sender.py`, `app/notifications/templates/price_drop.html`,
  `app/notifications/templates/price_drop.txt`
- **Change:** Complete rewrite of both price drop and subscription confirmation emails.
  Old design used a dark `#1a1a2e` promotional header with large brand logo,
  36px coloured price block, and badge pills — Gmail classifies this as a newsletter.
  New design is a minimal transactional layout: white background, no header block,
  personal greeting, product card with image + price table, one CTA button, thin
  rule footer.
- **Price drop email structure:**
  - Subject: `Price dropped: {product name} — now ₹18,999` (specific, with truncation + `…`)
  - Greeting: `Hi Pramod,` (first name extracted from email address)
  - Product card: 80px image, product name, MRP/current/previous price table, savings
  - CTA button: `View on Amazon →` / `View on Flipkart →`
  - Footer: dashboard link for unsubscribe (retained as requested)
- **Confirmation email structure:**
  - Subject: `Monitoring started: {product name}`
  - Same transactional style as price drop

#### FEAT-002 — MRP in Price Drop Email
- **Files:** `app/notifications/email_sender.py`, `app/notifications/templates/price_drop.html`,
  `app/notifications/templates/price_drop.txt`, `app/workers/scraper_worker.py`,
  `app/workers/email_worker.py`
- **Change:** MRP (Maximum Retail Price) now flows through the full notification
  pipeline and appears as a crossed-out grey row above "Current price" in the email
  when available and greater than the current price. MRP row is silently omitted
  when not available.
- **Pipeline:** `ScrapeResult.mrp` → `NotificationJob.mrp` → `send_price_drop(mrp=)` →
  `{{mrp_row}}` template placeholder → rendered as `<tr>` with `text-decoration:line-through`.

#### FEAT-003 — Myntra Share Link Paste Handling
- **Files:** `code/priceping-ui/src/components/landing/HeroSection.jsx`,
  `code/priceping-ui/src/components/track/UrlInputForm.jsx`
- **Change:** Myntra's mobile share button copies both the product name and URL to
  clipboard as a single string: `"DAMENSCH Men Polo T-shirt https://www.myntra.com/..."`.
  When pasted into either input, the text is now cleaned immediately on `onChange`
  and again on submit. Detection uses `(!val.startsWith('http') && /https?:\/\//.test(val))`
  which handles both newline-separated and space-separated formats (browser collapses
  `\n` to space in `<input type="url">`).

#### FEAT-004 — Flipkart Short URL Support (`dl.flipkart.com/s/`)
- **Files:** `app/services/url_validator.py`, `app/scraper_v2/scrapers/generic_scraper.py`
- **Change:** Flipkart's mobile share button generates Firebase Dynamic Links
  (`dl.flipkart.com/s/XXXXX`). These were previously rejected by the validator
  (no product ID extractable from `/s/` path). Now accepted and handled in two layers:
  1. **Validator:** `dl.flipkart.com/s/` URLs return immediately with empty
     `marketplace_product_id` — same pattern as `amzn.in` short URLs.
  2. **Browser scraper:** After navigation, Playwright follows the Firebase redirect
     to the real product page. Post-navigation, `page.url` contains the real URL
     with `?pid=TVSHMHKP5GFWZFAZ`. `FlipkartAffiliateClient.extract_product_id(page.url)`
     extracts the `?pid=` query param (not the path-based `itm...` ID which returns
     HTTP 404) and retries the affiliate API to get MRP, special_price, and offers.
- **Why path-based ID fails:** The resolved URL contains two identifiers — `/p/itm65659ce812c21`
  (browser scraper ID) and `?pid=TVSHMHKP5GFWZFAZ` (affiliate API ID). Using the
  path-based ID returns HTTP 404 from the affiliate API. `FlipkartAffiliateClient.extract_product_id()`
  already prioritises `?pid=` over path — using it directly on `page.url` gives the
  correct PID.

---

### Fixes

#### FIX-001 — Email From Address Using Dead Domain
- **File:** `app/core/config.py`
- **Symptom:** Emails sending from `alerts@pricewatch.app` and `Pricemonitor` — a
  domain that is no longer active and was never authenticated with SendGrid.
- **Fix:** Updated four config defaults:
  - `email_from_address`: `alerts@pricewatch.app` → `pings@priceping.in`
  - `email_from_name`: `Pricemonitor` → `PricePing`
  - `email_reply_to`: `no-reply@pricewatch.app` → `support@priceping.in`
  - `dashboard_url`: `https://pricewatch.app/dashboard` → `https://www.priceping.in/dashboard`
- **Note:** Railway Variables and local `.env` must be updated separately — Pydantic
  Settings reads `.env` and environment variables over config defaults. The 403 error
  seen locally was caused by `.env` having `EMAIL_FROM_ADDRESS=pricemonitor26@gmail.com`
  (a test address, not a verified SendGrid sender).

#### FIX-002 — `List-Unsubscribe` Header Causing SendGrid 403
- **File:** `app/notifications/email_sender.py`
- **Symptom:** `SendGrid exception — status=403 body={"errors":[{"message":"The from
  address does not match a verified Sender Identity..."}]}`. Error was misleading —
  the actual cause was the manually-set `List-Unsubscribe` header conflicting with
  SendGrid's internal header handling, not the from address.
- **Root cause:** `message.header = Header("List-Unsubscribe", f"<{settings.dashboard_url}>")` 
  was present in both `send_price_drop()` and `send_subscription_confirmation()`.
  SendGrid's API rejects sends when this header is set manually via the Python library.
  The same curl request without the header succeeds (confirmed via direct API test).
- **Fix:** Removed `Header` import and both `message.header` assignments. `reply_to`
  is retained. The dashboard unsubscribe link remains in the email footer template —
  this is different from the `List-Unsubscribe` HTTP header.

#### FIX-003 — Product Image Not Rendering in Email Clients
- **File:** `app/notifications/email_sender.py`
- **Symptom:** Product image not visible in Gmail mobile and Outlook.
- **Root cause:** Image `<img>` tag used only CSS `width`/`height` and `object-fit:contain`.
  Outlook (Word rendering engine) ignores CSS dimensions on images. Gmail mobile strips
  inline CSS. `object-fit:contain` is not supported in any email client.
- **Fix:** `_build_image_tag()` helper added. Uses `width="80" height="80"` as HTML
  attributes (universally supported) and `style="display:block;border:0;outline:none;"`
  only. `object-fit:contain` removed. Image renders correctly once sender is trusted
  by Gmail (Gmail blocks images from new senders by default — not a code issue).

#### FIX-004 — Email Subject Line Cut Off Without Ellipsis
- **File:** `app/notifications/email_sender.py`
- **Symptom:** Long product names truncated mid-word with no indication in subject line.
- **Fix:** `(product_name[:55] + "…") if len(product_name) > 55 else product_name`
  applied in both price drop and confirmation subjects.

#### FIX-005 — Confirmation Email Logged as Sent Regardless of Outcome
- **File:** `app/notifications/email_sender.py` (improved error logging)
- **Symptom:** `subscriptions.py` logged "Confirmation email sent" even when
  `send_subscription_confirmation()` returned `False` (i.e., 403 from SendGrid).
  Made debugging harder — success and failure looked identical in logs.
- **Fix:** Both exception blocks now capture the full SendGrid response body:
  `body = getattr(exc, "body", None)` and log `status` + `body`, providing the
  exact SendGrid rejection reason instead of only the exception string.

#### FIX-006 — `.DS_Store` Files Tracked by Git
- **File:** `.gitignore`
- **Symptom:** `git status` showed `modified: docs/.DS_Store`, `docs/claude/.DS_Store`,
  and `untracked: .DS_Store` on every macOS checkout.
- **Fix:** Added `.DS_Store` and `**/.DS_Store` to `.gitignore`. Removed already-tracked
  files from git index: `git rm --cached .DS_Store docs/.DS_Store docs/claude/.DS_Store`.

#### FIX-007 — Subscription Confirmation Email Uses Old Branding
- **File:** `app/notifications/email_sender.py`
- **Symptom:** Confirmation email used dark `#1a1a2e` header with `👁️ PRICEMONITOR`
  and `Pricemonitor` brand name — old identity.
- **Fix:** Confirmation email completely rewritten inline to match the new transactional
  style. Brand name updated to `PricePing` throughout.

---

### Configuration

#### CFG-001 — SendGrid Domain Authentication for `priceping.in`
- **Records added in Hostinger DNS:**
  - 3× CNAME records (SendGrid-generated, unique to account) for DKIM signing
  - TXT `@` → `v=spf1 include:sendgrid.net ~all` for SPF
  - TXT `_dmarc` → `v=DMARC1; p=none; rua=mailto:pramod@priceping.in` for DMARC monitoring
- **Verified in SendGrid:** Domain Authentication shows green "Verified" for `priceping.in`
- **Effect:** All emails from `pings@priceping.in` are now DKIM-signed and SPF-authorised.
  Domain in from address matches domain in all email body links — eliminates the primary
  spam signal.

#### CFG-002 — SendGrid Single Sender Verification
- **Sender:** `pings@priceping.in` (FROM), `support@priceping.in` (REPLY-TO)
- **Status:** Verified ✅
- **Nickname:** priceping

#### CFG-003 — Railway Variables to Update
The following Railway Variables must match the updated `config.py` defaults:

| Variable | Value |
|---|---|
| `EMAIL_FROM_ADDRESS` | `pings@priceping.in` |
| `EMAIL_FROM_NAME` | `PricePing` |
| `EMAIL_REPLY_TO` | `support@priceping.in` |
| `DASHBOARD_URL` | `https://www.priceping.in/dashboard` |

#### CFG-004 — Local `.env` Variables to Update
Same variables must be updated or removed from local `.env`. Removing them lets
`config.py` defaults take effect. Never commit `.env` to git.

---

### Deviations from Design

#### DEV-001 — Email Template Uses No External CSS File
- **Original design:** `price_drop.css` exists as a reference stylesheet
- **Actual:** CSS file is never loaded by Python (not referenced in `_load_template()`).
  All styles are inline in `price_drop.html`. `price_drop.css` is a documentation
  artefact only. New template omits promotional styles entirely — no classes needed.

#### DEV-002 — Affiliate API Called Inside Browser Scraper for Short URLs
- **Original design:** Affiliate API is attempt 0 in the engine; browser scraper is
  the fallback. They are separate concerns.
- **Actual:** For `dl.flipkart.com/s/` URLs, the affiliate API is also called from
  inside `generic_scraper.py` after navigation (post-redirect retry). This is an
  intentional exception — the affiliate PID is only knowable after the browser follows
  the Firebase redirect. The retry is guarded by a specific condition
  (`"dl.flipkart.com" in url and "/s/" in url and product_id`) so normal URL flows
  are unaffected.

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not implemented | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not run | Before Profile page goes live |
| DEF-007 | Product page URL uses `product_id` UUID — no slug column yet | Phase 2 |
| DEF-008 | No rate limiting on preview endpoint | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not built | When auth implemented |
| DEF-011 | `GET /v1/health` endpoint not implemented — AppShell health check disabled | When endpoint added |
| DEF-012 | Buy recommendation for new products shows generic "insufficient data" message | Next session |
| DEF-013 | `ProductDescription.jsx` and `FullSpecsTable.jsx` unused — can be deleted | Cleanup |
| DEF-014 | Flipkart `special_price` fix applies to future scrapes only — not backfilled | Manual re-track or wait for cron |
| DEF-016 | Flipkart short URL `_resolve_short_url()` in `url_validator.py` uses urllib HTTP redirect — Firebase Dynamic Links use JS redirect so resolution falls back to original URL. Short URLs still work via browser but `canonical_url` stored in DB is the short URL not the real URL. | When slug column added |
| DEF-017 | DMARC policy is `p=none` (monitoring only) — upgrade to `p=quarantine` after confirming clean delivery for 1–2 weeks | DNS-only change |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **Buy recommendation improvements** | High | New product / insufficient data messaging. Needs `recommendation.js` + `SidebarRecommendation.jsx` |
| **`GET /v1/health`** | Medium | Re-enables AppShell health check banner |
| **`PATCH /v1/subscriptions/{id}`** | Medium | `target_price` persistence — unlocks `TargetPriceInput` |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **DMARC tighten** | Low | Change `p=none` → `p=quarantine; pct=25` after 1–2 weeks of clean delivery |
| **Products slug column** | Low | Phase 2 — slug backfill + `GET /v1/products/by-slug/{slug}` |

---

### Files Modified

| File | Change type | Description |
|---|---|---|
| `app/core/config.py` | FIX | From address, brand name, reply-to, dashboard URL updated to `priceping.in` |
| `app/notifications/email_sender.py` | FEAT/FIX | Full rewrite — transactional design, MRP support, image fix, 403 fix, error logging |
| `app/notifications/templates/price_drop.html` | FEAT | Complete rewrite — transactional layout, `{{greeting}}`, `{{mrp_row}}` placeholders |
| `app/notifications/templates/price_drop.txt` | FEAT | Updated to match new design with `{{mrp_row}}` |
| `app/services/url_validator.py` | FEAT | `dl.flipkart.com/s/` short URL accepted; `_resolve_short_url()` helper added |
| `app/workers/scraper_worker.py` | FEAT | `mrp: Optional[Decimal] = None` added to `NotificationJob`; populated from `result.mrp` |
| `app/workers/email_worker.py` | FEAT | `mrp=job.mrp` passed to `send_price_drop()` |
| `app/scraper_v2/scrapers/generic_scraper.py` | FEAT/FIX | Post-redirect affiliate retry for Flipkart short URLs using `?pid=` param |
| `code/priceping-ui/src/components/landing/HeroSection.jsx` | FIX | `extractUrl()` added — handles Myntra share paste in landing page hero |
| `code/priceping-ui/src/components/track/UrlInputForm.jsx` | FIX | `extractUrl()` + robust detection updated — handles Myntra share paste in track page |
| `.gitignore` | FIX | `.DS_Store` and `**/.DS_Store` added |

---

*Archive this file to `docs/changelog/v4_6-email-url-fixes.md` when the next phase begins.*
