'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Users } from 'lucide-react'
import { getPlatformLabel, getPlatformBadgeClass } from '@/lib/utils'

/**
 * ProductHero
 * Left column, section ①.
 * Image gallery (Phase 1: single image) + product identity + spec chips.
 *
 * Props: product object from GET /v1/products/{id}
 */
export default function ProductHero({ product }) {
  const {
    name,
    brand,
    image_url,
    platform,
    availability,
    rating,
    review_count,
    seller,
    watcher_count,
    current_price,
    mrp,
    price_stats,
    product_metadata,
  } = product

  // Phase 1: single image. Phase 2: gallery from product_metadata.images[]
  const extraImages = product_metadata?.images ?? []
  const allImages = [image_url, ...extraImages].filter(Boolean)
  const [activeImg, setActiveImg] = useState(allImages[0] ?? null)

  // Near all-time low badge
  const isNearAllTimeLow =
    price_stats?.all_time_low &&
    current_price <= price_stats.all_time_low * 1.05

  // Quick spec chips — top 6 specs from product_metadata.specs
  const specs = product_metadata?.specs ?? {}
  const specChips = Object.entries(specs).slice(0, 6)

  const hasDiscount = mrp && mrp > current_price
  const discountPct = hasDiscount
    ? Math.round(((mrp - current_price) / mrp) * 100)
    : null

  return (
    <div className="flex flex-col sm:flex-row gap-5">
      {/* Image column */}
      <div className="flex flex-col items-center gap-2 flex-shrink-0">
        {/* Main image */}
        <div className="relative w-[200px] h-[200px] rounded-xl border border-slate-200 bg-slate-50 overflow-hidden flex-shrink-0">
          {activeImg ? (
            <Image
              src={activeImg}
              alt={name}
              fill
              sizes="200px"
              className="object-contain p-3"
              unoptimized
              priority
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-300 text-5xl">
              📦
            </div>
          )}
        </div>

        {/* Thumbnails — only shown if > 1 image */}
        {allImages.length > 1 && (
          <div className="flex gap-2">
            {allImages.slice(0, 4).map((src, i) => (
              <button
                key={i}
                onClick={() => setActiveImg(src)}
                className={`relative w-[56px] h-[56px] rounded-lg border overflow-hidden transition-all ${
                  activeImg === src
                    ? 'border-indigo-500 ring-2 ring-indigo-200'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <Image
                  src={src}
                  alt={`${name} view ${i + 1}`}
                  fill
                  sizes="56px"
                  className="object-contain p-1"
                  unoptimized
                />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Identity column */}
      <div className="flex-1 min-w-0">
        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className={`badge-platform ${getPlatformBadgeClass(platform)}`}>
            {getPlatformLabel(platform)}
          </span>
          {availability ? (
            <span className="badge-in-stock">In Stock</span>
          ) : (
            <span className="badge-out-of-stock">Out of Stock</span>
          )}
          {isNearAllTimeLow && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-100 text-green-800 border border-green-200">
              🏷️ Near All-Time Low
            </span>
          )}
          {discountPct && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700 border border-red-200">
              ↓ {discountPct}% off
            </span>
          )}
        </div>

        {/* Product name */}
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 leading-snug mb-2">
          {name}
        </h1>

        {/* Brand + seller */}
        {(brand || seller) && (
          <p className="text-sm text-slate-500 mb-3">
            {brand && <span>By <span className="font-medium text-slate-700">{brand}</span></span>}
            {brand && seller && <span className="mx-1.5">·</span>}
            {seller && <span>Sold by <span className="font-medium text-slate-700">{seller}</span></span>}
          </p>
        )}

        {/* Rating */}
        {rating && (
          <div className="flex items-center gap-1.5 mb-3">
            <div className="flex items-center gap-0.5">
              {[1, 2, 3, 4, 5].map((star) => (
                <span
                  key={star}
                  className={`text-sm ${
                    star <= Math.round(Number(rating))
                      ? 'text-amber-400'
                      : 'text-slate-200'
                  }`}
                >
                  ★
                </span>
              ))}
            </div>
            <span className="text-sm font-medium text-slate-700">{Number(rating).toFixed(1)}</span>
            {review_count && (
              <span className="text-sm text-slate-500">
                ({Number(review_count).toLocaleString('en-IN')} reviews)
              </span>
            )}
          </div>
        )}

        {/* Watcher count */}
        {watcher_count > 0 && (
          <div className="flex items-center gap-1.5 text-sm text-slate-500 mb-4">
            <Users size={14} />
            <span>
              <span className="font-medium text-slate-700">{watcher_count}</span>{' '}
              {watcher_count === 1 ? 'person' : 'people'} monitoring this
            </span>
          </div>
        )}

        {/* Quick spec chips */}
        {specChips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {specChips.map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] bg-slate-100 text-slate-600 border border-slate-200"
                title={key}
              >
                {String(value)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
