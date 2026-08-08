'use client'

import { useState } from 'react'
import { RefreshCw, Copy, Check, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { useAppStore } from '@/store/useAppStore'
import { useItems } from '@/hooks/useItems'
import { formatPrice, formatDateIST, getPlatformLabel } from '@/lib/utils'

/**
 * SidebarPriceBox
 * Sidebar box 1: price display, buy button, track CTA, refresh, share.
 *
 * Track CTA has three states:
 *   A — no email in store → navigate to /track?url=...
 *   B — email known, not tracking → navigate to /track?url=...
 *   C — currently tracking (isTracking=true) → show "✅ Tracking" + "Stop tracking" (unimplemented in Phase 1)
 *
 * Note: In Phase 1 we can't check if the current user is tracking this specific
 * product without an extra API call. We use a simple heuristic: if the user came
 * from the dashboard (referer check is unreliable in Next.js CSR), show State B.
 * A proper subscription check requires the auth endpoints (DEF-003).
 * For Phase 1, this box always shows State A or B based on userEmail.
 *
 * Props:
 *   product   — full product object from GET /v1/products/{id}
 *   onRefresh — () => void — calls refetch on the product query
 *   isRefreshing — boolean
 */
export default function SidebarPriceBox({ product, onRefresh, isRefreshing }) {
  const { userEmail } = useAppStore()
  const [copied, setCopied] = useState(false)

  // Fetch the user's tracked items so isTracking is accurate even when the
  // product page opens in a new tab (empty cache). useItems is a no-op when
  // userEmail is null (enabled: !!email guard). TanStack Query deduplicates
  // the request if the cache is already warm from a prior dashboard visit.
  const { data: itemsData, isLoading: isCheckingStatus } = useItems(userEmail)
  const isTracking =
    !!userEmail &&
    !!product?.product_id &&
    (itemsData?.items?.some(
      (item) => item.product?.product_id === product.product_id
    ) ?? false)

  const {
    current_price,
    mrp,
    special_price,
    discount_pct,
    availability,
    platform,
    url,
    last_checked_at,
  } = product

  const hasDiscount = mrp && mrp > current_price
  const discountPct =
    discount_pct ??
    (hasDiscount ? Math.round(((mrp - current_price) / mrp) * 100) : null)
  const hasOfferPrice = special_price && special_price < current_price

  // Track CTA URL — pre-fills the track page with this product's URL
  const trackUrl = `/track?url=${encodeURIComponent(url)}`

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      toast.success('Link copied!')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Could not copy link.')
    }
  }

  function handleWhatsApp() {
    const text = encodeURIComponent(
      `${product.name}\n${formatPrice(current_price)} on ${getPlatformLabel(platform)}\n${window.location.href}`
    )
    window.open(`https://wa.me/?text=${text}`, '_blank')
  }

  return (
    <div className="card p-5 space-y-4">
      {/* Price block */}
      <div>
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-3xl font-bold text-slate-900 tracking-tight">
            {formatPrice(current_price)}
          </span>
          {hasDiscount && (
            <span className="text-sm font-medium text-green-600">
              {discountPct}% off
            </span>
          )}
        </div>

        {hasDiscount && (
          <p className="text-sm text-slate-400 mt-0.5">
            MRP: <span className="line-through">{formatPrice(mrp)}</span>
          </p>
        )}

        {hasOfferPrice && (
          <p className="text-sm text-amber-700 mt-1 font-medium">
            Offer price: {formatPrice(special_price)} (with bank offer)
          </p>
        )}
      </div>

      {/* Availability */}
      <div className="flex items-center gap-2">
        {availability ? (
          <>
            <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
            <span className="text-sm text-green-700 font-medium">
              In stock on {getPlatformLabel(platform)}
            </span>
          </>
        ) : (
          <>
            <span className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
            <span className="text-sm text-red-600 font-medium">Out of stock</span>
          </>
        )}
      </div>

      {/* Buy button */}
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="btn-accent w-full flex items-center justify-center gap-2"
      >
        Buy on {getPlatformLabel(platform)}
        <ExternalLink size={14} />
      </a>

      {/* Track CTA — three states + checking guard */}
      {isCheckingStatus ? (
        // Subscription status not yet known — show neutral spinner
        // so neither "Monitor" nor "Watching this" flashes incorrectly
        <div className="btn-outline w-full flex items-center justify-center gap-2 opacity-60 cursor-wait pointer-events-none">
          <RefreshCw size={14} className="animate-spin" />
          Checking…
        </div>
      ) : isTracking ? (
        // State C — already tracking this product
        <div className="w-full rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-center">
          <p className="text-sm font-semibold text-green-700">✅ Watching this</p>
          <p className="text-xs text-green-600 mt-0.5">We'll notify you when the price drops.</p>
        </div>
      ) : (
        // State A/B — not tracking, navigate to track page
        <div className="space-y-1.5">
          <a href={trackUrl} className="btn-outline w-full flex items-center justify-center gap-2">
            🔔 {userEmail ? 'Monitor · Get drop pings' : 'Monitor this price'}
          </a>
          {userEmail && (
            <p className="text-center text-[11px] text-slate-400">
              Pings go to{' '}
              <span className="font-medium text-slate-500 truncate inline-block max-w-[180px] align-bottom">
                {userEmail}
              </span>
            </p>
          )}
        </div>
      )}

      {/* Last checked + refresh */}
      <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-100">
        <span>Updated {formatDateIST(last_checked_at)}</span>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1 text-slate-500 hover:text-indigo-600 transition-colors"
          title="Refresh price"
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Share row */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleCopyLink}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors px-2.5 py-1.5 rounded-lg hover:bg-slate-100"
        >
          {copied ? <Check size={12} className="text-green-600" /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy link'}
        </button>
        <button
          onClick={handleWhatsApp}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-green-600 transition-colors px-2.5 py-1.5 rounded-lg hover:bg-green-50"
        >
          💬 WhatsApp
        </button>
      </div>
    </div>
  )
}
