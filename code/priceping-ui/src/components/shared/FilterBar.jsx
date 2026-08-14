'use client'

import { useState } from 'react'
import { SlidersHorizontal, ChevronDown, ChevronUp, X } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Constants ─────────────────────────────────────────────────────────────────

const PLATFORMS = [
  { label: 'All',      value: null,        dot: 'bg-primary-500' },
  { label: 'Amazon',   value: 'amazon',    dot: 'bg-amber-400' },
  { label: 'Flipkart', value: 'flipkart',  dot: 'bg-blue-500' },
  { label: 'Myntra',   value: 'myntra',    dot: 'bg-pink-500' },
]

export const CATEGORIES = [
  { label: 'Mobiles',     value: 'mobiles' },
  { label: 'Electronics', value: 'electronics' },
  { label: 'Appliances',  value: 'appliances' },
  { label: 'Fashion',     value: 'fashion' },
  { label: 'Footwear',    value: 'footwear' },
  { label: 'Home',        value: 'home' },
  { label: 'Beauty',      value: 'beauty' },
  { label: 'Sports',      value: 'sports' },
  { label: 'Books',       value: 'books' },
  { label: 'Toys',        value: 'toys' },
  { label: 'Other',       value: 'other' },
]

// Convert a category slug to a display label — 'appliances' → 'Appliances'
function slugToLabel(slug) {
  return slug.charAt(0).toUpperCase() + slug.slice(1)
}

/**
 * FilterBar — collapsible horizontal filter bar for platform + category.
 *
 * Props:
 *   platforms      string[]   selected platform values (empty = All)
 *   onPlatforms    fn         called with new string[] on platform change
 *   categories     string[]   selected category values (empty = all)
 *   onCategories   fn         called with new string[] on category change
 *   resultCount    number     shown in collapsed summary line
 *
 * Platform behaviour:
 *   - "All" checkbox (value: null) means no platform filter
 *   - Checking a specific platform unchecks "All"
 *   - Unchecking all platforms reverts to "All"
 *
 * Category behaviour:
 *   - Pills are multi-select — clicking toggles
 *   - Empty selection = show all categories
 */
export default function FilterBar({
  platforms = [],
  onPlatforms,
  categories = [],
  onCategories,
  resultCount = 0,
  availableCategories = null, // null = show all; string[] = show only these slugs
}) {
  const [open, setOpen] = useState(false)

  // ── Derived state ─────────────────────────────────────────────────────────
  const isAllPlatforms = platforms.length === 0
  const activeCount = platforms.length + categories.length
  const hasFilters = activeCount > 0

  // Category pills — driven by availableCategories from DB when provided.
  // Falls back to hardcoded CATEGORIES only during initial load (null).
  const categoryPills = availableCategories !== null
    ? availableCategories
        .filter(v => v && v !== 'other')
        .map(value => ({ value, label: slugToLabel(value) }))
    : CATEGORIES.filter(c => c.value !== 'other')

  // ── Active filter summary chips (shown in collapsed bar) ──────────────────
  const activePlatformLabels = PLATFORMS
    .filter(p => p.value && platforms.includes(p.value))
    .map(p => p.label)

  const activeCategoryLabels = categoryPills
    .filter(c => categories.includes(c.value))
    .map(c => c.label)

  const summaryChips = [...activePlatformLabels, ...activeCategoryLabels]

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handlePlatformChange(value) {
    if (value === null) {
      // "All" clicked — clear platform filter
      onPlatforms([])
      return
    }
    const next = platforms.includes(value)
      ? platforms.filter(p => p !== value)   // deselect
      : [...platforms, value]                // select
    onPlatforms(next)
  }

  function handleCategoryToggle(value) {
    const next = categories.includes(value)
      ? categories.filter(c => c !== value)
      : [...categories, value]
    onCategories(next)
  }

  function removeChip(label) {
    const platform = PLATFORMS.find(p => p.label === label)
    if (platform && platform.value) {
      onPlatforms(platforms.filter(p => p !== platform.value))
      return
    }
    const category = categoryPills.find(c => c.label === label)
    if (category) {
      onCategories(categories.filter(c => c !== category.value))
    }
  }

  function clearAll() {
    onPlatforms([])
    onCategories([])
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mb-6 rounded-xl border border-slate-200 bg-slate-50 overflow-hidden">

      {/* ── Collapsed bar (always visible) ─────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-2.5">

        {/* Toggle button */}
        <button
          onClick={() => setOpen(o => !o)}
          className={cn(
            'flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium',
            'border transition-colors',
            hasFilters
              ? 'border-primary-300 bg-primary-50 text-primary-700'
              : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
          )}
        >
          <SlidersHorizontal size={13} />
          Filters
          {hasFilters && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary-600 text-[10px] text-white font-bold">
              {activeCount}
            </span>
          )}
          {open
            ? <ChevronUp size={12} className="text-slate-400" />
            : <ChevronDown size={12} className="text-slate-400" />
          }
        </button>

        {/* Active filter chips */}
        {summaryChips.length > 0 && (
          <>
            <span className="text-slate-300 text-sm">·</span>
            <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
              {summaryChips.map(label => (
                <span
                  key={label}
                  className="flex items-center gap-1 rounded-full bg-primary-100 px-2.5 py-0.5 text-xs font-medium text-primary-700"
                >
                  {label}
                  <button
                    onClick={() => removeChip(label)}
                    className="hover:text-primary-900 transition-colors"
                    aria-label={`Remove ${label} filter`}
                  >
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
            <button
              onClick={clearAll}
              className="shrink-0 text-xs text-primary-600 hover:text-primary-800 transition-colors font-medium"
            >
              Clear all
            </button>
          </>
        )}

        {/* Result count — right aligned when no chips */}
        {summaryChips.length === 0 && (
          <span className="ml-auto text-xs text-slate-400">
            {resultCount} product{resultCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── Expanded panel ──────────────────────────────────────────────── */}
      {open && (
        <div className="border-t border-slate-200 bg-white px-4 py-3 flex flex-col gap-3">

          {/* Platform row */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Platform
            </span>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map(({ label, value, dot }) => {
                const checked = value === null ? isAllPlatforms : platforms.includes(value)
                return (
                  <button
                    key={label}
                    onClick={() => handlePlatformChange(value)}
                    className={cn(
                      'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium',
                      'border transition-colors',
                      checked
                        ? 'border-primary-300 bg-primary-50 text-primary-700'
                        : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700'
                    )}
                  >
                    <span className={cn('h-2 w-2 rounded-full', dot)} />
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Category row */}
          <div className="flex flex-wrap items-start gap-2">
            <span className="w-16 shrink-0 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Category
            </span>
            <div className="flex flex-wrap gap-2">
              {categoryPills.map(({ label, value }) => {
                const active = categories.includes(value)
                return (
                  <button
                    key={value}
                    onClick={() => handleCategoryToggle(value)}
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-medium border transition-colors',
                      active
                        ? 'border-primary-300 bg-primary-50 text-primary-700'
                        : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700'
                    )}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
