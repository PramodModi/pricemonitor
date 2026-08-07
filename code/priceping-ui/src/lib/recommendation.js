/**
 * Rule-based buying recommendation engine — Phase 1.
 *
 * Input: price_stats object from GET /v1/products/{id}
 * Output: locked shape (same interface when Phase 3 upgrades to ML API call)
 *
 * {
 *   verdict:    "buy" | "wait" | "high" | "neutral" | "insufficient",
 *   message:    string,   // one sentence, user-facing, max 100 chars
 *   confidence: null,     // populated in Phase 3 by ML model
 *   reasoning:  null,     // populated in Phase 3 by ML model
 * }
 *
 * Rules evaluated in priority order (first match wins):
 *  1. current ≤ all_time_low × 1.05   → buy  (near all-time low)
 *  2. current ≤ avg × 0.90            → buy  (>10% below average)
 *  3. current ≥ all_time_high × 0.92  → high (near all-time high)
 *  4. drop_count ≥ 3                  → wait (frequent drops)
 *  5. avg × 0.90 < current < avg × 1.10 → neutral
 *  6. fallthrough                     → insufficient
 */
export function computeRecommendation(priceStats, currentPrice) {
  // Guard: no data
  if (!priceStats || currentPrice == null) {
    return {
      verdict: 'insufficient',
      message: "We're still collecting price history. Check back in a few days.",
      confidence: null,
      reasoning: null,
    }
  }

  const { all_time_low, all_time_high, drop_count, first_tracked_at } = priceStats
  const current = Number(currentPrice)

  // Need at least some history to give a meaningful signal
  const hasHistory = all_time_low != null && all_time_high != null
  if (!hasHistory || drop_count == null) {
    return {
      verdict: 'insufficient',
      message: "We're still collecting price history. Check back in a few days.",
      confidence: null,
      reasoning: null,
    }
  }

  const low = Number(all_time_low)
  const high = Number(all_time_high)
  const avg = (low + high) / 2

  // Rule 1 — near all-time low
  if (current <= low * 1.05) {
    return {
      verdict: 'buy',
      message: "Near the lowest price we've ever recorded. Strong buy signal.",
      confidence: null,
      reasoning: null,
    }
  }

  // Rule 2 — more than 10% below average
  if (current <= avg * 0.90) {
    return {
      verdict: 'buy',
      message: 'Price is more than 10% below average. Good time to buy.',
      confidence: null,
      reasoning: null,
    }
  }

  // Rule 3 — near all-time high
  if (current >= high * 0.92) {
    return {
      verdict: 'high',
      message: 'Price is near its all-time high. Consider waiting.',
      confidence: null,
      reasoning: null,
    }
  }

  // Rule 4 — frequent drops (proxy: drop_count ≥ 3)
  // Phase 2 will use last_drop_at for recency check
  if (drop_count >= 3) {
    return {
      verdict: 'wait',
      message: `Price has dropped ${drop_count} times. Another drop may follow.`,
      confidence: null,
      reasoning: null,
    }
  }

  // Rule 5 — around average
  if (current > avg * 0.90 && current < avg * 1.10) {
    return {
      verdict: 'neutral',
      message: 'Price is around its historical average. No strong signal either way.',
      confidence: null,
      reasoning: null,
    }
  }

  // Rule 6 — fallthrough
  return {
    verdict: 'insufficient',
    message: "We're still collecting price history. Check back in a few days.",
    confidence: null,
    reasoning: null,
  }
}

/**
 * Visual config for each verdict — used by SidebarRecommendation.jsx.
 */
export const VERDICT_CONFIG = {
  buy: {
    icon: '✅',
    label: 'Great time to buy',
    cardClass: 'bg-green-50 border-green-200',
    labelClass: 'text-green-800',
    iconClass: 'bg-green-100',
  },
  wait: {
    icon: '⏳',
    label: 'Consider waiting',
    cardClass: 'bg-amber-50 border-amber-200',
    labelClass: 'text-amber-800',
    iconClass: 'bg-amber-100',
  },
  high: {
    icon: '⛔',
    label: 'Price is high',
    cardClass: 'bg-red-50 border-red-200',
    labelClass: 'text-red-800',
    iconClass: 'bg-red-100',
  },
  neutral: {
    icon: '📊',
    label: 'Average price',
    cardClass: 'bg-slate-50 border-slate-200',
    labelClass: 'text-slate-700',
    iconClass: 'bg-slate-100',
  },
  insufficient: {
    icon: '📈',
    label: 'Collecting data',
    cardClass: 'bg-slate-50 border-slate-200',
    labelClass: 'text-slate-500',
    iconClass: 'bg-slate-100',
  },
}
