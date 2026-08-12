import Link from 'next/link'
import { useState } from 'react'
import { formatPrice, getPlatformLabel, formatTimeAgo } from '@/lib/utils'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import api from '@/lib/api'

/**
 * CrossPortalSuggestion — Option B card shown after subscription.
 * "Also on Flipkart — ₹72,999 (last checked 3h ago)"
 */
function CrossPortalSuggestion({ listing, onDismiss }) {
  const queryClient  = useQueryClient()
  const userEmail    = useAppStore((s) => s.userEmail)
  const setEmail     = useAppStore((s) => s.setUserEmail)

  const [isAdding, setIsAdding]         = useState(false)
  const [isDone, setIsDone]             = useState(false)
  const [showEmail, setShowEmail]       = useState(false)
  const [emailInput, setEmailInput]     = useState('')
  const [emailError, setEmailError]     = useState('')

  const doSubscribe = async (email) => {
    setIsAdding(true)
    try {
      await api.post('/v1/subscriptions/direct', {
        product_id: listing.product_id,
        email,
      })
      if (!userEmail) setEmail(email)
      await queryClient.invalidateQueries({ queryKey: ['items', email] })
      setIsDone(true)
    } catch {
      // silent — user can dismiss and try manually
    } finally {
      setIsAdding(false)
    }
  }

  const handleTrack = () => {
    if (userEmail) {
      doSubscribe(userEmail)
    } else {
      setShowEmail(true)
    }
  }

  if (isDone) {
    return (
      <div className="rounded-xl border border-green-100 bg-green-50 p-4 text-center">
        <p className="text-sm font-medium text-green-700">
          ✅ Now monitoring on {getPlatformLabel(listing.platform)} too!
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wide mb-1">
            💡 Also available
          </p>
          <p className="text-sm font-medium text-slate-800">
            On {getPlatformLabel(listing.platform)}{' '}
            {listing.current_price && (
              <span className="text-indigo-600 font-semibold">
                — {formatPrice(listing.current_price)}
              </span>
            )}
          </p>
          {listing.last_checked_at && (
            <p className="text-xs text-slate-400 mt-0.5">
              last checked {formatTimeAgo(listing.last_checked_at)}
            </p>
          )}
        </div>
        <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600 text-lg leading-none">
          ×
        </button>
      </div>

      {showEmail ? (
        <form onSubmit={(e) => {
          e.preventDefault()
          const t = emailInput.trim()
          if (!t || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) {
            setEmailError('Please enter a valid email.')
            return
          }
          setEmailError('')
          doSubscribe(t)
        }} className="space-y-1.5">
          <input type="email" value={emailInput} onChange={(e) => setEmailInput(e.target.value)}
            placeholder="you@example.com" autoFocus
            className="w-full rounded-md border border-indigo-200 bg-white px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          {emailError && <p className="text-[10px] text-red-500">{emailError}</p>}
          <div className="flex gap-1.5">
            <button type="submit" disabled={isAdding} className="flex-1 rounded-md bg-indigo-600 py-1.5 text-xs font-semibold text-white disabled:opacity-60">
              {isAdding ? 'Adding…' : 'Monitor'}
            </button>
            <button type="button" onClick={onDismiss} className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-500">
              No thanks
            </button>
          </div>
        </form>
      ) : (
        <div className="flex gap-2">
          <button onClick={handleTrack} disabled={isAdding}
            className="flex-1 rounded-lg bg-indigo-600 py-2 text-xs font-semibold text-white disabled:opacity-60">
            {isAdding ? 'Adding…' : `🔔 Monitor on ${getPlatformLabel(listing.platform)}`}
          </button>
          <button onClick={onDismiss}
            className="rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs text-slate-500">
            No thanks
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * SuccessScreen — Step 3 of Track flow.
 * Shown after subscription is confirmed.
 *
 * Props:
 *   email                — the email that will receive alerts
 *   productId            — to navigate to product detail page
 *   productSlug          — preferred over productId for URL
 *   crossPortalListings  — other portal listings for Option B suggestion
 *   onTrackAnother()     — resets back to Step 1
 */
export default function SuccessScreen({ email, productId, productSlug, crossPortalListings = [], onTrackAnother }) {
  const [dismissedIds, setDismissedIds] = useState([])

  const productHref = productSlug
    ? `/products/${productSlug}`
    : productId
      ? `/products/${productId}`
      : null

  const visibleSuggestions = crossPortalListings.filter(
    (l) => !dismissedIds.includes(l.product_id)
  )

  return (
    <div className="card p-8 text-center space-y-5 animate-slide-up">
      {/* Icon */}
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-green-100 text-3xl">
        ✅
      </div>

      {/* Heading */}
      <div>
        <h2 className="font-display text-xl font-semibold text-slate-900">
          You're now monitoring this product!
        </h2>
        {email && (
          <p className="mt-2 text-sm text-slate-500">
            We'll email{' '}
            <span className="font-medium text-slate-700">{email}</span>{' '}
            the moment the price drops.
          </p>
        )}
      </div>

      {/* Option B — cross-portal suggestions */}
      {visibleSuggestions.length > 0 && (
        <div className="space-y-2 text-left">
          {visibleSuggestions.map((listing) => (
            <CrossPortalSuggestion
              key={listing.product_id}
              listing={listing}
              onDismiss={() => setDismissedIds((ids) => [...ids, listing.product_id])}
            />
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col gap-3">
        {productHref && (
          <Link href={productHref} className="btn-primary justify-center">
            View product details →
          </Link>
        )}
        <button onClick={onTrackAnother} className="btn-outline justify-center">
          Monitor another item
        </button>
        <Link href="/dashboard" className="btn-ghost justify-center text-slate-500">
          Go to my dashboard
        </Link>
      </div>
    </div>
  )
}
