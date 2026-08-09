'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { formatPrice, getPlatformBadgeClass, getPlatformLabel } from '@/lib/utils'
import api from '@/lib/api'

/**
 * ProductListCard — catalogue card for the /offers page.
 *
 * Monitor flow (no scrape — product is already in DB):
 *   - Email in store  → POST /v1/subscriptions/direct immediately
 *   - No email        → show inline email prompt, then POST on submit
 *
 * Tracking state is read from TanStack Query cache ['items', userEmail].
 */
export default function ProductListCard({ product }) {
  const router      = useRouter()
  const queryClient = useQueryClient()
  const userEmail   = useAppStore((s) => s.userEmail)
  const setEmail    = useAppStore((s) => s.setUserEmail)

  const [isSubscribing, setIsSubscribing]     = useState(false)
  const [showEmailPrompt, setShowEmailPrompt] = useState(false)
  const [emailInput, setEmailInput]           = useState('')
  const [emailError, setEmailError]           = useState('')
  const [toastMsg, setToastMsg]               = useState('')

  const {
    product_id, name, image_url, url, platform,
    current_price, mrp, special_price, discount_pct,
    availability, rating, review_count,
    watcher_count, all_time_low, all_time_high,
  } = product

  // ── Tracking state — cache read, no API call ──────────────────────────
  const cachedItems = queryClient.getQueryData(['items', userEmail])
  const isTracking  =
    !!userEmail &&
    (cachedItems?.items?.some(
      (item) => item.product.product_id === product_id,
    ) ?? false)

  // ── Price calculations ────────────────────────────────────────────────
  const currentPriceNum = current_price ? Number(current_price) : null
  const mrpNum          = mrp           ? Number(mrp)           : null
  const hasDiscount     = mrpNum && currentPriceNum && mrpNum > currentPriceNum
  const effectiveDiscountPct = discount_pct
    ? Math.round(Number(discount_pct))
    : hasDiscount
    ? Math.round(((mrpNum - currentPriceNum) / mrpNum) * 100)
    : null
  const specialPriceNum  = special_price ? Number(special_price) : null
  const showSpecialPrice =
    specialPriceNum && currentPriceNum && specialPriceNum < currentPriceNum
  const atAllTimeLow =
    all_time_low && all_time_high &&
    Number(all_time_low) < Number(all_time_high) &&
    currentPriceNum !== null &&
    currentPriceNum <= Number(all_time_low)

  // ── Subscribe helper ──────────────────────────────────────────────────
  const showToast = (msg) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 3000)
  }

  const doSubscribe = async (email) => {
    setIsSubscribing(true)
    try {
      await api.post('/v1/subscriptions/direct', {
        product_id,
        email,
      })
      // Persist email in store if it came from the prompt
      if (!userEmail) setEmail(email)
      // Invalidate items cache so button flips to "✅ Monitoring"
      await queryClient.invalidateQueries({ queryKey: ['items', email] })
      showToast('You\'re now monitoring this product 🔔')
      setShowEmailPrompt(false)
    } catch (err) {
      const msg =
        err?.response?.data?.detail?.message ||
        'Something went wrong. Please try again.'
      showToast(msg)
    } finally {
      setIsSubscribing(false)
    }
  }

  // ── Monitor button click ──────────────────────────────────────────────
  const handleMonitorClick = (e) => {
    e.stopPropagation()
    if (isTracking || isSubscribing) return
    if (userEmail) {
      doSubscribe(userEmail)
    } else {
      setShowEmailPrompt(true)
    }
  }

  // ── Email prompt submit ───────────────────────────────────────────────
  const handleEmailSubmit = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const trimmed = emailInput.trim()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setEmailError('Please enter a valid email address.')
      return
    }
    setEmailError('')
    doSubscribe(trimmed)
  }

  return (
    <div
      className="card group relative flex cursor-pointer flex-col hover:shadow-md transition-shadow duration-200"
      onClick={() => router.push(`/products/${product_id}`)}
    >
      {/* ── Toast ─────────────────────────────────────────────────────── */}
      {toastMsg && (
        <div
          className="absolute inset-x-2 top-2 z-20 rounded-lg bg-slate-800 px-3 py-2 text-center text-xs font-medium text-white shadow-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {toastMsg}
        </div>
      )}

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
        <span className={`absolute left-2 top-2 ${getPlatformBadgeClass(platform)}`}>
          {getPlatformLabel(platform)}
        </span>
        {atAllTimeLow && (
          <span className="absolute right-2 top-2 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700 shadow-sm">
            🏆 All-time low
          </span>
        )}
      </div>

      {/* ── Card content ──────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-2.5 p-4">
        <span
          className={`w-fit text-xs font-medium ${
            availability ? 'badge-in-stock' : 'badge-out-of-stock'
          }`}
        >
          {availability ? 'In Stock' : 'Out of Stock'}
        </span>

        <p className="line-clamp-2 text-sm font-medium leading-snug text-slate-800">
          {name || 'Unnamed Product'}
        </p>

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
              MRP <span className="price-strike">{formatPrice(mrpNum)}</span>
            </p>
          )}
          {showSpecialPrice && (
            <p className="text-xs font-medium text-indigo-600">
              With bank offer: {formatPrice(specialPriceNum)}
            </p>
          )}
        </div>

        {rating && (
          <p className="text-xs text-slate-500">
            ⭐ {Number(rating).toFixed(1)}
            {review_count
              ? ` · ${Number(review_count).toLocaleString('en-IN')} reviews`
              : ''}
          </p>
        )}

        {watcher_count > 0 && (
          <p className="text-xs text-slate-400">
            👁 {watcher_count}{' '}
            {watcher_count === 1 ? 'person' : 'people'} monitoring
          </p>
        )}

        {/* ── Email prompt (shown when no email in store) ────────────── */}
        {showEmailPrompt && (
          <div
            className="mt-1 rounded-lg border border-indigo-100 bg-indigo-50 p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="mb-2 text-xs font-medium text-indigo-800">
              Enter your email to get price drop alerts
            </p>
            <form onSubmit={handleEmailSubmit} className="flex flex-col gap-1.5">
              <input
                type="email"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-md border border-indigo-200 bg-white px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                autoFocus
              />
              {emailError && (
                <p className="text-[10px] text-red-500">{emailError}</p>
              )}
              <div className="flex gap-1.5">
                <button
                  type="submit"
                  disabled={isSubscribing}
                  className="flex-1 rounded-md bg-indigo-600 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                >
                  {isSubscribing ? 'Adding…' : 'Monitor'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowEmailPrompt(false); setEmailError('') }}
                  className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-500"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── Monitor button ─────────────────────────────────────────── */}
        {!showEmailPrompt && (
          <button
            onClick={handleMonitorClick}
            disabled={isTracking || isSubscribing}
            className={`mt-auto w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors
              ${
                isTracking
                  ? 'cursor-default bg-green-50 text-green-700'
                  : isSubscribing
                  ? 'cursor-wait bg-indigo-100 text-indigo-400'
                  : 'btn-primary'
              }`}
          >
            {isTracking
              ? '✅ Monitoring'
              : isSubscribing
              ? 'Adding…'
              : '🔔 Monitor this'}
          </button>
        )}
      </div>
    </div>
  )
}
