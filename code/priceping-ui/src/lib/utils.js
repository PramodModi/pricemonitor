/**
 * Utility functions for PricePing frontend.
 * All date formatting is IST-aware (Asia/Kolkata).
 */

import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

// ─── shadcn/ui class merging ──────────────────────────────────────────────────

/**
 * Merge Tailwind classes, resolving conflicts correctly.
 * Required by shadcn/ui components and any component that uses conditional classes.
 * cn('px-2 py-1', condition && 'bg-red-500', 'px-4') → 'py-1 bg-red-500 px-4'
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

// ─── Price formatting ─────────────────────────────────────────────────────────

/**
 * Format a number as Indian Rupee.
 * formatPrice(67999) → "₹67,999"
 * formatPrice(67999.50) → "₹67,999.50"  (decimal only when non-zero)
 */
export function formatPrice(value) {
  if (value == null) return '—'
  const num = Number(value)
  if (isNaN(num)) return '—'
  return num.toLocaleString('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: num % 1 === 0 ? 0 : 2,
  })
}

// ─── Date / time formatting ───────────────────────────────────────────────────

const IST = 'Asia/Kolkata'

/**
 * Relative time from an ISO timestamp.
 * formatTimeAgo("2026-08-05T08:00:00Z") → "2h ago" / "3d ago" / "just now"
 */
export function formatTimeAgo(isoStr) {
  if (!isoStr) return '—'
  const diffMs = Date.now() - new Date(isoStr).getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  const diffMo = Math.floor(diffDay / 30)
  return `${diffMo}mo ago`
}

/**
 * Full IST formatted date + time.
 * formatDateIST("2026-08-05T08:00:00Z") → "5 Aug 2026, 1:30 PM"
 */
export function formatDateIST(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleString('en-IN', {
    timeZone: IST,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

/**
 * Short date for chart axis labels.
 * formatDateShort("2026-08-05T08:00:00Z") → "5 Aug"
 */
export function formatDateShort(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleDateString('en-IN', {
    timeZone: IST,
    day: 'numeric',
    month: 'short',
  })
}

/**
 * Month + year label (for chart tooltip).
 * formatMonthYear("2026-08-05T08:00:00Z") → "Aug 2026"
 */
export function formatMonthYear(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleDateString('en-IN', {
    timeZone: IST,
    month: 'short',
    year: 'numeric',
  })
}

// ─── Slug ─────────────────────────────────────────────────────────────────────

/**
 * Generate a URL slug from a product name and an ID suffix.
 * slugify("Apple iPhone 15 (128GB)", "B0CHX1W1XY")
 *   → "apple-iphone-15-128gb-B0CHX1W1XY"
 *
 * Note: In Phase 1 the "slug" is just the product_id UUID.
 * This function is used for Phase 2 when DB slug generation is added.
 */
export function slugify(name, idSuffix) {
  const base = name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')   // strip special chars
    .replace(/\s+/g, '-')           // spaces → dashes
    .replace(/-+/g, '-')            // collapse multiple dashes
    .replace(/^-|-$/g, '')          // trim leading/trailing dashes
  return `${base}-${idSuffix}`
}

// ─── Platform helpers ─────────────────────────────────────────────────────────

const PLATFORM_LABELS = {
  amazon: 'Amazon India',
  flipkart: 'Flipkart',
  myntra: 'Myntra',
}

const PLATFORM_BADGE_CLASSES = {
  amazon: 'badge-amazon',
  flipkart: 'badge-flipkart',
  myntra: 'badge-myntra',
}

const PLATFORM_ICONS = {
  amazon: '🛒',
  flipkart: '🛍️',
  myntra: '👗',
}

export function getPlatformLabel(platform) {
  return PLATFORM_LABELS[platform] ?? platform
}

export function getPlatformBadgeClass(platform) {
  return PLATFORM_BADGE_CLASSES[platform] ?? 'badge-amazon'
}

export function getPlatformIcon(platform) {
  return PLATFORM_ICONS[platform] ?? '🛒'
}

// ─── Validation ───────────────────────────────────────────────────────────────

/**
 * Basic email format check.
 * isValidEmail("user@example.com") → true
 */
export function isValidEmail(email) {
  if (!email || typeof email !== 'string') return false
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
}

/**
 * Returns true if the URL looks like a supported platform product page.
 * Used for client-side pre-validation before calling POST /v1/products/preview.
 *
 * Amazon short URLs (amzn.in) are validated by hostname only — the path
 * structure is unpredictable (/d/XXXXX). The backend resolves the redirect
 * and does authoritative validation.
 */
export function isSupportedPlatformUrl(url) {
  if (!url || typeof url !== 'string') return false
  try {
    const { hostname, pathname } = new URL(url.trim())

    // amzn.in short URLs — no path check, backend resolves the redirect
    const isAmazonShort = hostname.includes('amzn.in')

    // Full amazon.in product URLs — must have /dp/ or /gp/product/ in path
    const isAmazonFull =
      hostname.includes('amazon.in') &&
      (/\/dp\//.test(pathname) || /\/gp\/product\//.test(pathname))

    const isFlipkart =
      hostname.includes('flipkart.com') &&
      pathname.split('/').length >= 3

    const isMyntra =
      hostname.includes('myntra.com') &&
      pathname.split('/').length >= 3

    return isAmazonShort || isAmazonFull || isFlipkart || isMyntra
  } catch {
    return false
  }
}

/**
 * Format the discount amount between MRP and current price.
 * Returns a formatted rupee string when MRP > current_price, otherwise null.
 * formatDiscount(67999, 79999) → "₹12,000"
 * formatDiscount(67999, null) → null
 * formatDiscount(67999, 67999) → null  (no discount)
 */
export function formatDiscount(currentPrice, mrp) {
  if (currentPrice == null || mrp == null) return null
  const current = Number(currentPrice)
  const full = Number(mrp)
  if (isNaN(current) || isNaN(full) || full <= current) return null
  return formatPrice(full - current)
}

/**
 * Format a timestamp as "Month Year" for "Tracked since" display.
 * formatTrackedSince("2026-05-01T00:00:00Z") → "May 2026"
 */
export function formatTrackedSince(isoStr) {
  return formatMonthYear(isoStr)
}
