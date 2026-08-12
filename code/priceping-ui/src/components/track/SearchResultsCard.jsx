'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { formatPrice, formatTimeAgo, getPlatformLabel } from '@/lib/utils'
import { Package, Loader2 } from 'lucide-react'
import api from '@/lib/api'

// UUID v4 format check — Flipkart PIDs (e.g. "WMNGPYWTEFA3VFHF") are not UUIDs
const isDbUuid = (id) => 
  typeof id === 'string' && 
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)

const LIVE_PLATFORMS = [
  { value: 'amazon',   label: '🛒 Amazon India' },
  { value: 'flipkart', label: '🛍️ Flipkart' },
  { value: 'myntra',   label: '👗 Myntra' },
]

/**
 * PlatformBadge — small coloured badge for a portal name.
 */
function PlatformBadge({ platform }) {
  const cls = {
    amazon:   'badge-amazon',
    flipkart: 'badge-flipkart',
    myntra:   'badge-myntra',
  }[platform] ?? 'badge-amazon'
  return <span className={cls}>{getPlatformLabel(platform)}</span>
}

/**
 * ListingCard — one horizontal card per listing (flattened from canonical).
 *
 * Two modes:
 *   DB listing  (_is_tavily falsy)  → direct subscribe via POST /v1/subscriptions/direct
 *   Tavily listing (_is_tavily true) → pass URL to preview flow (product not in DB yet)
 */
function ListingCard({ listing, product, onSelectUrl }) {
  const queryClient = useQueryClient()
  const userEmail   = useAppStore((s) => s.userEmail)
  const setEmail    = useAppStore((s) => s.setUserEmail)

  const [isSubscribing, setIsSubscribing]     = useState(false)
  const [showEmailPrompt, setShowEmailPrompt] = useState(false)
  const [emailInput, setEmailInput]           = useState('')
  const [emailError, setEmailError]           = useState('')
  const [toastMsg, setToastMsg]               = useState('')

  const cachedItems = queryClient.getQueryData(['items', userEmail])
  const isTracking  =
    !listing._is_tavily &&
    !!userEmail &&
    (cachedItems?.items?.some(
      (item) => item.product.product_id === listing.product_id,
    ) ?? false)

  const showToast = (msg) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 3000)
  }

  const doSubscribe = async (email) => {
    setIsSubscribing(true)
    try {
      await api.post('/v1/subscriptions/direct', {
        product_id: listing.product_id,
        email,
      })
      if (!userEmail) setEmail(email)
      await queryClient.invalidateQueries({ queryKey: ['items', email] })
      showToast("You're now monitoring this product 🔔")
      setShowEmailPrompt(false)
    } catch (err) {
      const msg =
        err?.response?.data?.detail?.message ||
        'Something went wrong. Please try again.'
      showToast(msg)
    } finally {
      setIsSubscribing(false)
    }
  }

  const handleMonitorClick = () => {
    // Route to preview flow when: Tavily result, no product_id, or non-UUID product_id
    // Flipkart affiliate PIDs (e.g. "WMNGPYWTEFA3VFHF") are not DB UUIDs
    if (listing._is_tavily || !isDbUuid(listing.product_id)) {
      onSelectUrl?.(listing.url)
      return
    }
    if (isTracking || isSubscribing) return
    if (userEmail) {
      doSubscribe(userEmail)
    } else {
      setShowEmailPrompt(true)
    }
  }

  return (
    <div className="card p-4">
      {/* Toast */}
      {toastMsg && (
        <div className="mb-3 rounded-lg bg-slate-800 px-3 py-2 text-center text-xs font-medium text-white">
          {toastMsg}
        </div>
      )}

      {/* Vertical layout: image top, info middle, button bottom */}

      {/* Platform badge */}
      <div className="mb-2">
        <PlatformBadge platform={listing.platform} />
      </div>

      {/* Product image */}
      <div className="w-full aspect-square rounded-lg border border-slate-100 bg-slate-50 overflow-hidden flex items-center justify-center mb-3">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name ?? 'Product'}
            className="w-full h-full object-contain p-2"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        ) : (
          <Package size={32} className="text-slate-300" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 mb-3">
        <p className="text-sm font-medium text-slate-900 leading-snug line-clamp-2 mb-1">
          {product.name ?? 'Unknown Product'}
        </p>

        {/* Price */}
        <div className="flex items-baseline gap-1.5 flex-wrap">
          {listing.current_price != null ? (
            <span className="text-lg font-bold text-slate-900">
              {formatPrice(listing.current_price)}
            </span>
          ) : null}
          {listing.mrp != null && listing.mrp > listing.current_price && (
            <span className="text-xs text-slate-400 line-through">
              {formatPrice(listing.mrp)}
            </span>
          )}
        </div>

        {/* Stock + last checked */}
        <div className="mt-1 flex items-center gap-1 text-xs whitespace-nowrap overflow-hidden">
          {listing._is_tavily ? null : (
            <>
              <span className={listing.availability ? 'text-green-600' : 'text-red-500'}>
                {listing.availability ? 'In Stock' : 'Out of Stock'}
              </span>
              {listing.last_checked_at && (
                <span className="text-slate-400 truncate">
                  {' · checked '}{formatTimeAgo(listing.last_checked_at)}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Monitor button — full width at bottom */}
      {!showEmailPrompt && (
        <button
          onClick={handleMonitorClick}
          disabled={isTracking || isSubscribing}
          className={`w-full rounded-lg py-2 text-sm font-medium transition-colors
            ${
              isTracking
                ? 'cursor-default bg-green-50 text-green-700'
                : isSubscribing
                ? 'cursor-wait bg-indigo-100 text-indigo-400'
                : 'btn-primary justify-center'
            }`}
        >
          {isTracking
            ? '✅ Monitoring'
            : isSubscribing
            ? 'Adding…'
            : (listing._is_tavily || !isDbUuid(listing.product_id))
            ? '🔍 Get live details'
            : '🔔 Monitor this'}
        </button>
      )}

      {/* Inline email prompt */}
      {showEmailPrompt && (
        <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50 p-3">
          <p className="mb-2 text-xs font-medium text-indigo-800">
            Enter your email to get price drop alerts
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const trimmed = emailInput.trim()
              if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
                setEmailError('Please enter a valid email address.')
                return
              }
              setEmailError('')
              doSubscribe(trimmed)
            }}
            className="flex flex-col gap-1.5"
          >
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-md border border-indigo-200 bg-white px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              autoFocus
            />
            {emailError && (
              <p className="text-[10px] text-red-500">{emailError}</p>
            )}
            <div className="flex gap-1.5">
              <button
                type="submit"
                disabled={isSubscribing}
                className="flex-1 rounded-md bg-indigo-600 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
              >
                {isSubscribing ? 'Adding…' : 'Monitor'}
              </button>
              <button
                type="button"
                onClick={() => { setShowEmailPrompt(false); setEmailError('') }}
                className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-500"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

/**
 * Flatten canonical results into individual listing cards.
 * Each listing becomes its own card carrying the parent product's identity.
 */
function flattenResults(results) {
  const cards = []
  for (const result of results) {
    for (const listing of result.listings) {
      cards.push({ listing, product: result })
    }
  }
  return cards
}

/**
 * SearchResultsCard — full search results panel.
 *
 * Props:
 *   query      — original search query string
 *   results    — array from GET /v1/search response
 *   onBack()   — returns to input form
 *   onSelectUrl(url) — triggers URL preview flow for Tavily/live results
 */
export default function SearchResultsCard({ query, results, onBack, onSelectUrl }) {
  const [liveResults, setLiveResults]           = useState([])
  const [searchingPlatform, setSearchingPlatform] = useState(null)   // which platform is loading
  const [searchedPlatforms, setSearchedPlatforms] = useState(new Set()) // already searched

  const dbCards   = flattenResults(results)
  const liveCards = flattenResults(liveResults)
  const allCards  = [...dbCards, ...liveCards]

  const handleLiveSearch = async (platform) => {
    if (searchingPlatform || searchedPlatforms.has(platform)) return
    setSearchingPlatform(platform)
    try {
      const resp = await api.post('/v1/products/search-by-name', {
        name: query,
        platform,
        limit: 5,
      })
      const candidates = resp.data.candidates ?? []
      const synthetic = candidates
        .filter((c) => c.url)
        .map((c) => ({
          canonical_id: c.url,
          name: c.name,
          brand: c.brand,
          category: null,
          image_url: c.image_url,
          model_number: null,
          best_price: c.current_price,
          best_platform: c.platform,
          listings: [{
            product_id: c.product_id ?? null,
            platform: c.platform,
            current_price: c.current_price,
            mrp: c.mrp,
            url: c.url,
            availability: c.availability,
            last_checked_at: null,
            _is_tavily: !c.current_price,
          }],
        }))
      setLiveResults((prev) => [...prev, ...synthetic])
      setSearchedPlatforms((prev) => new Set([...prev, platform]))
    } catch {
      // silently fail — button stays available to retry
      setSearchedPlatforms((prev) => new Set([...prev, platform]))
    } finally {
      setSearchingPlatform(null)
    }
  }

  return (
    <div className="space-y-4">

      {/* Header */}
      <div>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-lg font-semibold text-slate-900">
              Search results
            </h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {allCards.length > 0
                ? `${allCards.length} listing${allCards.length !== 1 ? 's' : ''} found for "${query}"`
                : `No products found for "${query}"`
              }
            </p>
          </div>
          <button onClick={onBack} className="btn-ghost text-sm py-1.5 px-3 shrink-0">
            ← Back
          </button>
        </div>

        {/* Can't find it — always visible just below header */}
        {dbCards.length > 0 && (
          <button
            onClick={onBack}
            className="mt-3 w-full flex items-center justify-center gap-1.5 rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-2.5 text-sm font-medium text-indigo-600 hover:bg-indigo-100 transition-colors"
          >
            🔍 Not what you wanted? Try with more details
          </button>
        )}
      </div>

      {/* DB Results */}
      {dbCards.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {dbCards.map(({ listing, product }, i) => (
            <ListingCard
              key={listing.product_id ?? listing.url ?? i}
              listing={listing}
              product={product}
              onSelectUrl={onSelectUrl}
            />
          ))}
        </div>
      )}

      {/* Empty DB state */}
      {dbCards.length === 0 && liveCards.length === 0 && !searchingPlatform && (
        <div className="card p-8 text-center">
          <Package size={32} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm font-medium text-slate-700">No matching products in our catalog</p>
          <p className="text-xs text-slate-500 mt-1">
            Search live on a store below to find your product.
          </p>
        </div>
      )}

      {/* Live platform search section */}
      <div className="rounded-xl border-2 border-indigo-100 bg-indigo-50 px-5 py-5">
        <p className="text-base font-semibold text-slate-800 mb-1">
          🏪 Search live on stores
        </p>
        <p className="text-sm text-slate-500 mb-4">
          {dbCards.length > 0
            ? "Don't see your product above? Search directly on a store for fresh results."
            : "Search directly on a store to find your product."
          }
        </p>
        <div className="flex flex-wrap gap-3">
          {LIVE_PLATFORMS.map((p) => {
            const isLoading = searchingPlatform === p.value
            const isDone    = searchedPlatforms.has(p.value)
            return (
              <button
                key={p.value}
                onClick={() => handleLiveSearch(p.value)}
                disabled={!!searchingPlatform || isDone}
                className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium border-2 transition-colors
                  ${isDone
                    ? 'border-green-200 bg-green-50 text-green-700 cursor-default'
                    : isLoading
                    ? 'border-indigo-300 bg-white text-indigo-400 cursor-wait'
                    : 'border-indigo-200 bg-white text-slate-700 hover:border-indigo-400 hover:text-indigo-700 shadow-sm'
                  }`}
              >
                {isLoading
                  ? <Loader2 size={14} className="animate-spin" />
                  : isDone
                  ? '✅'
                  : null
                }
                {isLoading
                  ? `Searching ${p.label.split(' ').slice(1).join(' ')}…`
                  : isDone
                  ? `${p.label} searched`
                  : p.label
                }
              </button>
            )
          })}
        </div>
      </div>

      {/* Live Results — appended below platform section */}
      {liveCards.length > 0 && (
        <>
          <p className="text-xs text-slate-500 font-medium px-1">
            Live results from stores
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {liveCards.map(({ listing, product }, i) => (
              <ListingCard
                key={listing.product_id ?? listing.url ?? i}
                listing={listing}
                product={product}
                onSelectUrl={onSelectUrl}
              />
            ))}
          </div>
        </>
      )}

      {/* Loading indicator */}
      {searchingPlatform && (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin text-indigo-500" />
          Fetching live results…
        </div>
      )}

    </div>
  )
}
