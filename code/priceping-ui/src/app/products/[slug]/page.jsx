'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useProduct } from '@/hooks/useProduct'
import { toast } from 'sonner'

// Left column components
import Breadcrumb from '@/components/product/Breadcrumb'
import ProductHero from '@/components/product/ProductHero'
import KeySpecsGrid from '@/components/product/KeySpecsGrid'
import PriceHistoryChart from '@/components/product/PriceHistoryChart'
import OffersSection from '@/components/product/OffersSection'
import ProductDetailTabs from '@/components/product/ProductDetailTabs'

// Right sidebar components
import SidebarPriceBox from '@/components/product/SidebarPriceBox'
import SidebarRecommendation from '@/components/product/SidebarRecommendation'
import SidebarPriceStats from '@/components/product/SidebarPriceStats'
import TargetPriceInput from '@/components/product/TargetPriceInput'

// Mobile bottom bar
import MobileBottomBar from '@/components/product/MobileBottomBar'

/**
 * Product Detail Page — /products/[slug]
 *
 * Phase 1: Client Component. `slug` param = product_id UUID (no slug column yet).
 * Phase 2: Upgrade to ISR with generateMetadata() and products.slug column.
 *
 * Layout: two-column on desktop (left scrollable, right sticky sidebar),
 * single column + sticky bottom bar on mobile.
 */
export default function ProductPage() {
  // In Phase 1, `slug` IS the product_id UUID
  const { slug: productId } = useParams()

  const {
    data: product,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useProduct(productId)

  // ─── Loading skeleton ──────────────────────────────────────────────────
  if (isLoading) {
    return <ProductPageSkeleton />
  }

  // ─── Error / not found ─────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center px-4">
        <div className="text-5xl mb-4">😕</div>
        <h2 className="text-xl font-semibold text-slate-700 mb-2">
          Product not found
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          {error?.message ?? 'This product may have been removed or the URL is incorrect.'}
        </p>
        <Link href="/dashboard" className="btn-primary">
          ← Back to Dashboard
        </Link>
      </div>
    )
  }

  if (!product) return null

  const { product_metadata, price_stats, current_price } = product
  const specs = product_metadata?.specs ?? null
  const features = product_metadata?.features ?? null
  const description = product_metadata?.description ?? null
  const category = product_metadata?.category ?? null
  const brand = product.brand ?? product_metadata?.brand ?? null

  function handleRefresh() {
    refetch().then(({ data }) => {
      if (data) toast.success('Price updated.')
    })
  }

  return (
    <>
      {/* ── Page wrapper ─────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-4 py-4 pb-24 md:pb-6">

        {/* Breadcrumb */}
        <div className="mb-4">
          <Breadcrumb
            productName={product.name}
            category={category}
            brand={brand}
          />
        </div>

        {/* ── Two-column layout ──────────────────────────────────── */}
        <div className="flex flex-col lg:flex-row gap-6 items-start">

          {/* ── LEFT COLUMN (scrollable) ──────────────────────────── */}
          <div className="flex-1 min-w-0 space-y-6">

            {/* ① Hero — image + identity + spec chips */}
            <div className="card p-5">
              <ProductHero product={product} />
            </div>

            {/* On mobile: sidebar boxes appear inline between sections */}
            {/* They are hidden on desktop (desktop sidebar handles them) */}
            <div className="lg:hidden space-y-4">
              <SidebarPriceBox
                product={product}
                onRefresh={handleRefresh}
                isRefreshing={isFetching}
              />
              <SidebarRecommendation
                priceStats={price_stats}
                currentPrice={current_price}
              />
            </div>

            {/* ② Key Specs Grid */}
            {specs && (
              <div className="card p-5">
                <KeySpecsGrid specs={specs} />
              </div>
            )}

            {/* ③ Price History Chart */}
            <PriceHistoryChart
              productId={productId}
              allTimeLow={price_stats?.all_time_low}
            />

            {/* On mobile: price stats + target price appear after chart */}
            <div className="lg:hidden space-y-4">
              <SidebarPriceStats
                priceStats={price_stats}
                currentPrice={current_price}
              />
              <TargetPriceInput currentPrice={current_price} />
            </div>

            {/* ⑤ Bank Offers & Coupons */}
            <OffersSection offers={product.offers} />

            {/* ⑥⑦ Description, Features & Full Specifications — tabbed */}
            <ProductDetailTabs
              description={description}
              features={features}
              specs={specs}
            />
          </div>

          {/* ── RIGHT COLUMN — sticky sidebar (desktop only) ──────── */}
          <aside className="hidden lg:block w-[280px] flex-shrink-0">
            <div
              className="space-y-4"
              style={{ position: 'sticky', top: '80px' }}
            >
              {/* Box 1 — Price, Buy, Track */}
              <SidebarPriceBox
                product={product}
                onRefresh={handleRefresh}
                isRefreshing={isFetching}
              />

              {/* Box 2 — AI Recommendation */}
              <SidebarRecommendation
                priceStats={price_stats}
                currentPrice={current_price}
              />

              {/* Box 3 — Price Stats */}
              <SidebarPriceStats
                priceStats={price_stats}
                currentPrice={current_price}
              />

              {/* Box 4 — Target Price Input */}
              <TargetPriceInput currentPrice={current_price} />
            </div>
          </aside>
        </div>
      </div>

      {/* Mobile sticky bottom bar */}
      <MobileBottomBar product={product} />
    </>
  )
}

// ─── Loading skeleton ────────────────────────────────────────────────────────

function ProductPageSkeleton() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-4 animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="skeleton h-4 w-56 rounded mb-4" />

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left column */}
        <div className="flex-1 space-y-6">
          {/* Hero card */}
          <div className="card p-5">
            <div className="flex gap-5">
              <div className="skeleton w-[200px] h-[200px] rounded-xl flex-shrink-0" />
              <div className="flex-1 space-y-3">
                <div className="skeleton h-4 w-24 rounded-full" />
                <div className="skeleton h-6 w-full rounded" />
                <div className="skeleton h-5 w-3/4 rounded" />
                <div className="skeleton h-4 w-32 rounded" />
                <div className="flex gap-2 mt-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="skeleton h-6 w-16 rounded-full" />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Key specs skeleton */}
          <div className="card p-5">
            <div className="skeleton h-4 w-36 rounded mb-4" />
            <div className="grid grid-cols-2 gap-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="skeleton h-10 rounded" />
              ))}
            </div>
          </div>

          {/* Chart skeleton */}
          <div className="card p-5">
            <div className="skeleton h-[200px] rounded-lg" />
          </div>
        </div>

        {/* Right sidebar skeleton */}
        <div className="hidden lg:block w-[280px] space-y-4">
          <div className="card p-5 space-y-3">
            <div className="skeleton h-8 w-32 rounded" />
            <div className="skeleton h-4 w-24 rounded" />
            <div className="skeleton h-10 w-full rounded-lg" />
            <div className="skeleton h-10 w-full rounded-lg" />
          </div>
          <div className="card p-4">
            <div className="skeleton h-20 w-full rounded" />
          </div>
          <div className="card p-4 space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex justify-between">
                <div className="skeleton h-3.5 w-24 rounded" />
                <div className="skeleton h-3.5 w-20 rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
