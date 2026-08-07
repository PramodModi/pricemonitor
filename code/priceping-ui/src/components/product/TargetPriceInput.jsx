'use client'

import { useState } from 'react'
import { Target } from 'lucide-react'
import { toast } from 'sonner'
import { useAppStore } from '@/store/useAppStore'
import { formatPrice } from '@/lib/utils'

/**
 * TargetPriceInput
 * Sidebar box 4.
 * Shown only if userEmail is in store (user is logged in).
 *
 * Phase 1 note: PATCH /v1/subscriptions/{id} with { target_price } is not
 * yet built (DEF-003). The Set button shows a toast informing the user it
 * is coming soon, so the UI is visible but non-destructive.
 *
 * Props:
 *   currentPrice  number
 */
export default function TargetPriceInput({ currentPrice }) {
  const { userEmail } = useAppStore()
  const [targetInput, setTargetInput] = useState('')
  const [savedTarget, setSavedTarget] = useState(null)

  // Only show if user has an email (Phase 1 auth check)
  if (!userEmail) return null

  function handleSet() {
    const val = parseFloat(targetInput.replace(/[^0-9.]/g, ''))
    if (isNaN(val) || val <= 0) {
      toast.error('Please enter a valid price.')
      return
    }
    if (val >= currentPrice) {
      toast.error('Target price should be lower than the current price.')
      return
    }
    // Phase 1: store locally + toast; PATCH endpoint not yet built
    setSavedTarget(val)
    setTargetInput('')
    toast.success(`Target set: ${formatPrice(val)} — we'll ping you when price drops below this.`)
  }

  function handleClear() {
    setSavedTarget(null)
    toast.success('Target price removed.')
  }

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Target size={15} className="text-indigo-600 flex-shrink-0" />
        <h3 className="text-sm font-semibold text-slate-800">Set target price</h3>
      </div>

      {savedTarget ? (
        /* Saved state */
        <div className="space-y-2">
          <p className="text-sm text-slate-700">
            Target:{' '}
            <span className="font-semibold text-indigo-700">
              {formatPrice(savedTarget)}
            </span>
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setSavedTarget(null)
                setTargetInput(String(savedTarget))
              }}
              className="text-xs text-indigo-600 hover:text-indigo-700"
            >
              Edit
            </button>
            <span className="text-slate-300">·</span>
            <button
              onClick={handleClear}
              className="text-xs text-slate-400 hover:text-red-500"
            >
              Remove
            </button>
          </div>
        </div>
      ) : (
        /* Input state */
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                ₹
              </span>
              <input
                type="number"
                value={targetInput}
                onChange={(e) => setTargetInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSet()}
                placeholder={Math.round(currentPrice * 0.9).toLocaleString('en-IN')}
                className="w-full pl-7 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
                min={1}
              />
            </div>
            <button
              onClick={handleSet}
              className="btn-primary text-sm px-3 py-2 flex-shrink-0"
            >
              Set
            </button>
          </div>
          <p className="text-[11px] text-slate-400">
            Ping you when price drops below this.<br/>
            If not set, ping you on each price drop.
          </p>
        </div>
      )}
    </div>
  )
}
