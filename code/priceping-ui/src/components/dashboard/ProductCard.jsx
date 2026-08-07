'use client'

import Image from 'next/image'
import { Trash2, ExternalLink, Star } from 'lucide-react'
import {
  formatPrice,
  formatTimeAgo,
  getPlatformLabel,
  getPlatformBadgeClass,
} from '@/lib/utils'

/**
 * ProductCard — vertical grid card for the Dashboard.
 *
 * Matches the offers page card layout (image top, content below) so the
 * dashboard and offers page feel visually consistent. Differences from
 * the offers-page card:
 *   - Remove button (Trash2) in the bottom-right action row
 *   - External link button (ExternalLink) to open the product URL
 *   - "Updated X ago" timestamp at the bottom
 *   - No Monitor button — user already tracks this item
 *
 * Props:
 *   item     — one element from GET /v1/items response
 *              { subscription_id, subscribed_at, product: { ... } }
 *   onRemove(subscriptionId) — called when trash icon is clicked
 */
export default function ProductCard({ item, onRemove }) {
  const { subscription_id, product, price_drop_pct } = item

  const {
    product_id,
    name,
    image_url,
    platform,
    availability,
    current_price,
    mrp,
    special_price,
    rating,
    review_count,
    last_checked_at,
    url,
  } = product

  // Coerce to numbers — FastAPI returns Decimal fields as strings
  const currentPriceNum = Number(current_price)
  const mrpNum          = mrp           ? Number(mrp)           : null
  const specialPriceNum = special_price ? Number(special_price) : null

  const hasDiscount  = mrpNum && mrpNum > currentPriceNum
  const discountPct  = hasDiscount
    ? Math.round(((mrpNum - currentPriceNum) / mrpNum) * 100)
    : null
  const hasOfferPrice = specialPriceNum && specialPriceNum < currentPriceNum

  function handleCardClick(e) {
    if (e.target.closest('[data-no-nav]')) return
    window.open(`/products/${product_id}`, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      onClick={handleCardClick}
      className="card group flex flex-col cursor-pointer hover:shadow-md transition-shadow duration-150"
    >
      {/* ── Image ─────────────────────────────────────────────────────── */}
      <div className="relative aspect-square w-full overflow-hidden rounded-t-xl bg-slate-50">
        {image_url ? (
          <Image
            src={image_url}
            alt={name || 'Product'}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
            className="object-contain p-3"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-5xl text-slate-200">
            📦
          </div>
        )}
        {/* Platform badge — top-left */}
        <span className={`absolute left-2 top-2 ${getPlatformBadgeClass(platform)}`}>
          {getPlatformLabel(platform)}
        </span>
        {/* Price drop badge — top-right, only when price dropped since last scrape */}
        {price_drop_pct && (
          <span className="absolute right-2 top-2 rounded-full bg-green-500 px-2 py-0.5 text-[10px] font-bold text-white shadow-sm">
            ↓ {price_drop_pct}%
          </span>
        )}
      </div>

      {/* ── Content ───────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-2 p-3">
        {/* Availability */}
        <span
          className={`w-fit text-xs font-medium ${
            availability ? 'badge-in-stock' : 'badge-out-of-stock'
          }`}
        >
          {availability ? 'In Stock' : 'Out of Stock'}
        </span>

        {/* Product name */}
        <p className="line-clamp-2 text-sm font-medium leading-snug text-slate-800 group-hover:text-indigo-600 transition-colors">
          {name || 'Unnamed Product'}
        </p>

        {/* Price section */}
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="price-large">{formatPrice(currentPriceNum)}</span>
            {discountPct && (
              <span className="price-drop-badge">{discountPct}% off</span>
            )}
          </div>
          {hasDiscount && (
            <p className="text-xs text-slate-400">
              MRP <span className="price-strike">{formatPrice(mrpNum)}</span>
            </p>
          )}
          {hasOfferPrice && (
            <p className="text-xs font-medium text-amber-700">
              Offer price: {formatPrice(specialPriceNum)}
            </p>
          )}
        </div>

        {/* Rating */}
        {rating && (
          <p className="flex items-center gap-1 text-xs text-slate-500">
            <Star size={11} className="fill-amber-400 text-amber-400" />
            {Number(rating).toFixed(1)}
            {review_count && (
              <span className="text-slate-400 ml-0.5">
                ({Number(review_count).toLocaleString('en-IN')})
              </span>
            )}
          </p>
        )}

        {/* Bottom row — timestamp + action buttons */}
        <div
          className="mt-auto flex items-center justify-between pt-1"
          data-no-nav
        >
          <span className="text-[11px] text-slate-400">
            Updated {formatTimeAgo(last_checked_at)}
          </span>

          <div className="flex items-center gap-0.5" data-no-nav>
            {/* Open product page */}
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              data-no-nav
              onClick={(e) => e.stopPropagation()}
              className="rounded p-1.5 text-slate-400 hover:bg-indigo-50 hover:text-indigo-500 transition-colors"
              title="Open product page"
            >
              <ExternalLink size={14} />
            </a>
            {/* Remove from tracking */}
            <button
              data-no-nav
              onClick={(e) => {
                e.stopPropagation()
                onRemove(subscription_id)
              }}
              className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              title="Remove from monitoring"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
