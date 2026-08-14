'use client'

import { useState } from 'react'
import Image from 'next/image'
import { ArrowLeft, Loader2, Star } from 'lucide-react'
import {
  formatPrice,
  formatDiscount,
  getPlatformLabel,
  getPlatformIcon,
  getPlatformBadgeClass,
  isValidEmail,
} from '@/lib/utils'
import CatalogContext from './CatalogContext'
import { useAppStore } from '@/store/useAppStore'
import { useItems } from '@/hooks/useItems'

/**
 * PreviewCard — Step 2 of Track flow.
 * Shows scraped product details + catalog context.
 * User confirms email and clicks "Yes, track it".
 *
 * Props:
 *   previewResult — full response from POST /v1/products/preview
 *   onConfirm(email) — called when user confirms
 *   onBack()           — called when user clicks "Different product or URL" (goes to input)
 *   onBackToResults() — optional, called when user clicks "Back to search results"
 *                       only passed when preview was reached via search flow
 *   isConfirming     — shows spinner on confirm button
 *   error            — error message string (if confirm failed)
 */
export default function PreviewCard({ previewResult, onConfirm, onBack, onBackToResults, isConfirming, error }) {
  const storedEmail = useAppStore((state) => state.userEmail)
  const [email, setEmail] = useState(storedEmail ?? '')
  const [emailError, setEmailError] = useState('')

  const { live_data, catalog_data } = previewResult ?? {}

  // product_id from catalog_data — null for brand-new products.
  const productId = catalog_data?.product_id ?? null

  // Subscribe to the items query reactively. TanStack Query deduplicates —
  // TrackPageClient already started this fetch on mount, so no second network
  // request fires here. When data arrives both components re-render together.
  // Only enabled when email looks valid and product exists in DB (productId set).
  const hasValidEmail = email.trim().length > 0 && email.includes('@')
  const { data: itemsData, isLoading: isCheckingSubscription } = useItems(
    productId && hasValidEmail ? email.trim().toLowerCase() : null
  )

  // True only when this specific user is already subscribed to this product.
  // Mirrors Streamlit's _is_already_tracking() — checks items list by product_id.
  const isAlreadyTracking = !!productId && !!itemsData?.items?.some(
    (item) => String(item.product?.product_id) === String(productId)
  )

  // For existing products (catalog_data present) with a valid email, wait for
  // the subscription check before showing either button. PATH A returns in
  // ~200ms; GET /v1/items takes ~400-500ms. Without this guard, 'Yes, track it'
  // flashes briefly before 'Already tracking' appears.
  const isCheckingStatus = !!productId && hasValidEmail && isCheckingSubscription

  if (!live_data) return null

  const {
    name,
    brand,
    image_url,
    platform,
    current_price,
    mrp,
    availability,
    rating,
    review_count,
    seller,
  } = live_data

  const discount = formatDiscount(current_price, mrp)

  const handleConfirm = () => {
    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email address.')
      return
    }
    setEmailError('')
    onConfirm(email.trim().toLowerCase())
  }

  return (
    <div className="card p-6 space-y-5 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="font-display text-lg font-semibold text-slate-900">
          Is this the right product?
        </h2>
        <p className="mt-0.5 text-sm text-slate-500">
          Review the details below, then confirm your email to start tracking.
        </p>
      </div>

      {/* Product info */}
      <div className="flex gap-4">
        {/* Image */}
        <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-xl border border-slate-100 bg-slate-50">
          {image_url ? (
            <Image
              src={image_url}
              alt={name ?? 'Product image'}
              fill
              className="object-contain p-2"
              sizes="112px"
              unoptimized
            />
          ) : (
            <div className="flex h-full items-center justify-center text-3xl text-slate-300">
              📦
            </div>
          )}
        </div>

        {/* Details */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Badges */}
          <div className="flex flex-wrap gap-1.5">
            <span className={getPlatformBadgeClass(platform)}>
              {getPlatformIcon(platform)} {getPlatformLabel(platform)}
            </span>
            <span className={availability ? 'badge-in-stock' : 'badge-out-of-stock'}>
              {availability ? '✓ In stock' : '✗ Out of stock'}
            </span>
          </div>

          {/* Name */}
          <h3 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-3">
            {name}
          </h3>

          {brand && (
            <p className="text-xs text-slate-500">Brand: {brand}</p>
          )}

          {/* Price */}
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-display text-2xl font-bold text-slate-900">
              {formatPrice(current_price)}
            </span>
            <span className="inline-flex items-center rounded-md bg-primary-50 px-1.5 py-0.5
                             text-[10px] font-bold uppercase tracking-wider text-primary-600">
              Live price
            </span>
          </div>

          {(mrp || discount) && (
            <div className="flex items-center gap-2">
              {mrp && mrp > current_price && (
                <span className="price-strike">{formatPrice(mrp)}</span>
              )}
              {discount && (
                <span className="price-drop-badge">↓ {discount} less</span>
              )}
            </div>
          )}

          {/* Rating */}
          {rating && (
            <div className="flex items-center gap-1 text-xs text-amber-600 font-medium">
              <Star size={11} fill="currentColor" />
              {Number(rating).toFixed(1)}
              {review_count && (
                <span className="text-slate-400 font-normal">
                  · {new Intl.NumberFormat('en-IN').format(review_count)} ratings
                </span>
              )}
            </div>
          )}

          {seller && (
            <p className="text-xs text-slate-400">Sold by: {seller}</p>
          )}
        </div>
      </div>

      {/* Catalog context */}
      <CatalogContext catalogData={catalog_data} />

      {/* Email input */}
      <div>
        <label htmlFor="track-email" className="block text-sm font-medium text-slate-700 mb-1.5">
          📧 Email for price drop alerts
        </label>
        <input
          id="track-email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (emailError) setEmailError('')
          }}
          placeholder="you@example.com"
          className="input"
          disabled={isConfirming}
          autoComplete="email"
        />
        {emailError && (
          <p className="mt-1.5 text-xs text-red-600">{emailError}</p>
        )}
        {error && (
          <p className="mt-1.5 text-xs text-red-600">{error}</p>
        )}
      </div>

      {/* Already tracking banner — shown when stored email matches typed email */}
      {isAlreadyTracking && (
        <div className="rounded-xl border border-green-100 bg-green-50 px-4 py-3">
          <p className="flex items-center gap-2 text-sm font-medium text-green-700">
            <span className="text-base">✅</span>
            You're already tracking this product
          </p>
          <p className="mt-0.5 text-xs text-green-600">
            {storedEmail} · Price drop pings are active.
          </p>
        </div>
      )}

      {/* Actions */}
      {onBackToResults && (
        <button
          onClick={onBackToResults}
          disabled={isConfirming}
          className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 font-medium -mt-1"
        >
          <ArrowLeft size={14} />
          Back to search results
        </button>
      )}
      <div className="flex flex-col-reverse gap-3 sm:flex-row">
        <button
          onClick={onBack}
          disabled={isConfirming}
          className="btn-ghost justify-center"
        >
          <ArrowLeft size={15} />
          Different product or URL
        </button>

        {isAlreadyTracking ? (
          <a
            href="/dashboard"
            className="btn-outline flex-1 justify-center text-center"
          >
            View in dashboard →
          </a>
        ) : isCheckingStatus ? (
          // Subscription check in progress — don't show either button yet
          <button disabled className="btn-primary flex-1 justify-center opacity-70">
            <Loader2 size={16} className="animate-spin" />
            Checking…
          </button>
        ) : (
          <button
            onClick={handleConfirm}
            disabled={isConfirming}
            className="btn-primary flex-1 justify-center"
          >
            {isConfirming ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving…
              </>
            ) : (
              <>✅ Yes, track it</>
            )}
          </button>
        )}
      </div>

      {!isAlreadyTracking && (
        <p className="text-center text-xs text-slate-400">
          Preview valid for ~10 minutes · No spam, only price drop alerts
        </p>
      )}
    </div>
  )
}
