'use client'

import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { formatPrice, getPlatformBadgeClass, getPlatformLabel } from '@/lib/utils'

/**
 * ProductListCard — catalogue card for the /offers page.
 *
 * Distinct from dashboard ProductCard:
 *   - No subscription_id / delete button
 *   - Monitor button with 3 states (not tracking / tracking / no email)
 *   - Clicking card body → /products/{product_id}
 *   - Monitor button → /track?url=... (goes through full preview flow)
 *
 * Tracking state is read from the TanStack Query cache key ['items', userEmail]
 * populated by useItems() in OffersPageClient — zero extra API calls per card.
 */
export default function ProductListCard({ product }) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const userEmail = useAppStore((state) => state.userEmail)

  const {
    product_id,
    name,
    image_url,
    url,
    platform,
    current_price,
    mrp,
    special_price,
    discount_pct,
    availability,
    rating,
    review_count,
    watcher_count,
    all_time_low,
    all_time_high,
  } = product

  // ── Tracking state — cache read, no API call ────────────────────────────
  const cachedItems = queryClient.getQueryData(['items', userEmail])
  const isTracking =
    !!userEmail &&
    (cachedItems?.items?.some(
      (item) => item.product.product_id === product_id
    ) ?? false)

  // ── Price calculations ─────────────────────────────────────────────────
  const currentPriceNum = current_price ? Number(current_price) : null
  const mrpNum          = mrp           ? Number(mrp)           : null

  const hasDiscount = mrpNum && currentPriceNum && mrpNum > currentPriceNum
  const effectiveDiscountPct = discount_pct
    ? Math.round(Number(discount_pct))
    : hasDiscount
    ? Math.round(((mrpNum - currentPriceNum) / mrpNum) * 100)
    : null

  const specialPriceNum = special_price ? Number(special_price) : null
  const showSpecialPrice =
    specialPriceNum && currentPriceNum && specialPriceNum < currentPriceNum

  // All-time low badge: only when there's a genuine price range and
  // current price is at or below the recorded low.
  const atAllTimeLow =
    all_time_low &&
    all_time_high &&
    Number(all_time_low) < Number(all_time_high) &&
    currentPriceNum !== null &&
    currentPriceNum <= Number(all_time_low)

  // ── Navigation helpers ─────────────────────────────────────────────────
  const handleCardClick = () => router.push(`/products/${product_id}`)

  const handleMonitorClick = (e) => {
    e.stopPropagation() // don't also trigger handleCardClick
    if (isTracking) return
    router.push(`/track?url=${encodeURIComponent(url)}`)
  }

  return (
    <div
      className="card group flex cursor-pointer flex-col hover:shadow-md transition-shadow duration-200"
      onClick={handleCardClick}
    >
      {/* ── Product image ─────────────────────────────────────────────── */}
      <div className="relative aspect-square w-full overflow-hidden rounded-t-xl bg-slate-50">
        {image_url ? (
          <img
            src={image_url}
            alt={name || 'Product'}
            className="h-full w-full object-contain p-4"
            loading="lazy"
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

        {/* All-time low badge — top-right */}
        {atAllTimeLow && (
          <span className="absolute right-2 top-2 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700 shadow-sm">
            🏆 All-time low
          </span>
        )}
      </div>

      {/* ── Card content ──────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-2.5 p-4">
        {/* Availability */}
        <span
          className={`w-fit text-xs font-medium ${
            availability
              ? 'badge-in-stock'
              : 'badge-out-of-stock'
          }`}
        >
          {availability ? 'In Stock' : 'Out of Stock'}
        </span>

        {/* Product name — 2-line clamp */}
        <p className="line-clamp-2 text-sm font-medium leading-snug text-slate-800">
          {name || 'Unnamed Product'}
        </p>

        {/* Price section */}
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="price-large">
              {currentPriceNum ? formatPrice(currentPriceNum) : '—'}
            </span>
            {effectiveDiscountPct !== null && (
              <span className="price-drop-badge">{effectiveDiscountPct}% off</span>
            )}
          </div>

          {hasDiscount && (
            <p className="text-xs text-slate-400">
              MRP{' '}
              <span className="price-strike">{formatPrice(mrpNum)}</span>
            </p>
          )}

          {showSpecialPrice && (
            <p className="text-xs font-medium text-indigo-600">
              With bank offer: {formatPrice(specialPriceNum)}
            </p>
          )}
        </div>

        {/* Rating */}
        {rating && (
          <p className="text-xs text-slate-500">
            ⭐ {Number(rating).toFixed(1)}
            {review_count
              ? ` · ${Number(review_count).toLocaleString('en-IN')} reviews`
              : ''}
          </p>
        )}

        {/* Watcher count */}
        {watcher_count > 0 && (
          <p className="text-xs text-slate-400">
            👁 {watcher_count}{' '}
            {watcher_count === 1 ? 'person' : 'people'} monitoring
          </p>
        )}

        {/* Monitor button — pushed to bottom of card */}
        <button
          onClick={handleMonitorClick}
          disabled={isTracking}
          className={`mt-auto w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors
            ${
              isTracking
                ? 'cursor-default bg-green-50 text-green-700'
                : 'btn-primary'
            }`}
        >
          {isTracking ? '✅ Monitoring' : '🔔 Monitor this'}
        </button>
      </div>
    </div>
  )
}
