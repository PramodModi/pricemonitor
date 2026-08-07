'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import ProductListCard from '@/components/offers/ProductListCard'
import { useProducts } from '@/hooks/useProducts'
import { useItems } from '@/hooks/useItems'
import { useAppStore } from '@/store/useAppStore'

// ── Platform filter tabs ────────────────────────────────────────────────────
const TABS = [
  { label: 'All',      value: null },
  { label: 'Amazon',   value: 'amazon' },
  { label: 'Flipkart', value: 'flipkart' },
  { label: 'Myntra',   value: 'myntra' },
]

const VALID_PLATFORMS = new Set(['amazon', 'flipkart', 'myntra'])

// ── Loading skeleton ────────────────────────────────────────────────────────
function CardSkeleton() {
  return (
    <div className="card animate-pulse overflow-hidden">
      {/* Image placeholder */}
      <div className="aspect-square w-full bg-slate-100" />
      {/* Content placeholders */}
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

// ── Main component ──────────────────────────────────────────────────────────
export default function OffersPageClient() {
  const searchParams = useSearchParams()
  const userEmail    = useAppStore((state) => state.userEmail)

  // Seed active tab from ?platform= query param (e.g. links from Footer)
  const qPlatform = searchParams.get('platform')
  const [activePlatform, setActivePlatform] = useState(
    VALID_PLATFORMS.has(qPlatform) ? qPlatform : null
  )

  // Pre-populate ['items', userEmail] cache so ProductListCard can check
  // tracking state without making per-card API calls.
  useItems(userEmail)

  const { data, isLoading, isError } = useProducts(activePlatform)

  const products = data?.items  ?? []
  const total    = data?.total  ?? 0

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* ── Page header ─────────────────────────────────────────────── */}
        <div className="mb-6">
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Monitored Products
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {total > 0
              ? `${total} product${total !== 1 ? 's' : ''} tracked by the community · sorted by most watched`
              : 'Products tracked by the PricePing community'}
          </p>
        </div>

        {/* ── Platform filter tabs ─────────────────────────────────────── */}
        <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
          {TABS.map((tab) => (
            <button
              key={tab.label}
              onClick={() => setActivePlatform(tab.value)}
              className={`shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition-colors
                ${
                  activePlatform === tab.value
                    ? 'bg-primary-600 text-white'
                    : 'border border-slate-200 bg-white text-slate-600 hover:border-primary-300 hover:text-primary-600'
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Content area ─────────────────────────────────────────────── */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="mb-4 text-5xl">⚠️</p>
            <p className="text-lg font-medium text-slate-700">
              Couldn't load products
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Please try again in a moment.
            </p>
          </div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="mb-4 text-5xl">📭</p>
            <p className="text-lg font-medium text-slate-700">
              {activePlatform
                ? `No ${activePlatform.charAt(0).toUpperCase() + activePlatform.slice(1)} products yet`
                : 'No products yet'}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Be the first to monitor a product.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {products.map((product) => (
              <ProductListCard key={product.product_id} product={product} />
            ))}
          </div>
        )}
    </div>
  )
}
