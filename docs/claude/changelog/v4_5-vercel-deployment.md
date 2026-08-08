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

## [v4.5] — Production Deployment — August 2026

This phase takes PricePing from local development to full production deployment.
The Next.js frontend is deployed to Vercel at `priceping.in`. The FastAPI backend
is restored on Railway (Hobby plan) with a clean custom domain `api.priceping.in`.
DNS is fully configured via Hostinger.

**Scope of this phase:** Railway Hobby plan upgrade, Next.js 16 upgrade (CVE fix),
ESLint build error fixes, Vercel deployment, custom domain configuration
(`priceping.in` → Vercel, `api.priceping.in` → Railway), CORS updates, environment
variable management cleanup.

---

### Summary of Changes

| Area | Change |
|---|---|
| Railway | Upgraded from expired free tier to Hobby plan ($5/month) |
| `code/priceping-ui/package.json` | Next.js upgraded 15.3.5 → 16.3.0 (CVE-2025-66478 fix) |
| `code/priceping-ui/package-lock.json` | Updated after Next.js upgrade |
| `code/priceping-ui/.eslintrc.json` | Removed `@typescript-eslint/no-var-requires` rule; `react/no-unescaped-entities` turned off |
| `code/priceping-ui/next.config.js` | Removed `eslint` key (not supported in Next.js 16) |
| `code/priceping-ui/.gitignore` | Added `.env.production` and `.env.local` — env vars managed in Vercel dashboard |
| `code/priceping-ui/.env.production` | Removed from git tracking (`git rm --cached`) |
| `app/fastapi/main.py` | CORS `allow_origins` updated — added `https://www.priceping.in` and `https://pricemonitor-pi.vercel.app` |
| Vercel | Project created; root directory set to `code/priceping-ui`; framework preset set to Next.js |
| Vercel | `NEXT_PUBLIC_API_URL` set to `https://api.priceping.in` |
| Hostinger DNS | A record `@` → `216.198.79.1` (Vercel); CNAME `www` → `a8671e34d58351c8.vercel-dns-017.com` |
| Hostinger DNS | CNAME `api` → `5df9wqy3.up.railway.app`; TXT `_railway-verify.api` → Railway verification token |
| Railway | Custom domain `api.priceping.in` added and verified |

---

### Operations

#### OPS-001 — Railway Hobby Plan Upgrade
- **Change:** Railway free tier expired. Upgraded to Hobby plan at $5/month minimum
  usage. Includes $5 of monthly usage credits — actual FastAPI service consumption
  estimated at $2–4/month, staying within the credit.
- **Impact:** Backend fully restored. GitHub Actions cron, Streamlit UI, and Next.js
  frontend API calls all operational again.

#### OPS-002 — Vercel Deployment
- **URL:** `https://pricemonitor-pi.vercel.app` (Vercel default), `https://www.priceping.in` (production)
- **Repo:** `github.com/PramodModi/pricemonitor`
- **Root directory:** `code/priceping-ui`
- **Framework:** Next.js (must be set manually — Vercel does not auto-detect when
  Next.js project is not at repo root)
- **Build command:** `npm run build` (default)
- **Auto-deploy:** Enabled — every push to `main` triggers a new deployment

#### OPS-003 — Custom Domain `priceping.in` → Vercel
- **Registrar:** Hostinger (hpanel.hostinger.com)
- **Records added:**
  - A record: `@` → `216.198.79.1`
  - CNAME: `www` → `a8671e34d58351c8.vercel-dns-017.com`
- **Canonical URL:** `www.priceping.in` (Vercel Production domain)
- **Redirect:** `priceping.in` → 308 permanent redirect → `www.priceping.in`
- **Propagation time:** ~30 minutes

#### OPS-004 — Custom Domain `api.priceping.in` → Railway
- **Records added in Hostinger:**
  - CNAME: `api` → `5df9wqy3.up.railway.app`
  - TXT: `_railway-verify.api` → Railway domain verification token
- **Verified by Railway:** Yes — automatic after DNS propagation (~10 minutes)
- **Result:** FastAPI accessible at `https://api.priceping.in/v1/...`

---

### Features

#### FEAT-001 — Clean Backend URL
- **Change:** FastAPI backend now accessible at `https://api.priceping.in` in addition
  to the original Railway URL `https://pricemonitor-production-21cc.up.railway.app`.
- **Benefit:** Frontend environment variable points to `api.priceping.in` — if the
  backend ever migrates off Railway, only a DNS CNAME update is needed. No Vercel
  env var change, no code change.

---

### Fixes

#### FIX-001 — ESLint Unescaped Entities Blocking Vercel Build
- **Files:** `code/priceping-ui/.eslintrc.json`
- **Symptom:** Vercel build failed with `react/no-unescaped-entities` errors across
  8 components: `HowItWorks.jsx`, `DealsPlaceholder.jsx`, `FooterCTA.jsx`,
  `SidebarPriceBox.jsx`, `CatalogContext.jsx`, `PreviewCard.jsx`, `SuccessScreen.jsx`,
  `UrlInputForm.jsx`. All had apostrophes in JSX text (e.g. `We'll`, `you're`).
- **Root cause:** ESLint treats unescaped `'` characters in JSX as errors in production
  builds. Local dev (`npm run dev`) does not enforce this — only `npm run build` does.
- **Fix:** `react/no-unescaped-entities` rule set to `"off"` in `.eslintrc.json`.
  Apostrophes in user-facing copy are intentional — escaping them (`&apos;`) is
  unnecessary when the text is already inside JSX string context.

#### FIX-002 — TypeScript ESLint Rule in JavaScript Project
- **File:** `code/priceping-ui/.eslintrc.json`
- **Symptom:** Build error: `Definition for rule '@typescript-eslint/no-var-requires'
  was not found` in `src/lib/api.js`.
- **Root cause:** `.eslintrc.json` referenced a TypeScript ESLint rule
  (`@typescript-eslint/no-var-requires`) but the TypeScript ESLint plugin is not
  installed — the project uses plain JavaScript, not TypeScript.
- **Fix:** Replaced the entire `.eslintrc.json` with a clean config extending only
  `next/core-web-vitals`, removing the TypeScript rule entirely.

#### FIX-003 — Vercel Blocking Deployment Due to Next.js CVE
- **File:** `code/priceping-ui/package.json`
- **Symptom:** Build succeeded but Vercel refused to deploy:
  `"Vulnerable version of Next.js detected, please update immediately."` for
  CVE-2025-66478 in Next.js 15.3.5.
- **Fix:** Upgraded Next.js to 16.3.0 via `npm install next@latest`. Build passes
  locally with zero errors. Vercel no longer blocks deployment.

#### FIX-004 — `eslint` Key in `next.config.js` Not Supported in Next.js 16
- **File:** `code/priceping-ui/next.config.js`
- **Symptom:** Warning on every `npm run build` and `npm run dev`:
  `Unrecognized key(s) in object: 'eslint'` — Next.js 16 removed support for
  the `eslint.ignoreDuringBuilds` config option.
- **Fix:** Removed the `eslint` block from `next.config.js`. ESLint errors are now
  handled at the `.eslintrc.json` level (FIX-001 and FIX-002), making the
  `ignoreDuringBuilds` bypass unnecessary.

#### FIX-005 — CORS Blocking API Calls from Vercel Domain
- **File:** `app/fastapi/main.py`
- **Symptom:** All API calls from `https://pricemonitor-pi.vercel.app` blocked with:
  `Access to XMLHttpRequest blocked by CORS policy: No 'Access-Control-Allow-Origin'
  header is present.`
- **Root cause:** FastAPI `CORSMiddleware` only allowed `http://localhost:3000` and
  `https://priceping.in`. The Vercel deployment URL was not whitelisted.
- **Fix:** Added `https://pricemonitor-pi.vercel.app` and `https://www.priceping.in`
  to `allow_origins`.

---

### Configuration

#### CFG-001 — Environment Variable Management
- **Pattern established:** `.env` files are never committed to git for the frontend.
  - `.env.local` — local dev only (`NEXT_PUBLIC_API_URL=http://localhost:8001`)
  - `.env.production` — removed from git (`git rm --cached`); managed in Vercel dashboard
  - Both added to `code/priceping-ui/.gitignore`
- **Vercel dashboard** is the single source of truth for production env vars.

#### CFG-002 — Vercel Environment Variables (Production)
| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.priceping.in` |

#### CFG-003 — FastAPI CORS Origins (Final)
```python
allow_origins=[
    "http://localhost:3000",
    "https://priceping.in",
    "https://www.priceping.in",
    "https://pricemonitor-pi.vercel.app",
]
```

#### CFG-004 — Vercel Project Settings
| Setting | Value |
|---|---|
| Repository | `github.com/PramodModi/pricemonitor` |
| Root Directory | `code/priceping-ui` |
| Framework Preset | Next.js (set manually) |
| Node.js Version | 20.x (Vercel default) |
| Auto-deploy branch | `main` |

---

### Deviations from Design

#### DEV-001 — Next.js 15 → 16 (Major Version Upgrade)
- **Original design:** Next.js 15 (as per v4.0)
- **Actual:** Next.js 16.3.0
- **Reason:** Vercel enforces CVE blocking — Next.js 15.3.5 contains CVE-2025-66478
  and Vercel refused to deploy it. `npm install next@latest` resolved to 16.3.0.
- **Impact:** Zero breaking changes observed. All 7 routes build and function
  identically. One config key removed (`eslint` in `next.config.js` — no longer
  supported in Next.js 16).

#### DEV-002 — Framework Preset Not Auto-Detected by Vercel
- **Expected:** Vercel auto-detects Next.js from `package.json`
- **Actual:** Vercel defaulted to "Other" because the Next.js project is not at the
  repo root — it lives at `code/priceping-ui/`. Had to manually set Framework Preset
  to "Next.js" in Vercel project settings.
- **Symptom when wrong:** Build succeeded but deployment failed with
  `No Output Directory named "public" found`.

---

### Known Deferred Issues

| ID | Issue | Deferred to |
|---|---|---|
| DEF-001 | `src/app/login/page.jsx` not yet built | Next session |
| DEF-003 | FastAPI auth endpoints not implemented: `auth/check`, `auth/login`, `auth/set-password`, `auth/send-otp` | Before auth features go live |
| DEF-004 | `users.password_hash` Alembic migration not run | Before Profile page goes live |
| DEF-007 | Product page URL uses `product_id` UUID — no slug column yet | Phase 2 |
| DEF-008 | No rate limiting on preview endpoint | Phase 2 |
| DEF-010 | `TargetPriceInput` saves locally only — `PATCH /v1/subscriptions/{id}` not built | When auth endpoints implemented |
| DEF-011 | `GET /v1/health` endpoint not implemented — AppShell health check disabled | When endpoint added |
| DEF-012 | Buy recommendation for new products shows generic "insufficient data" message | Next session |
| DEF-013 | `ProductDescription.jsx` and `FullSpecsTable.jsx` are unused — can be deleted | Cleanup |
| DEF-014 | Flipkart `special_price` fix applies to future scrapes only — existing rows not backfilled | Manual re-track or wait for cron |
| DEF-015 | Domain email authentication (SPF, DKIM, DMARC via SendGrid) not configured | DNS-only task, no code changes |

---

### Next Phase Candidates

| Item | Priority | Description |
|---|---|---|
| **Buy recommendation improvements** | High | New product / insufficient data messaging; stable-N-days; dropped-N-times signals. Needs `recommendation.js` + `SidebarRecommendation.jsx` |
| **Login page** | High | `src/app/login/page.jsx` — email gate + optional password, JWT handling |
| **FastAPI auth endpoints** | High | `GET /v1/auth/check`, `POST /v1/auth/login`, `POST /v1/auth/set-password`, `POST /v1/auth/send-otp` |
| **`GET /v1/health`** | Medium | Re-enables AppShell health check banner |
| **`PATCH /v1/subscriptions/{id}`** | Medium | `target_price` persistence — unlocks `TargetPriceInput` |
| **`users.password_hash` migration** | Medium | Alembic migration for Profile page password feature |
| **Products slug column** | Low | Phase 2 — slug backfill + `GET /v1/products/by-slug/{slug}` |
| **Domain email auth** | Low | SPF + DKIM + DMARC via SendGrid Sender Authentication — DNS only |

---

### Production URLs (Final)

| Service | URL |
|---|---|
| Frontend | `https://www.priceping.in` |
| Frontend (redirect) | `https://priceping.in` → 308 → `https://www.priceping.in` |
| Frontend (Vercel default) | `https://pricemonitor-pi.vercel.app` |
| Backend API | `https://api.priceping.in` |
| Backend (Railway default) | `https://pricemonitor-production-21cc.up.railway.app` |
| Database | Supabase (PostgreSQL) |
| Legacy UI | Streamlit Community Cloud |

---

### Files Modified

| File | Change type | Description |
|---|---|---|
| `app/fastapi/main.py` | FIX | CORS origins updated — `www.priceping.in` and Vercel URL added |
| `code/priceping-ui/package.json` | FIX | Next.js upgraded 15.3.5 → 16.3.0 |
| `code/priceping-ui/package-lock.json` | FIX | Updated after Next.js upgrade |
| `code/priceping-ui/.eslintrc.json` | FIX | TypeScript rule removed; `react/no-unescaped-entities` disabled |
| `code/priceping-ui/next.config.js` | FIX | `eslint` key removed (not supported in Next.js 16) |
| `code/priceping-ui/.gitignore` | CFG | `.env.production` and `.env.local` added |
| `code/priceping-ui/.env.production` | CFG | Removed from git tracking (`git rm --cached`) |

---

*Archive this file to `docs/changelog/v4_5-vercel-deployment.md` when the next phase begins.*
