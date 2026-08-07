'use client'

import { useState, useEffect } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
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
 * UrlInputForm — Step 1 of the Track flow.
 * URL input + Fetch button.
 * Validates on submit (not on change — avoids premature errors).
 *
 * Props:
 *   onSubmit(url)   — called with the validated URL string
 *   isLoading       — shows spinner + disables form
 *   initialUrl      — pre-fills the input (from ?url= query param on landing page)
 */
export default function UrlInputForm({ onSubmit, isLoading, initialUrl = '' }) {
  const [url, setUrl]   = useState(initialUrl)
  const [error, setError] = useState('')

  // Auto-trigger if initialUrl is provided (from landing page hero)
  useEffect(() => {
    if (initialUrl) {
      handleSubmit(new Event('submit'))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = (e) => {
    e?.preventDefault?.()

    // Extract the first URL from the input — handles multiline Myntra share
    // text where the product name appears on the line before the URL.
    const trimmed = extractUrl(url.trim())

    if (!trimmed) {
      setError('Please paste a product URL.')
      return
    }

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

    setError('')
    onSubmit(trimmed)
  }

  return (
    <div className="card p-6 md:p-8">
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold text-slate-900">
          Paste a product URL
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          We'll fetch the product details and show you a preview before you start tracking.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="product-url" className="block text-sm font-medium text-slate-700 mb-1.5">
            Product URL
          </label>
          <input
            id="product-url"
            type="url"
            value={url}
            onChange={(e) => {
              const val = e.target.value
              // If multiline paste (e.g. Myntra share text), extract the URL
              // immediately so the input shows the clean URL, not the raw paste.
              const cleaned = val.includes('\n') ? extractUrl(val) : val
              setUrl(cleaned)
              if (error) setError('')
            }}
            placeholder="https://www.amazon.in/..."
            className="input font-mono text-sm"
            autoFocus
            autoComplete="off"
            disabled={isLoading}
          />
          {error && (
            <p className="mt-2 text-xs text-red-600">{error}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="btn-primary w-full justify-center"
        >
          {isLoading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Fetching product details…
            </>
          ) : (
            <>
              Fetch product details
              <ArrowRight size={16} />
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
