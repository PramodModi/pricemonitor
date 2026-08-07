import { Suspense } from 'react'
import OffersPageClient from './OffersPageClient'

/**
 * /offers — public product catalogue page.
 *
 * Thin Suspense wrapper required because OffersPageClient uses
 * useSearchParams() (Next.js 15 rule — same pattern as Track page).
 *
 * Phase 1: Client Component.
 * Phase 2: Upgrade to ISR (add `export const revalidate = 1800`) once
 *           GET /v1/products is stable and SEO indexing is needed.
 */
export default function OffersPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <OffersPageClient />
    </Suspense>
  )
}
