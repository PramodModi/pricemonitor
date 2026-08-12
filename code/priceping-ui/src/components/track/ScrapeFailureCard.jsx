'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { formatPrice, getPlatformLabel } from '@/lib/utils'
import { Package, Loader2, ArrowRight, Search } from 'lucide-react'
import api from '@/lib/api'

const PLATFORMS = ['amazon', 'flipkart', 'myntra']

/**
 * CandidateCard — one product candidate from search-by-name.
 * Shows image, name, platform, and a Monitor button.
 * On click → POST /v1/subscriptions/direct (product already exists in DB
 * after preview) or POST /v1/products/preview (URL scrape flow).
 */
function CandidateCard({ candidate, onSelect }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-slate-100 bg-white hover:border-indigo-200 hover:shadow-sm transition-all cursor-pointer"
      onClick={() => onSelect(candidate)}
    >
      {/* Image */}
      <div className="shrink-0 w-14 h-14 rounded-lg border border-slate-100 bg-slate-50 overflow-hidden flex items-center justify-center">
        {candidate.image_url ? (
          <img
            src={candidate.image_url}
            alt={candidate.name}
            className="w-full h-full object-contain p-1"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        ) : (
          <Package size={22} className="text-slate-300" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 line-clamp-2 leading-snug">
          {candidate.name}
        </p>
        {candidate.current_price != null && (
          <p className="text-sm font-semibold text-indigo-600 mt-0.5">
            {formatPrice(candidate.current_price)}
          </p>
        )}
      </div>

      <ArrowRight size={16} className="shrink-0 text-slate-400" />
    </div>
  )
}

/**
 * ScrapeFailureCard — shown when POST /v1/products/preview fails.
 *
 * Recovery flow:
 *   Step 1 — user types product name + selects platform
 *   Step 2a — DB search (GET /v1/search) — show results with Monitor button
 *   Step 2b — If no DB results → POST /v1/products/search-by-name (Tavily)
 *   Step 3 — User picks a candidate → URL passed to preview flow OR direct subscribe
 *
 * Case B (found on different platform):
 *   Show result with "Found on Flipkart" note + offer to search requested platform
 *
 * Props:
 *   onSelectUrl(url)   — pass URL back to preview flow
 *   onBack()           — return to URL input
 */
export default function ScrapeFailureCard({ onSelectUrl, onBack }) {
  const queryClient = useQueryClient()
  const userEmail   = useAppStore((s) => s.userEmail)
  const setEmail    = useAppStore((s) => s.setUserEmail)
  const scrapedUrl  = useAppStore((s) => s.scrapedUrl)

  const [name, setName]               = useState('')
  const [platform, setPlatform]       = useState('amazon')
  const [isSearching, setIsSearching] = useState(false)
  const [dbResults, setDbResults]     = useState(null)   // null = not searched yet
  const [nameResults, setNameResults] = useState(null)
  const [searchError, setSearchError] = useState('')

  // ── Step 1 submit — DB search first ──────────────────────────────────────
  const handleSearch = async () => {
    const q = name.trim()
    if (q.length < 2) {
      setSearchError('Please enter at least 2 characters.')
      return
    }
    setSearchError('')
    setIsSearching(true)
    setDbResults(null)
    setNameResults(null)

    try {
      // Run DB search and Tavily in parallel — faster than sequential
      const [searchResp, nameResp] = await Promise.all([
        api.get('/v1/search', { params: { q, limit: 20 } }),
        api.post('/v1/products/search-by-name', { name: q, platform, limit: 5 }),
      ])

      const allResults = searchResp.data.results ?? []

      // Brand filter — if query starts with a recognisable brand word (≥2 chars),
      // only show results matching that brand. If brand filter returns nothing,
      // treat as "not in DB" and show Tavily results instead of wrong-brand results.
      // Example: "LG Refrigerator" → filter to brand="LG" → nothing → Tavily
      // Example: "Samsung" → filter to brand starts with "samsung" → Samsung results
      const firstWord = q.split(/\s+/)[0].toLowerCase()
      const hasBrandWord = firstWord.length >= 2
      const brandFiltered = hasBrandWord
        ? allResults.filter(r => r.brand?.toLowerCase().startsWith(firstWord))
        : allResults

      // If brand filter removed all results → skip DB results, use Tavily
      const resultsToUse = (hasBrandWord && brandFiltered.length === 0)
        ? []
        : (brandFiltered.length > 0 ? brandFiltered : allResults)

      const matchingPlatform = resultsToUse.filter(r =>
        r.listings?.some(l => l.platform === platform)
      )
      const otherPlatform = resultsToUse.filter(r =>
        !r.listings?.some(l => l.platform === platform) &&
        r.listings?.length > 0
      )

      if (matchingPlatform.length > 0 || otherPlatform.length > 0) {
        // DB has brand-matching results — show them, ignore Tavily
        setDbResults({ matchingPlatform, otherPlatform })
      } else {
        // DB empty or wrong brand filtered out — show Tavily results
        setNameResults(nameResp.data.candidates ?? [])
      }

    } catch (err) {
      setSearchError('Search failed. Please try again.')
    } finally {
      setIsSearching(false)
    }
  }

  // ── Direct monitor from DB result ─────────────────────────────────────────
  const [subscribing, setSubscribing] = useState(null)   // product_id being subscribed
  const [emailPrompt, setEmailPrompt] = useState(null)   // product_id needing email
  const [emailInput, setEmailInput]   = useState('')
  const [emailError, setEmailError]   = useState('')
  const [toastMsg, setToastMsg]       = useState('')

  const showToast = (msg) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 3000)
  }

  const doDirectSubscribe = async (productId, email) => {
    setSubscribing(productId)
    try {
      await api.post('/v1/subscriptions/direct', { product_id: productId, email })
      if (!userEmail) setEmail(email)
      await queryClient.invalidateQueries({ queryKey: ['items', email] })
      showToast("You're now monitoring this product 🔔")
      setEmailPrompt(null)
    } catch (err) {
      showToast('Something went wrong. Please try again.')
    } finally {
      setSubscribing(null)
    }
  }

  const handleDbListingMonitor = (listing) => {
    if (userEmail) {
      doDirectSubscribe(listing.product_id, userEmail)
    } else {
      setEmailPrompt(listing.product_id)
    }
  }

  const handleEmailSubmit = (e, productId) => {
    e.preventDefault()
    const trimmed = emailInput.trim()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setEmailError('Please enter a valid email address.')
      return
    }
    setEmailError('')
    doDirectSubscribe(productId, trimmed)
  }

  // ── Input form ────────────────────────────────────────────────────────────
  const showForm = dbResults === null && nameResults === null && !isSearching

  return (
    <div className="card p-6 md:p-8 space-y-5">
      {/* Header — only shown on input form, not on results */}
      {showForm && (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-amber-500 text-lg">⚠️</span>
            <h2 className="font-display text-lg font-semibold text-slate-900">
              Couldn't load that product
            </h2>
          </div>
          <p className="text-sm text-slate-500">
            Tell us what you're looking for and we'll find it for you.
          </p>
        </div>
      )}

      {/* Toast */}
      {toastMsg && (
        <div className="rounded-lg bg-slate-800 px-3 py-2 text-center text-xs font-medium text-white">
          {toastMsg}
        </div>
      )}

      {/* Loading state */}
      {isSearching && (
        <div className="flex flex-col items-center justify-center py-10 gap-3">
          <Loader2 size={28} className="animate-spin text-indigo-500" />
          <p className="text-sm text-slate-500">Searching for "{name}"…</p>
        </div>
      )}

      {/* Search form */}
      {showForm && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Product name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setSearchError('') }}
              placeholder="e.g. Samsung Galaxy S24"
              className="input text-sm"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            {searchError && (
              <p className="mt-1.5 text-xs text-red-600">{searchError}</p>
            )}
          </div>

          {/* Platform selector */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Platform
            </label>
            <div className="flex gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPlatform(p)}
                  className={`flex-1 rounded-lg border py-2 text-xs font-medium transition-colors
                    ${platform === p
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                    }`}
                >
                  {getPlatformLabel(p)}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleSearch}
            disabled={isSearching}
            className="btn-primary w-full justify-center"
          >
            {isSearching ? (
              <><Loader2 size={16} className="animate-spin" /> Searching…</>
            ) : (
              <><Search size={16} /> Search products</>
            )}
          </button>

          <button onClick={onBack} className="btn-ghost w-full justify-center text-slate-500 text-sm">
            ← Try a different URL
          </button>
        </div>
      )}

      {/* DB results — Case A: matching platform */}
      {dbResults !== null && (
        <div className="space-y-4">
          {dbResults.matchingPlatform.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">
                Found on {getPlatformLabel(platform)}:
              </p>
              {dbResults.matchingPlatform.map((canonical) => {
                const listing = canonical.listings.find(l => l.platform === platform)
                if (!listing) return null
                const isMonitored = queryClient.getQueryData(['items', userEmail])
                  ?.items?.some(i => i.product.product_id === listing.product_id)

                return (
                  <div key={canonical.canonical_id} className="rounded-xl border border-slate-100 p-3 space-y-2">
                    <div className="flex items-center gap-3">
                      <div className="shrink-0 w-12 h-12 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden">
                        {canonical.image_url
                          ? <img src={canonical.image_url} alt={canonical.name} className="w-full h-full object-contain p-1" onError={(e) => { e.target.style.display = 'none' }} />
                          : <Package size={20} className="text-slate-300" />
                        }
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 line-clamp-2">{canonical.name}</p>
                        {listing.current_price && (
                          <p className="text-sm font-semibold text-indigo-600">{formatPrice(listing.current_price)}</p>
                        )}
                      </div>
                    </div>

                    {/* Email prompt */}
                    {emailPrompt === listing.product_id ? (
                      <form onSubmit={(e) => handleEmailSubmit(e, listing.product_id)} className="space-y-1.5">
                        <input type="email" value={emailInput} onChange={(e) => setEmailInput(e.target.value)}
                          placeholder="you@example.com" autoFocus
                          className="w-full rounded-md border border-indigo-200 bg-white px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                        {emailError && <p className="text-[10px] text-red-500">{emailError}</p>}
                        <div className="flex gap-1.5">
                          <button type="submit" disabled={!!subscribing} className="flex-1 rounded-md bg-indigo-600 py-1.5 text-xs font-semibold text-white disabled:opacity-60">
                            {subscribing === listing.product_id ? 'Adding…' : 'Monitor'}
                          </button>
                          <button type="button" onClick={() => setEmailPrompt(null)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-500">Cancel</button>
                        </div>
                      </form>
                    ) : (
                      <button
                        onClick={() => handleDbListingMonitor(listing)}
                        disabled={isMonitored || !!subscribing}
                        className={`w-full rounded-lg py-1.5 text-xs font-medium transition-colors
                          ${isMonitored ? 'bg-green-50 text-green-700 cursor-default'
                            : subscribing === listing.product_id ? 'bg-indigo-100 text-indigo-400 cursor-wait'
                            : 'btn-primary'}`}
                      >
                        {isMonitored ? '✅ Monitoring' : subscribing === listing.product_id ? 'Adding…' : '🔔 Monitor this'}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Case B — found on different platform */}
          {dbResults.otherPlatform.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-slate-500">
                Not found on {getPlatformLabel(platform)}, but available on:
              </p>
              {dbResults.otherPlatform.slice(0, 3).map((canonical) =>
                canonical.listings.map((listing) => (
                  <div key={listing.product_id} className="rounded-xl border border-amber-100 bg-amber-50 p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Package size={16} className="text-amber-500 shrink-0" />
                      <p className="text-xs text-amber-700 font-medium">
                        Found on {getPlatformLabel(listing.platform)} · last checked {listing.last_checked_at ? new Date(listing.last_checked_at).toLocaleDateString() : '—'}
                      </p>
                    </div>
                    <p className="text-sm font-medium text-slate-800 line-clamp-1">{canonical.name}</p>
                    {listing.current_price && (
                      <p className="text-sm font-semibold text-indigo-600">{formatPrice(listing.current_price)}</p>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDbListingMonitor(listing)}
                        className="flex-1 btn-primary py-1.5 text-xs"
                      >
                        Monitor on {getPlatformLabel(listing.platform)}
                      </button>
                      <button
                        onClick={() => {
                          setDbResults(null)
                          setNameResults(null)
                          // Trigger Tavily search for the requested platform
                          setIsSearching(true)
                          api.post('/v1/products/search-by-name', { name, platform, limit: 5 })
                            .then(({ data }) => setNameResults(data.candidates ?? []))
                            .catch(() => setSearchError('Search failed.'))
                            .finally(() => setIsSearching(false))
                        }}
                        className="flex-1 btn-outline py-1.5 text-xs"
                      >
                        Search {getPlatformLabel(platform)} →
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* No results at all */}
          {dbResults.matchingPlatform.length === 0 && dbResults.otherPlatform.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-2">
              No results found. Try a different search term.
            </p>
          )}

          <button onClick={() => { setDbResults(null); setNameResults(null) }} className="btn-ghost w-full text-sm text-slate-500">
            ← Search again
          </button>
        </div>
      )}

      {/* Tavily results — Case C */}
      {nameResults !== null && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-700">
            {nameResults.length > 0
              ? `Found ${nameResults.length} results on ${getPlatformLabel(platform)}:`
              : `No results found on ${getPlatformLabel(platform)}.`
            }
          </p>

          {nameResults.map((candidate, i) => (
            <CandidateCard
              key={i}
              candidate={candidate}
              onSelect={(c) => onSelectUrl(c.url)}
            />
          ))}

          {nameResults.length === 0 && (
            <p className="text-xs text-slate-400 text-center">
              Try pasting the product URL directly instead.
            </p>
          )}

          <button onClick={() => { setDbResults(null); setNameResults(null) }} className="btn-ghost w-full text-sm text-slate-500">
            ← Search again
          </button>
          <button onClick={onBack} className="btn-ghost w-full text-sm text-slate-500">
            ← Try a different URL
          </button>
        </div>
      )}
    </div>
  )
}
