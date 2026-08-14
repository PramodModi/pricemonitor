'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import ProductListCard from '@/components/offers/ProductListCard'
import FilterBar from '@/components/shared/FilterBar'
import { useProducts, useAllProductsCount } from '@/hooks/useProducts'
import { useItems } from '@/hooks/useItems'
import { useAppStore } from '@/store/useAppStore'

const VALID_PLATFORMS = new Set(['amazon', 'flipkart', 'myntra'])

function CardSkeleton() {
  return (
    <div className="card animate-pulse overflow-hidden">
      <div className="aspect-square w-full bg-slate-100" />
      <div className="flex flex-col gap-3 p-4">
        <div className="h-3 w-16 rounded bg-slate-100" />
        <div className="space-y-1.5">
          <div className="h-3.5 w-full rounded bg-slate-100" />
          <div className="h-3.5 w-4/5 rounded bg-slate-100" />
        </div>
        <div className="h-6 w-2/5 rounded bg-slate-100" />
        <div className="h-3 w-1/3 rounded bg-slate-100" />
        <div className="mt-auto h-9 w-full rounded-lg bg-slate-100" />
      </div>
    </div>
  )
}

export default function OffersPageClient() {
  const searchParams = useSearchParams()
  const userEmail    = useAppStore((state) => state.userEmail)

  const qPlatform = searchParams.get('platform')
  const [activePlatforms, setActivePlatforms]   = useState(
    VALID_PLATFORMS.has(qPlatform) ? [qPlatform] : []
  )
  const [activeCategories, setActiveCategories] = useState([])

  useItems(userEmail)

  // Offers = only products with current_price < all_time_high (server-filtered)
  const { data, isLoading, isError } = useProducts(
    activePlatforms,
    activeCategories,
    true,  // onlyDropped
  )

  // Total catalogue count for subtitle context ("X deals of Y tracked")
  const { data: catalogueCount } = useAllProductsCount()

  const products  = data?.items ?? []
  const total     = data?.total ?? 0
  const catalogue = catalogueCount ?? 0

  // Derive available categories from loaded dropped products
  const availableCategories = products.length > 0
    ? [...new Set(products.map(p => p.category).filter(Boolean))]
    : null

  function emptyMessage() {
    if (activePlatforms.length > 0 && activeCategories.length > 0)
      return `No price drops in ${activeCategories.join(', ')} on ${activePlatforms.join(' & ')} right now`
    if (activePlatforms.length > 0)
      return `No price drops on ${activePlatforms.join(' & ')} right now`
    if (activeCategories.length > 0)
      return `No price drops in ${activeCategories.join(', ')} right now`
    return 'No price drops right now — check back soon'
  }

  const subtitle = isLoading
    ? 'Finding products below their all-time high…'
    : total > 0
      ? `${total} product${total !== 1 ? 's' : ''} below their all-time high · out of ${catalogue} tracked`
      : catalogue > 0
        ? `Tracking ${catalogue} products · none currently below their peak price`
        : 'Products tracked by the PricePing community'

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold text-slate-900">
          🔥 Today's Price Drops
        </h1>
        <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
      </div>

      <FilterBar
        platforms={activePlatforms}
        onPlatforms={setActivePlatforms}
        categories={activeCategories}
        onCategories={setActiveCategories}
        resultCount={total}
        availableCategories={availableCategories}
      />

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="mb-4 text-5xl">⚠️</p>
          <p className="text-lg font-medium text-slate-700">Couldn't load products</p>
          <p className="mt-1 text-sm text-slate-500">Please try again in a moment.</p>
        </div>
      ) : products.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="mb-4 text-5xl">📭</p>
          <p className="text-lg font-medium text-slate-700">{emptyMessage()}</p>
          <p className="mt-1 text-sm text-slate-500">
            We check prices every 4 hours — deals appear here as soon as we spot them.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {products.map((product) => (
              <ProductListCard key={product.product_id} product={product} />
            ))}
          </div>
          <p className="mt-8 text-center text-xs text-slate-400">
            Prices checked every 4 hours · {total} deal{total !== 1 ? 's' : ''} across {catalogue} tracked products
          </p>
        </>
      )}
    </div>
  )
}
