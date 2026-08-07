import { Suspense } from 'react'
import TrackPageClient from './TrackPageClient'

/**
 * Track page — Server Component wrapper.
 * useSearchParams() requires Suspense in Next.js 15.
 */
export default function TrackPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-xl pt-10 text-center text-slate-400">Loading…</div>}>
      <TrackPageClient />
    </Suspense>
  )
}
