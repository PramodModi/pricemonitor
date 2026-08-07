'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { isSupportedPlatformUrl } from '@/lib/utils'

/**
 * Extracts the first http/https URL from a string.
 * Handles multiline or space-separated clipboard text from Myntra's mobile
 * share button, which prepends the product name before the URL:
 *   "DAMENSCH Men Polo T-shirt https://www.myntra.com/..."
 * For normal URL-only pastes the input is returned unchanged.
 */
function extractUrl(text) {
  const match = text.match(/https?:\/\/[^\s]+/)
  return match ? match[0] : text.trim()
}

/**
 * HeroSection — the signature element of the landing page.
 * The URL input box IS the hero. No carousel, no banner.
 *
 * Submitting navigates to /track?url={encodedUrl}
 * The Track page reads ?url= and pre-fills + auto-triggers the scrape.
 */
export default function HeroSection() {
  const router = useRouter()
  const [url, setUrl]   = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()

    // Extract the first URL from the input — handles Myntra share text where
    // the product name appears before the URL on the same (or next) line.
    const trimmed = extractUrl(url.trim())

    if (!trimmed) {
      setError('Paste a product URL to get started.')
      return
    }

    try { new URL(trimmed) }
    catch {
      setError("That doesn't look like a valid URL.")
      return
    }

    if (!isSupportedPlatformUrl(trimmed)) {
      setError('Only Amazon India, Flipkart, and Myntra URLs are supported.')
      return
    }

    setError('')
    router.push(`/track?url=${encodeURIComponent(trimmed)}`)
  }

  return (
    <section className="section bg-white">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">

          {/* Tag pill */}
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary-100
                           bg-primary-50 px-4 py-1.5 text-sm font-medium text-primary-700">
            <span>🔔</span> Never miss a price drop
          </div>

          {/* Headline */}
          <h1 className="font-display text-display-xl text-balance text-slate-900">
            Smart price monitoring —{' '}
            <span className="text-primary-600">we ping you</span>{' '}
            when prices drop
          </h1>

          {/* Subheadline */}
          <p className="mt-5 text-lg text-slate-500 text-balance leading-relaxed">
            Paste any product URL from Amazon, Flipkart, or Myntra. We monitor the price
            and ping you the moment it drops — no app, no account required.
          </p>

          {/* ── The signature input box ─────────────────────────── */}
          <form
            onSubmit={handleSubmit}
            className="mt-8 flex flex-col sm:flex-row gap-3"
            noValidate
          >
            <div className="flex-1 relative">
              <input
                type="url"
                value={url}
                onChange={(e) => {
                  const val = e.target.value
                  // If the pasted text contains a URL preceded by other text
                  // (e.g. Myntra share: "Product Name https://..."),
                  // extract the URL immediately so the input shows the clean URL.
                  const cleaned = (!val.startsWith('http') && /https?:\/\//.test(val))
                    ? extractUrl(val)
                    : val
                  setUrl(cleaned)
                  setError('')
                }}
                placeholder="Paste Amazon, Flipkart, or Myntra URL…"
                className="hero-input w-full"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <button
              type="submit"
              className="btn-accent shrink-0 px-8 py-4 text-base font-bold"
            >
              Track price
              <ArrowRight size={18} />
            </button>
          </form>

          {/* Error */}
          {error && (
            <p className="mt-2 text-sm text-red-600">{error}</p>
          )}

          {/* Trust chips */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <TrustChip>✅ Free forever</TrustChip>
            <TrustChip>✅ No app required</TrustChip>
            <TrustChip>✅ We ping you by email</TrustChip>
          </div>
        </div>
      </div>
    </section>
  )
}

function TrustChip({ children }) {
  return (
    <span className="rounded-full bg-slate-50 border border-slate-200 px-3 py-1
                     text-sm font-medium text-slate-600">
      {children}
    </span>
  )
}
