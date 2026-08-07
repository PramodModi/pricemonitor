'use client'

import { useState } from 'react'
import { Bell, RefreshCw } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { useItems } from '@/hooks/useItems'
import ProductCard from '@/components/dashboard/ProductCard'
import EmptyState from '@/components/dashboard/EmptyState'
import DeleteDialog from '@/components/dashboard/DeleteDialog'
import { isValidEmail, getPlatformLabel } from '@/lib/utils'

/**
 * Dashboard page — /dashboard
 *
 * State machine:
 *   1. No userEmail in store → show email gate
 *   2. userEmail present → call GET /v1/items and show list
 *
 * Note: GET /v1/auth/check is not yet implemented on the backend (DEF-003).
 * This page skips the auth-check step and goes straight to the items list
 * for all email-only users (the current user state for everyone).
 * When auth/check is implemented, the email gate will branch on requires_password.
 */
export default function DashboardPage() {
  const { userEmail, setUserEmail, setDeleteTarget } = useAppStore()
  const [inputEmail, setInputEmail] = useState('')
  const [emailError, setEmailError] = useState('')
  const [activePlatform, setActivePlatform] = useState(null) // null = All

  const { data, isLoading, isError, error, refetch, isFetching } = useItems(userEmail)

  // Derive unique platforms present in this user's items
  const platforms = data
    ? [...new Set(data.items.map((i) => i.product.platform))]
    : []

  // Client-side filter — no API call
  const filteredItems = activePlatform
    ? (data?.items ?? []).filter((i) => i.product.platform === activePlatform)
    : (data?.items ?? [])

  // ─── Email gate ──────────────────────────────────────────────────────────
  function handleEmailSubmit(e) {
    e.preventDefault()
    const trimmed = inputEmail.trim().toLowerCase()
    if (!isValidEmail(trimmed)) {
      setEmailError('Please enter a valid email address.')
      return
    }
    setEmailError('')
    setUserEmail(trimmed)
  }

  if (!userEmail) {
    return (
      <div className="max-w-md mx-auto pt-16 px-4">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-indigo-100 rounded-2xl mb-4">
            <Bell size={28} className="text-indigo-600" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800 mb-2">
            Your Monitored Items
          </h1>
          <p className="text-slate-500 text-sm">
            Enter your email to see all the products you&apos;re monitoring.
          </p>
        </div>

        <form onSubmit={handleEmailSubmit} className="space-y-3">
          <div>
            <input
              type="email"
              value={inputEmail}
              onChange={(e) => {
                setInputEmail(e.target.value)
                setEmailError('')
              }}
              placeholder="you@example.com"
              className="hero-input w-full"
              autoFocus
              autoComplete="email"
            />
            {emailError && (
              <p className="text-red-500 text-sm mt-1.5">{emailError}</p>
            )}
          </div>
          <button type="submit" className="btn-primary w-full">
            View My Items →
          </button>
        </form>
      </div>
    )
  }

  // ─── Items view ───────────────────────────────────────────────────────────
  return (
    <div className="px-4 py-6 sm:px-6">
      {/* Page header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">My Monitored Items</h1>
          {data && (
            <p className="text-sm text-slate-500 mt-0.5">
              {activePlatform
                ? `${filteredItems.length} of ${data.count} item${data.count !== 1 ? 's' : ''} · ${getPlatformLabel(activePlatform)}`
                : `${data.count} item${data.count !== 1 ? 's' : ''} monitored`}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn-ghost flex items-center gap-1.5 text-sm"
            title="Refresh list"
          >
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Platform tabs — only when user has items on 2+ portals */}
      {!isLoading && !isError && platforms.length > 1 && (
        <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
          <button
            onClick={() => setActivePlatform(null)}
            className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors
              ${activePlatform === null
                ? 'bg-primary-600 text-white'
                : 'border border-slate-200 bg-white text-slate-600 hover:border-primary-300 hover:text-primary-600'
              }`}
          >
            All ({data.count})
          </button>
          {platforms.map((platform) => {
            const count = data.items.filter(
              (i) => i.product.platform === platform
            ).length
            return (
              <button
                key={platform}
                onClick={() => setActivePlatform(platform)}
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors
                  ${activePlatform === platform
                    ? 'bg-primary-600 text-white'
                    : 'border border-slate-200 bg-white text-slate-600 hover:border-primary-300 hover:text-primary-600'
                  }`}
              >
                {getPlatformLabel(platform)} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Loading state — centered beacon */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          {/* Beacon rings + bell */}
          <div className="relative mb-8 flex items-center justify-center">
            {/* Outer ping ring */}
            <span className="absolute h-28 w-28 rounded-full bg-indigo-100 animate-ping opacity-25" />
            {/* Inner ping ring — delayed */}
            <span
              className="absolute h-20 w-20 rounded-full bg-indigo-200 animate-ping opacity-40"
              style={{ animationDelay: '0.4s' }}
            />
            {/* Bell icon */}
            <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-indigo-600 shadow-lg">
              <Bell size={30} className="text-white" />
            </div>
          </div>

          <h2 className="text-xl font-semibold text-slate-800 mb-2">
            Fetching your items
          </h2>
          <p className="text-sm text-slate-500 mb-5">
            Checking prices across all your monitored products…
          </p>

          {/* Bouncing dots */}
          <div className="flex gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
              style={{ animationDelay: '0ms' }} />
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
              style={{ animationDelay: '150ms' }} />
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce"
              style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <div className="card border-red-100 bg-red-50 text-center py-10">
          <p className="text-red-600 font-medium mb-1">Could not load your items</p>
          <p className="text-red-500 text-sm mb-4">
            {error?.message ?? 'Something went wrong. Please try again.'}
          </p>
          <button onClick={() => refetch()} className="btn-outline text-sm">
            Try again
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && data?.count === 0 && <EmptyState />}

      {/* Items list */}
      {!isLoading && !isError && data?.count > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredItems.map((item) => (
            <ProductCard
              key={item.subscription_id}
              item={item}
              onRemove={(subscriptionId) =>
                setDeleteTarget({
                  subscriptionId,
                  productName: item.product.name,
                })
              }
            />
          ))}
        </div>
      )}

      {/* Delete confirmation dialog — reads from global store */}
      <DeleteDialog />
    </div>
  )
}
