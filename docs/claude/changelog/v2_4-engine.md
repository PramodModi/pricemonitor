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

## [v2.4] — ScraperEngine Retry Cascade — July 2026

This phase introduces `ScraperEngine` as the single public surface of
`scraper_v2`, decoupling all browser lifecycle management, retry logic,
and failure classification from the caller. `scraper_worker.py` and
`products.py` are reduced to one-line callers. The old v1 path and the
`USE_SCRAPER_V2` rollback flag are preserved unchanged.

---

### Summary of Changes

| Area | Change |
|---|---|
| `engine.py` | **New** — `ScraperEngine`: public entry point for `scraper_v2`, owns browser lifecycle and 5-attempt retry cascade |
| `failure_classifier.py` | **New** — `FailureClassifier`: diagnoses `ScrapeResponse` fields into typed `FailureDiagnosis` with retry mechanism recommendation |
| `scraper_worker.py` | `_process_job_v2()` replaced — now a 3-line caller: `ScraperEngine().scrape(url)` |
| `products.py` | Preview route v2 block replaced — now a 2-line caller: `ScraperEngine().scrape(url)` |
| `scraper_worker.py` | `self._generic = GenericScraper()` removed from `__init__()` — `ScraperEngine` manages its own `GenericScraper` |

---

### Features

#### FEAT-001 — ScraperEngine: Single Public Surface for scraper_v2
- **Affects:** `app/scraper_v2/engine.py` (new file)
- **Change:** `ScraperEngine` is the only class callers import from `scraper_v2`.
  It owns the Playwright instance, browser lifecycle, retry cascade, failure
  classification, and all fallback strategies. Callers pass only a URL.
- **Interface:**
  ```python
  with ScraperEngine() as engine:
      response = engine.scrape(url)   # url is all the caller provides
  ```
- **Benefit:** When `scraper_v3` arrives, or when an affiliate API / LLM
  extraction strategy is added, only `engine.py` changes. No caller is touched.
- **Future:** When `scraper_v2` is extracted as a standalone FastAPI service,
  `engine.scrape(url)` becomes a request handler with zero refactoring.

#### FEAT-002 — 5-Attempt Retry Cascade with Escalating Mechanisms
- **Affects:** `app/scraper_v2/engine.py`
- **Change:** Each failed scrape attempt escalates to a genuinely different
  mechanism rather than retrying the same configuration.

  | Attempt | Mechanism | Purpose |
  |---|---|---|
  | 1 | Chromium + fresh context | Normal path |
  | 2 | Chromium + new context + rotated UA | Transient session / WAF slippage |
  | 3 | Firefox + new process | TLS fingerprint bypass (Myntra fix) |
  | 4 | Google Cache → Bing Cache | Static HTML, zero bot detection (non-Amazon) |
  | 5 | ScraperAPI residential proxy | CAPTCHA + IP block bypass |

- **Cause-aware fast-paths:**
  - `ip_block` or `captcha` → jump directly to ScraperAPI (skip browser attempts)
  - `fingerprint` → jump directly to Firefox
- **Amazon-specific:** Google Cache / Bing Cache skipped for Amazon (`noarchive`
  policy — always returns empty). Amazon goes straight to ScraperAPI at attempt 4.

#### FEAT-003 — FailureClassifier: Structured Failure Diagnosis
- **Affects:** `app/scraper_v2/scrapers/failure_classifier.py` (new file)
- **Change:** Every failed `ScrapeResponse` is diagnosed into a typed
  `FailureDiagnosis` with `cause` (enum), `mechanism` (enum), `confidence`
  (0.0–1.0), and `evidence` (human-readable list). Reads only `ScrapeResponse`
  fields — no live Playwright `Page` access required.
- **Failure causes:**

  | Cause | Signal |
  |---|---|
  | `ip_block` | Myntra + fast nav + ≤1 layer tried |
  | `captcha` | BOT_DETECTED + captcha signal in error_message; or heuristic layer failed (no ₹ on page) |
  | `waf_challenge` | BOT_DETECTED + WAF signal; or Amazon + fast nav + ≤1 layer tried |
  | `fingerprint` | BOT_DETECTED + headless/webdriver/tls signal |
  | `rate_limited` | HTTP 429 / "too many requests" in error_message |
  | `css_stale` | ALL_LAYERS_FAILED + selector failed + heuristic passed (₹ on page, CSS selectors wrong) |
  | `html_structure` | ALL_LAYERS_FAILED + heuristic also failed but ≥2KB body |
  | `timeout` | TIMEOUT error_type or timeout signal in error_message |
  | `unknown` | None of the above |

- **Key insight — heuristic vs selector failure:**
  If `heuristic` is in `layers_failed`, no ₹ symbol was found anywhere on the
  page — the page is a bot-check page, not a real product page. If `heuristic`
  passed but `selector` failed, the page was real but CSS classes rotated
  (Flipkart obfuscated class rotation). These produce different diagnoses and
  different retry mechanisms.

#### FEAT-004 — Progressive Retry Delay
- **Affects:** `app/scraper_v2/engine.py`
- **Change:** A progressive sleep is inserted between retry attempts. Each attempt
  waits `2 × (attempt - 1)` seconds before starting — giving the previous portal
  session time to expire before the next mechanism is tried.

  | Transition | Sleep |
  |---|---|
  | attempt 1 → 2 | 2s |
  | attempt 2 → 3 | 4s |
  | attempt 3 → 4 | 6s |
  | attempt 4 → 5 | 8s (or 0s if GIVE_UP) |
  | rate-limited (any) | 15s flat |

- **Note:** Delay is skipped before `GIVE_UP` — no point waiting before immediately
  breaking out of the cascade.

---

### Fixes

#### FIX-001 — sync_playwright() Inside asyncio Loop Crash
- **Affects:** `app/scraper_v2/engine.py`
- **Symptom:** Attempts 3 (Firefox), 4 (cached page), and 5 (ScraperAPI) all threw
  `"Error: It looks like you are using Playwright Sync API inside the asyncio loop"`
  when called from the FastAPI preview endpoint.
- **Root cause:** FastAPI runs inside an asyncio event loop. Calling `sync_playwright()`
  again inside a running loop is not permitted. Attempts 1 and 2 worked because they
  reused `self._browser` (launched before the request started). Attempts 3, 4, 5
  each called `sync_playwright()` to open a new browser — crashing.
- **Fix:** All attempts reuse `self._pw` (the Playwright instance started once in
  `__init__()`). Firefox, cached page, and ScraperAPI all call `self._pw.firefox.launch()`
  or `self._pw.chromium.launch()` — no second `sync_playwright()` call anywhere.

#### FIX-002 — WAF Misdiagnosed as Cause on Local Machine
- **Affects:** `app/scraper_v2/scrapers/failure_classifier.py`
- **Symptom:** On local machine, Amazon nav completed in ~570ms and all 6 layers
  ran — yet classifier diagnosed `WAF_CHALLENGE` (fast-nav heuristic fired).
- **Root cause:** The fast-nav WAF heuristic used only `nav_ms < 800ms` as its
  signal. Local machines can navigate to Amazon in ~500ms legitimately. The
  threshold was calibrated for Railway (where real pages take 1500ms+), not local.
- **Fix:** Fast-nav heuristic now requires **both** `nav_ms < 800ms` **and**
  `len(layers_tried) <= 1`. If all 6 layers ran, the page loaded — nav speed is
  irrelevant. A WAF challenge page stops extraction after 0–1 layers, not 6.

#### FIX-003 — css_stale Misdiagnosis When Heuristic Also Fails (Railway)
- **Affects:** `app/scraper_v2/scrapers/failure_classifier.py`
- **Symptom:** On Railway, Amazon CAPTCHA pages were diagnosed as `css_stale`
  because `selector` was in `layers_failed`. The cascade used `NEW_CONTEXT`
  (wrong) instead of jumping to ScraperAPI.
- **Root cause:** Classifier checked `selector in layers_failed` first — true even
  on a CAPTCHA page. Did not check whether `heuristic` also failed (which would
  indicate no ₹ on the page at all, confirming it's a bot-check page).
- **Fix:** `heuristic in layers_failed` is now checked first. If heuristic failed,
  cause = `captcha`, mechanism = `scraperapi`. Only when heuristic passed but
  selector failed does cause = `css_stale`.

#### FIX-004 — ScrapeResponse Missing Required `job_id` Argument
- **Affects:** `app/scraper_v2/engine.py`
- **Symptom:** `TypeError: ScrapeResponse.__init__() missing 1 required positional
  argument: 'job_id'` — crashed attempt 4 (cached page fallback).
- **Root cause:** Every `ScrapeResponse` construction in `engine.py` was missing
  `job_id`. `ScrapeResponse` dataclass requires it as a positional argument.
- **Fix:** `job_id = str(uuid.uuid4())` generated once per `scrape()` call and
  threaded through all `ScrapeResponse` constructions and all `scraper.scrape()`
  calls in `engine.py`.

#### FIX-005 — GIVE_UP Mechanism Still Ran Browser Attempt
- **Affects:** `app/scraper_v2/engine.py`
- **Symptom:** When `_pick_mechanism()` returned `GIVE_UP`, the dispatch block
  fell through to `_attempt_browser()` — running a fifth full browser scrape
  that was guaranteed to fail, wasting ~20s.
- **Root cause:** `GIVE_UP` was not handled in the dispatch `if/elif` chain.
- **Fix:** Added `elif mechanism == RetryMechanism.GIVE_UP: break` as the first
  check in the dispatch block. Also skip progressive delay before `GIVE_UP`.

#### FIX-006 — Cached Page Attempt Used for Amazon (Always Fails)
- **Affects:** `app/scraper_v2/engine.py`
- **Symptom:** Attempt 4 on Railway always returned 354-byte and 198-byte bodies
  from Google Cache and Bing Cache respectively for Amazon URLs.
- **Root cause:** Amazon sets `<meta name="robots" content="noarchive">` on all
  product pages. Google and Bing respect this — no cached copies exist for any
  Amazon URL.
- **Fix:** `_pick_mechanism()` now uses a separate cascade for `portal.name == "amazon"`:
  skips `CACHED_PAGE` entirely, goes `NEW_CONTEXT → NEW_CONTEXT → FIREFOX →
  SCRAPERAPI/GIVE_UP → SCRAPERAPI/GIVE_UP`. All other portals (Flipkart, Myntra)
  still attempt cached page at attempt 4.

#### FIX-007 — `error_type.value` Crash in Diagnostic Write
- **Affects:** `app/fastapi/api/v1/products.py`
- **Symptom:** `AttributeError: 'str' object has no attribute 'value'` — logged
  as warning `"Failed to write preview diagnostic"`.
- **Root cause:** `result.error_type` from `engine.py`'s fallback `ScrapeResponse`
  can be a plain string in some code paths (set by `GenericScraper` before the
  `ScrapeFailureReason` enum wrapper). `products.py` called `.value` unconditionally.
- **Fix:** Changed to `result.error_type.value if hasattr(result.error_type, "value") else result.error_type`.

---

### Deviations from Design

#### DEV-001 — scraper_v2 Fully Decoupled from Worker Layer
- **Affects:** `app/scraper_v2/engine.py`, `app/workers/scraper_worker.py`
- **Original (v2.1):** `scraper_worker.py` owned browser lifecycle, context setup,
  Firefox branching, stealth application, and retry loop — calling `GenericScraper`
  as a dependency.
- **Actual:** `scraper_v2` is self-contained. `ScraperEngine` owns everything.
  `scraper_worker.py` is a thin caller. No `app.workers.*` import anywhere in
  `scraper_v2/`.
- **Reason:** Forward compatibility — when `scraper_v2` is extracted as a FastAPI
  microservice, only `engine.py` changes. When `scraper_v3` is introduced, only
  `engine.py` changes. The caller never needs to know which version, engine, or
  strategy is in use.

#### DEV-002 — Browser Lifecycle Owned by Engine, Not Worker
- **Affects:** `app/workers/scraper_worker.py`
- **Original:** `self._browser` (long-lived Chromium) and `self._pw` created in
  `ScraperWorker.__init__()`, used by `_process_job_v2()` directly.
- **Actual:** `ScraperEngine.__init__()` creates its own `self._pw` and
  `self._browser`. `scraper_worker.py` opens a new `ScraperEngine` per job via
  `with ScraperEngine() as engine`. The worker's `self._browser` is only used by
  the v1 path now.
- **Trade-off:** Opens/closes Playwright per job rather than holding a long-lived
  instance. Accepted for correctness and isolation — the retry cascade needs control
  over the browser lifecycle to escalate mechanisms safely.

#### DEV-003 — Firefox Launched Per-Attempt, Not Per-Job
- **Affects:** `app/scraper_v2/engine.py`
- **Original (v2.1):** Firefox browser opened once per job (if portal required it),
  closed after the job.
- **Actual:** Firefox is opened and closed per attempt inside the retry cascade.
  Each Firefox attempt is a fresh process with no shared state from the previous
  attempt.
- **Reason:** Isolation between retry attempts is the point. A fresh Firefox process
  changes all browser-level signals — PID, TLS session, socket pool, memory layout.

---

### Known Deferred Issues

| ID | Issue | File | Deferred to |
|---|---|---|---|
| DEF-001 | Amazon on Railway — Railway datacenter IP range consistently blocked by Amazon at edge. All 5 attempts fail without `SCRAPER_API_KEY`. Preview returns 502 for any Amazon URL on Railway. | `app/scraper_v2/engine.py` | Phase 3 — set `SCRAPER_API_KEY` |
| DEF-002 | Myntra on Railway — same IP block as v2.1 DEF-001. Engine correctly diagnoses `ip_block` and routes to ScraperAPI, but without `SCRAPER_API_KEY` all attempts exhaust. | `app/scraper_v2/engine.py` | Phase 3 — set `SCRAPER_API_KEY` |
| DEF-003 | `ScraperEngine` opens a new Playwright instance per job — long-lived Playwright instance would be more efficient. Acceptable for current scrape volume. | `app/scraper_v2/engine.py` | Phase 3 performance tuning |
| DEF-004 | Amazon PA-API (Layer 6 `affiliate_api`) still a stub — `No module named 'scraper_v2'` import error eliminated (v2.2 FIX-004) but layer returns `None` silently | `app/scraper_v2/scrapers/base.py` | When PA-API access received |
| DEF-005 | Adaptive layer ordering (LayerStatsCache) still using default order — insufficient production diagnostic data | `app/scraper_v2/scrapers/layer_selector.py` | Automatic after 2+ months data |
| DEF-006 | Progressive retry delay (max 20s) + scrape time (~20s each) means a full 5-attempt cascade can take ~2 minutes. Railway has a 30s request timeout on HTTP responses. Preview will 504 if all 5 attempts run. | `app/scraper_v2/engine.py` | Add per-cascade wall-clock timeout guard |
| DEF-007 | `triggered_by` for preview scrapes is always `null` — email not available at preview step | `app/fastapi/api/v1/products.py` | Backfill on confirm step |

---

### Configuration Added

New environment variable required for ScraperAPI fallback:

| Variable | Default | Used by | Description |
|---|---|---|---|
| `SCRAPER_API_KEY` | `""` | `ScraperEngine._attempt_scraperapi()` | ScraperAPI key for residential proxy fallback. Free tier: 1,000 req/month. Without this key, attempt 5 is `GIVE_UP`. Set in Railway environment variables. |

---

### Portal Status on Railway (July 2026)

| Portal | Without `SCRAPER_API_KEY` | With `SCRAPER_API_KEY` | Notes |
|---|---|---|---|
| Amazon | ❌ All 5 attempts fail | ✅ ScraperAPI attempt succeeds | Railway IP range consistently blocked by Amazon |
| Flipkart | ✅ Attempt 1 succeeds | ✅ | Not affected by current Railway IP |
| Myntra | ❌ IP block | ✅ ScraperAPI | Same as Amazon — Railway IP blocked |

---

### Files Added

| File | Purpose |
|---|---|
| `app/scraper_v2/engine.py` | `ScraperEngine` — public surface of `scraper_v2`. Owns browser lifecycle, 5-attempt retry cascade, failure routing. |
| `app/scraper_v2/scrapers/failure_classifier.py` | `FailureClassifier` — diagnoses `ScrapeResponse` into `FailureDiagnosis` with cause, mechanism, confidence, evidence. |

---

### Files Modified

| File | Change |
|---|---|
| `app/workers/scraper_worker.py` | `_process_job_v2()` replaced with 3-line `ScraperEngine` delegation; `self._generic = GenericScraper()` removed from `__init__()` |
| `app/fastapi/api/v1/products.py` | v2 scrape block (70 lines) replaced with 2-line `ScraperEngine` delegation; `GenericScraper`, `get_config` imports removed; `sync_playwright`/`Stealth` moved inside v1 `else` block; `error_type.value` crash fixed |

---

### Next Phase — Phase 3

| Item | Priority | Description |
|---|---|---|
| Set `SCRAPER_API_KEY` | **Immediate** | Unblocks Amazon and Myntra preview on Railway. Free tier (1,000 req/month) sufficient for MVP. |
| Wall-clock timeout guard | High | Add a max cascade duration (e.g. 25s) so preview never 504s on Railway's 30s limit. Break the cascade early and return partial failure rather than timing out. |
| ScraperAPI for scheduled scraper | Medium | GitHub Actions scraper currently uses Railway IP only through the preview path — cron path bypasses IP issues. Monitor if cron path gets blocked as user count grows. |
| LLM extraction layer | Low | Layer 6b via Groq free API — handles pages where all structural layers fail and ScraperAPI is unavailable. |
| Redis PreviewCache | Low | Replace in-memory `PreviewCache` with Redis for multi-instance deployments. |
| Price history chart | Low | Streamlit UI — price trend chart on product detail page. |
| Auth | Low | User login / session management. |

---

*Archive this file to `docs/changelog/v2.4-engine.md` when Phase 3 begins.*
