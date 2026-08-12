'use client'

import { useState, useEffect } from 'react'
import { ArrowRight, Loader2, Link2, Search } from 'lucide-react'
import { isSupportedPlatformUrl } from '@/lib/utils'

/**
 * Extracts the first http/https URL from a string.
 * Handles multiline clipboard text from Myntra's mobile share button,
 * which prepends the product name on a separate line before the URL:
 *   "DAMENSCH Men Polo T-shirt\nhttps://www.myntra.com/..."
 * For normal single-URL pastes the input is returned unchanged.
 */
function extractUrl(text) {
  const match = text.match(/https?:\/\/[^\s]+/)
  return match ? match[0] : text.trim()
}

/**
 * Detect whether the input looks like a URL.
 * Returns true for http/https strings — these go to the scrape flow.
 * Returns false for plain text — these go to the search flow.
 */
function looksLikeUrl(text) {
  const t = text.trim()
  return t.startsWith('http://') || t.startsWith('https://')
}

/**
 * Validate that a URL contains a recognisable product identifier.
 * Returns an error string or null if valid.
 * This is a fast frontend check — the backend does authoritative validation.
 *
 * Amazon:   /dp/XXXXXXXXXX  — 10 alphanumeric chars
 * Flipkart: ?pid=XXXXXXXXXX — 16 alphanumeric chars, OR /p/itm{...} path
 * Myntra:   /{id}/buy       — numeric product ID
 */
function validateProductUrl(url) {
  try {
    const parsed = new URL(url)
    const hostname = parsed.hostname

    // ── Short / mobile shared URLs — skip validation, backend resolves ────────
    // These are redirect URLs without predictable product ID patterns.
    if (
      hostname.includes('amzn.in') ||          // Amazon short URL (amzn.in/d/...)
      hostname.includes('dl.flipkart.com') ||   // Flipkart Firebase / deep link
      hostname.includes('onelink.me')           // Myntra shared link
    ) return null

    // ── Amazon India ──────────────────────────────────────────────────────────
    if (hostname.includes('amazon.in')) {
      const asinMatch = parsed.pathname.match(/\/dp\/([A-Z0-9]{10})/i)
      if (!asinMatch) {
        return "That doesn't look like a product page. Copy the URL from the product's page directly."
      }
      return null
    }

    // ── Flipkart ──────────────────────────────────────────────────────────────
    if (hostname.includes('flipkart.com')) {
      const hasPid = parsed.searchParams.get('pid')
      const hasPath = /\/p\/itm[a-z0-9]+/i.test(parsed.pathname)
      if (!hasPid && !hasPath) {
        return "That doesn't look like a Flipkart product page. Open the product and copy its URL."
      }
      return null
    }

    // ── Myntra ────────────────────────────────────────────────────────────────
    if (hostname.includes('myntra.com')) {
      // Mobile share URLs: myntra.com/mailers/... — no numeric ID, backend handles
      if (parsed.pathname.startsWith('/mailers/')) return null
      const hasProductId = /\/\d+\/buy/.test(parsed.pathname)
      if (!hasProductId) {
        return "That doesn't look like a Myntra product page. Open the product and copy its URL."
      }
      return null
    }

  } catch {
    // URL parse error handled elsewhere
  }
  return null
}


/**
 *
 * Dual-mode input:
 *   URL input  → calls onSubmitUrl(url)   → existing scrape → preview flow
 *   Name input → calls onSubmitSearch(q)  → GET /v1/search → results list
 *
 * Auto-detects on submit — user doesn't need to choose a mode.
 * Validates URL platform only when input is a URL.
 *
 * Props:
 *   onSubmitUrl(url)             — called with validated URL → scrape flow
 *   onSubmitSearch(q, platform)  — called with query + platform → search results flow
 *                                  platform: 'all' | 'amazon' | 'flipkart' | 'myntra'
 *   isLoading                    — shows spinner + disables form (URL scrape in progress)
 *   isSearching                  — shows spinner + disables form (search in progress)
 *   initialUrl                   — pre-fills the input (from ?url= query param on landing page)
 */

const PLATFORMS = [
  { value: 'all',      label: 'All' },
  { value: 'amazon',   label: 'Amazon India' },
  { value: 'flipkart', label: 'Flipkart' },
  { value: 'myntra',   label: 'Myntra' },
]

export default function UrlInputForm({
  onSubmitUrl,
  onSubmitSearch,
  isLoading = false,
  isSearching = false,
  initialUrl = '',
  initialQuery = '',
}) {
  const [value, setValue] = useState(initialUrl || initialQuery)
  const [error, setError] = useState('')
  const [selectedPlatform, setSelectedPlatform] = useState('all')

  const isBusy = isLoading || isSearching

  // Auto-trigger on mount when pre-filled from landing page (?url= or ?q=)
  useEffect(() => {
    if (initialUrl || initialQuery) {
      handleSubmit(new Event('submit'))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = (e) => {
    e?.preventDefault?.()

    const raw = value.trim()

    if (!raw) {
      setError('Please paste a product URL or type a product name.')
      return
    }

    setError('')

    // ── URL path ──────────────────────────────────────────────────────────────
    if (looksLikeUrl(raw)) {
      // Extract the first URL — handles multiline Myntra share text
      const trimmed = extractUrl(raw)

      // Basic URL format check
      try {
        new URL(trimmed)
      } catch {
        setError("That doesn't look like a valid URL. Try copying it directly from the browser address bar.")
        return
      }

      // Platform check — soft warning, backend does authoritative validation
      if (!isSupportedPlatformUrl(trimmed)) {
        setError('Only Amazon India, Flipkart, and Myntra URLs are supported.')
        return
      }

      // Product ID format check — fast-fail before hitting the scraper
      const productIdError = validateProductUrl(trimmed)
      if (productIdError) {
        setError(productIdError)
        return
      }

      onSubmitUrl(trimmed)
      return
    }

    // ── Search path ───────────────────────────────────────────────────────────
    if (raw.length < 2) {
      setError('Please enter at least 2 characters to search.')
      return
    }

    onSubmitSearch(raw, selectedPlatform)
  }

  // Determine which mode the input is currently in (for UI hints)
  const isUrlMode = looksLikeUrl(value)

  return (
    <div className="card p-6 md:p-8">
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold text-slate-900">
          Track a product
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Paste a product URL <span className="text-slate-400">or</span> type a product name to search.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="product-input" className="block text-sm font-medium text-slate-700 mb-1.5">
            Product URL or name
          </label>

          {/* Input with mode indicator icon */}
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center">
              {isUrlMode
                ? <Link2 size={15} className="text-indigo-400" />
                : <Search size={15} className="text-slate-400" />
              }
            </div>
            <input
              id="product-input"
              type="text"
              value={value}
              onChange={(e) => {
                const val = e.target.value
                // If multiline paste (e.g. Myntra share text), extract the URL
                // immediately so the input shows the clean URL, not the raw paste.
                const cleaned = (!val.startsWith('http') && /https?:\/\//.test(val))
                  ? extractUrl(val)
                  : val
                setValue(cleaned)
                if (error) setError('')
                // Reset platform filter when user switches to URL mode
                if (looksLikeUrl(cleaned)) setSelectedPlatform('all')
              }}
              placeholder="https://www.amazon.in/...  or  Samsung Galaxy S24"
              className="input pl-9 font-mono text-sm"
              autoFocus
              autoComplete="off"
              disabled={isBusy}
            />
          </div>

          {/* Mode hint — only shown when input has content */}
          {value.trim().length > 0 && !error && (
            <p className="mt-1.5 text-xs text-slate-400">
              {isUrlMode
                ? '🔗 URL detected — will fetch live price'
                : '🔍 Searching by name across tracked products'
              }
            </p>
          )}

          {/* Platform filter — only shown in name-search mode */}
          {!isUrlMode && value.trim().length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium text-slate-600 mb-2">Search on:</p>
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {PLATFORMS.map((p) => (
                  <label
                    key={p.value}
                    className={`flex items-center gap-1.5 cursor-pointer text-sm select-none ${
                      isBusy ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  >
                    <input
                      type="radio"
                      name="platform"
                      value={p.value}
                      checked={selectedPlatform === p.value}
                      onChange={() => setSelectedPlatform(p.value)}
                      disabled={isBusy}
                      className="accent-indigo-600"
                    />
                    <span className={selectedPlatform === p.value ? 'text-indigo-700 font-medium' : 'text-slate-600'}>
                      {p.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {error && (
            <p className="mt-2 text-xs text-red-600">{error}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isBusy}
          className="btn-primary w-full justify-center"
        >
          {isLoading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Fetching product details…
            </>
          ) : isSearching ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Searching…
            </>
          ) : isUrlMode ? (
            <>
              Fetch product details
              <ArrowRight size={16} />
            </>
          ) : (
            <>
              <Search size={16} />
              Search products
            </>
          )}
        </button>
      </form>

      {/* Supported platforms */}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-400">Works with:</span>
        <span className="badge-amazon">🛒 Amazon India</span>
        <span className="badge-flipkart">🛍️ Flipkart</span>
        <span className="badge-myntra">👗 Myntra</span>
      </div>
    </div>
  )
}
