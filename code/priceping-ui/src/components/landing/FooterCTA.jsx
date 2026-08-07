'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { isSupportedPlatformUrl } from '@/lib/utils'

/**
 * FooterCTA — repeats the hero URL input at the very bottom of the landing page.
 * Captures visitors who scrolled the entire page without acting.
 */
export default function FooterCTA() {
  const router = useRouter()
  const [url, setUrl]     = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) { setError('Paste a product URL to get started.'); return }
    try { new URL(trimmed) } catch { setError("That doesn't look like a valid URL."); return }
    if (!isSupportedPlatformUrl(trimmed)) {
      setError('Only Amazon India, Flipkart, and Myntra URLs are supported.')
      return
    }
    setError('')
    router.push(`/track?url=${encodeURIComponent(trimmed)}`)
  }

  return (
    <section className="section bg-primary-50 border-t border-primary-100">
      <div className="container">
        <div className="mx-auto max-w-xl text-center">
          <h2 className="font-display text-display-sm text-slate-900">
            Start monitoring prices — it's free
          </h2>
          <p className="mt-2 text-slate-500">
            Paste any product URL to get started. No account required.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col sm:flex-row gap-3">
            <input
              type="url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError('') }}
              placeholder="Paste product URL…"
              className="hero-input flex-1"
              autoComplete="off"
            />
            <button type="submit" className="btn-accent shrink-0 px-6 py-3.5 font-bold">
              Track price
              <ArrowRight size={16} />
            </button>
          </form>

          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

          <p className="mt-4 text-xs text-slate-400">
            No account required · Free forever · We ping you by email
          </p>
        </div>
      </div>
    </section>
  )
}
