'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { Bell } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { useItems } from '@/hooks/useItems'
import { usePreview } from '@/hooks/usePreview'
import { useSubscribe } from '@/hooks/useSubscribe'
import UrlInputForm from '@/components/track/UrlInputForm'
import PreviewCard from '@/components/track/PreviewCard'
import SuccessScreen from '@/components/track/SuccessScreen'

/**
 * Track page client logic — 3-step flow to add a product to tracking.
 * Phase: 1 | Rendering: Client Component
 *
 * State machine (in Zustand):
 *   "input"      → URL input form
 *   "loading"    → beacon animation (scrape running — takes 10–20s)
 *   "preview"    → PreviewCard (scrape done, user reviews)
 *   "confirming" → PreviewCard with spinner
 *   "success"    → SuccessScreen
 *
 * FIX 1 (infinite loop): initialUrl is read from searchParams ONCE on mount
 * into local state and cleared after the first submit. Prevents UrlInputForm's
 * auto-submit useEffect from re-firing when the component re-mounts after a
 * scrape error.
 *
 * FIX 2 (stale preview on re-visit): resetTrack() is called on mount so
 * navigating back to the landing page and submitting a new URL always starts
 * from a clean state — never shows a previous product's preview.
 *
 * FIX 3 (state race): loading branch driven by trackStep only, not
 * isLoadingPreview.
 */
export default function TrackPageClient() {
  const searchParams = useSearchParams()

  const trackStep     = useAppStore((s) => s.trackStep)
  const previewResult = useAppStore((s) => s.previewResult)
  const userEmail     = useAppStore((s) => s.userEmail)
  const setTrackStep  = useAppStore((s) => s.setTrackStep)
  const resetTrack    = useAppStore((s) => s.resetTrack)

  // Prefetch items on mount so PreviewCard's isAlreadyTracking cache is warm
  // by the time the preview is shown. useItems is a no-op when userEmail is
  // null (the hook's enabled: !!email guard handles this).
  useItems(userEmail)

  // FIX 2: Reset the state machine every time this page mounts.
  // Without this, navigating away and back leaves trackStep='preview' and
  // previewResult pointing to the previous product — the new URL auto-submit
  // fires but the old preview renders first because trackStep is not 'input'.
  useEffect(() => {
    resetTrack()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // FIX 1: Read ?url= param once on mount into local state. Cleared after
  // first submit so UrlInputForm's auto-submit useEffect does not re-fire
  // when the component re-mounts after a scrape error.
  const [initialUrl, setInitialUrl] = useState(searchParams.get('url') ?? '')

  const { mutate: fetchPreview, error: previewError } = usePreview()
  const { mutate: subscribe,    isPending: isConfirming, error: subscribeError } = useSubscribe()

  // Step 1 — input (also shown after a scrape error)
  if (trackStep === 'input') {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        {previewError && (
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            {previewError.message ?? 'Could not fetch product details. Please try again.'}
          </div>
        )}
        <UrlInputForm
          onSubmit={(url) => {
            // Clear initialUrl after the first submission so that if the
            // scrape fails and UrlInputForm re-mounts, its auto-submit
            // useEffect sees an empty string and does not re-trigger.
            setInitialUrl('')
            setTrackStep('loading')
            fetchPreview(url)
          }}
          isLoading={false}
          initialUrl={initialUrl}
        />
      </div>
    )
  }

  // Step 2 — loading (scrape in progress).
  // FIX 3: driven by trackStep ONLY — not isLoadingPreview. TanStack Query's
  // isPending stays true briefly after onError sets trackStep back to 'input',
  // which would cause the wrong branch to render.
  if (trackStep === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center">
        {/* Beacon rings + bell */}
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
        <p className="text-sm text-slate-500 mb-5">
          Checking the live price — this takes around 10–20 seconds…
        </p>

        {/* Bouncing dots */}
        <div className="flex gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
            style={{ animationDelay: '0ms' }} />
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
            style={{ animationDelay: '150ms' }} />
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
            style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    )
  }

  // Step 2 — preview / confirming
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

  // Step 3 — success
  if (trackStep === 'success') {
    const productSlug = previewResult?.live_data?.slug
    const productId   = previewResult?.catalog_data?.product_id
    return (
      <div className="mx-auto max-w-xl">
        <SuccessScreen
          email={userEmail}
          productId={productId}
          productSlug={productSlug}
          onTrackAnother={resetTrack}
        />
      </div>
    )
  }

  return null
}
