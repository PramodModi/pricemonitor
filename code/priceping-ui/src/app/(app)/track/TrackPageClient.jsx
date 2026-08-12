'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { Bell, Search } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { useItems } from '@/hooks/useItems'
import { usePreview } from '@/hooks/usePreview'
import { useSubscribe } from '@/hooks/useSubscribe'
import { useSearch } from '@/hooks/useSearch'
import UrlInputForm from '@/components/track/UrlInputForm'
import PreviewCard from '@/components/track/PreviewCard'
import SuccessScreen from '@/components/track/SuccessScreen'
import SearchResultsCard from '@/components/track/SearchResultsCard'
import ScrapeFailureCard from '@/components/track/ScrapeFailureCard'

/**
 * Track page client logic — flow to add a product to monitoring.
 * Phase: 1 | Rendering: Client Component
 *
 * State machine (in Zustand):
 *   "input"          → UrlInputForm (URL or name)
 *   "loading"        → beacon animation (URL scrape running — 10–20s)
 *   "searching"      → search animation (GET /v1/search running — <1s)
 *   "search_results" → SearchResultsCard (user clicks Monitor this directly)
 *   "preview"        → PreviewCard (URL scrape done, user reviews)
 *   "confirming"     → PreviewCard with spinner
 *   "success"        → SuccessScreen
 *
 * Search flow:
 *   User types name → "searching" → GET /v1/search → "search_results"
 *   ListingRow handles subscription directly (POST /v1/subscriptions/direct)
 *   with the same Monitor this / ✅ Monitoring pattern as the Offers page.
 *   No navigation away from search results needed.
 *
 * URL flow (unchanged):
 *   User pastes URL → "loading" → POST /v1/products/preview → "preview"
 *   → "confirming" → POST /v1/subscriptions → "success"
 */
/**
 * LoadingBeacon — animated beacon shown during URL scrape.
 * Message changes after 15s to reassure user it's still working.
 */
function LoadingBeacon() {
  const [isLong, setIsLong] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setIsLong(true), 15000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <div className="relative mb-8 flex items-center justify-center">
        <span className="absolute h-28 w-28 rounded-full bg-indigo-100 animate-ping opacity-25" />
        <span
          className="absolute h-20 w-20 rounded-full bg-indigo-200 animate-ping opacity-40"
          style={{ animationDelay: '0.4s' }}
        />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-indigo-600 shadow-lg">
          <Bell size={30} className="text-white" />
        </div>
      </div>
      <h2 className="text-xl font-semibold text-slate-800 mb-2">
        Fetching product details
      </h2>
      <p className="text-sm text-slate-500 mb-5 transition-all duration-500">
        {isLong
          ? "Taking longer than expected — almost there, hang tight…"
          : "Checking the live price — this takes around 10–20 seconds…"
        }
      </p>
      <div className="flex gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  )
}

export default function TrackPageClient() {
  const searchParams = useSearchParams()

  const trackStep     = useAppStore((s) => s.trackStep)
  const previewResult = useAppStore((s) => s.previewResult)
  const userEmail     = useAppStore((s) => s.userEmail)
  const setTrackStep  = useAppStore((s) => s.setTrackStep)
  const resetTrack    = useAppStore((s) => s.resetTrack)

  // Search state — local (not in Zustand — doesn't need to survive navigation)
  const [searchQuery, setSearchQuery]   = useState('')
  const [searchResults, setSearchResults] = useState([])

  // Prefetch items on mount so isTracking cache is warm in ListingRow
  useItems(userEmail)

  // FIX 2: Reset state machine every time this page mounts
  useEffect(() => {
    resetTrack()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // FIX 1: Read ?url= param once on mount into local state
  const [initialUrl, setInitialUrl] = useState(searchParams.get('url') ?? '')

  const { mutate: fetchPreview, error: previewError }                    = usePreview()
  const { mutate: subscribe,    isPending: isConfirming, error: subscribeError } = useSubscribe()
  const { mutate: runSearch,    isPending: isSearching,  error: searchError }    = useSearch()

  // ── Step 1 — input ──────────────────────────────────────────────────────────
  if (trackStep === 'input') {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        {previewError && (
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            {previewError.message ?? 'Could not fetch product details. Please try again.'}
          </div>
        )}
        {searchError && (
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            {searchError.message ?? 'Search failed. Please try again.'}
          </div>
        )}
        <UrlInputForm
          onSubmitUrl={(url) => {
            setInitialUrl('')
            setTrackStep('loading')
            fetchPreview(url)
          }}
          onSubmitSearch={(q, platform = 'all') => {
            setSearchQuery(q)
            setTrackStep('searching')
            runSearch(q, {
              onSuccess: async (data) => {
                // Filter DB results by platform when a specific one is selected
                let dbResults = data.results ?? []
                if (platform !== 'all' && dbResults.length > 0) {
                  dbResults = dbResults
                    .map((r) => ({
                      ...r,
                      listings: r.listings.filter((l) => l.platform === platform),
                    }))
                    .filter((r) => r.listings.length > 0)
                }

                if (dbResults.length > 0) {
                  setSearchResults(dbResults)
                  setTrackStep('search_results')
                } else {
                  // DB returned nothing (or filtered to nothing) — fall back to Tavily
                  try {
                    const apiModule = await import('@/lib/api')
                    const api = apiModule.default

                    // Which platforms to query: specific one, or all 3 in parallel
                    const platformsToSearch = platform === 'all'
                      ? ['amazon', 'flipkart', 'myntra']
                      : [platform]

                    const requests = platformsToSearch.map((p) =>
                      api.post('/v1/products/search-by-name', { name: q, platform: p, limit: 5 })
                    )
                    const responses = await Promise.allSettled(requests)

                    // Convert each platform's candidates into synthetic result cards
                    const syntheticResults = []
                    for (const resp of responses) {
                      if (resp.status !== 'fulfilled') continue
                      const candidates = resp.value.data.candidates ?? []
                      for (const c of candidates) {
                        if (!c.url) continue
                        syntheticResults.push({
                          canonical_id: c.url,   // URL as unique key
                          name: c.name,
                          brand: c.brand,
                          category: null,
                          image_url: c.image_url,
                          model_number: null,
                          best_price: c.current_price,
                          best_platform: c.platform,
                          listings: [{
                            product_id: null,
                            platform: c.platform,
                            current_price: c.current_price,
                            mrp: c.mrp,
                            url: c.url,
                            availability: c.availability,
                            last_checked_at: null,
                            _is_tavily: true,
                          }],
                        })
                      }
                    }

                    setSearchResults(syntheticResults)
                  } catch {
                    setSearchResults([])
                  }
                  setTrackStep('search_results')
                }
              },
              onError: () => {
                setTrackStep('input')
              },
            })
          }}
          isLoading={false}
          isSearching={isSearching}
          initialUrl={initialUrl}
        />
      </div>
    )
  }

  // ── Step 2a — loading (URL scrape in progress) ──────────────────────────────
  if (trackStep === 'loading') {
    return <LoadingBeacon />
  }

  // ── Step 2b — searching (GET /v1/search in progress) ───────────────────────
  if (trackStep === 'searching') {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center">
        <div className="relative mb-8 flex items-center justify-center">
          <span className="absolute h-28 w-28 rounded-full bg-slate-100 animate-ping opacity-25" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-slate-700 shadow-lg">
            <Search size={28} className="text-white" />
          </div>
        </div>
        <h2 className="text-xl font-semibold text-slate-800 mb-2">
          Searching products
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          Looking for "{searchQuery}"…
        </p>
        <div className="flex gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    )
  }

  // ── Step 2c — scrape failed — show recovery UI ─────────────────────────────
  if (trackStep === 'scrape_failed') {
    return (
      <div className="mx-auto max-w-xl">
        <ScrapeFailureCard
          onSelectUrl={(url) => {
            setTrackStep('loading')
            fetchPreview(url)
          }}
          onBack={resetTrack}
        />
      </div>
    )
  }

  // ── Step 3a — search results ────────────────────────────────────────────────
  // ListingRow handles subscription directly — no navigation to preview needed.
  if (trackStep === 'search_results') {
    return (
      <div className="mx-auto max-w-5xl">
        <SearchResultsCard
          query={searchQuery}
          results={searchResults}
          onBack={resetTrack}
          onSelectUrl={(url) => {
            setTrackStep('loading')
            fetchPreview(url)
          }}
        />
      </div>
    )
  }

  // ── Step 3b — preview / confirming (URL flow only) ──────────────────────────
  if (trackStep === 'preview' || trackStep === 'confirming') {
    return (
      <div className="mx-auto max-w-xl">
        <PreviewCard
          previewResult={previewResult}
          onConfirm={(email) => { setTrackStep('confirming'); subscribe({ email }) }}
          onBack={resetTrack}
          isConfirming={trackStep === 'confirming' || isConfirming}
          error={subscribeError?.message}
        />
      </div>
    )
  }

  // ── Step 4 — success ────────────────────────────────────────────────────────
  if (trackStep === 'success') {
    const productSlug        = previewResult?.live_data?.slug
    const productId          = previewResult?.catalog_data?.product_id
    const crossPortalListings = previewResult?.cross_portal_listings ?? []
    return (
      <div className="mx-auto max-w-xl">
        <SuccessScreen
          email={userEmail}
          productId={productId}
          productSlug={productSlug}
          crossPortalListings={crossPortalListings}
          onTrackAnother={resetTrack}
        />
      </div>
    )
  }

  return null
}
