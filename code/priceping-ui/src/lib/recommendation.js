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
 *  0a. No stats at all (brand new product)      -> insufficient (just started)
 *  0b. Stats present but no price range         -> insufficient (just started)
 *  0c. Only one price point seen (low === high) -> insufficient (too early)
 *  1.  current <= all_time_low * 1.05 AND not near high -> buy  (near all-time low)
 *  2.  current <= avg * 0.90                    -> buy  (>10% below average)
 *  3.  current >= all_time_high * 0.92          -> high (near all-time high)
 *  4.  drop_count >= 3                          -> wait (frequent drops)
 *  5.  low/high band within 2%                  -> neutral (stable price)
 *  6.  avg * 0.90 < current < avg * 1.10        -> neutral (around average)
 *  7.  fallthrough                              -> insufficient (not enough data)
 */

function _result(verdict, message) {
  return { verdict, message, confidence: null, reasoning: null }
}

export function computeRecommendation(priceStats, currentPrice) {
  // Guard 0a: brand new product — no stats object at all
  if (!priceStats || currentPrice == null) {
    return _result(
      'insufficient',
      "Just started tracking. We'll build up price history over the next few days.",
    )
  }

  const { all_time_low, all_time_high, drop_count } = priceStats
  const current = Number(currentPrice)

  // Guard 0b: stats exist but no price range yet
  const hasRange = all_time_low != null && all_time_high != null
  if (!hasRange || drop_count == null) {
    return _result(
      'insufficient',
      "Just started tracking. We'll build up price history over the next few days.",
    )
  }

  const low  = Number(all_time_low)
  const high = Number(all_time_high)

  // Guard 0c: only one distinct price seen (low === high)
  // Rules 1-6 are meaningless when there is no price variation to compare against.
  if (low === high) {
    return _result(
      'insufficient',
      'Only one price recorded so far. Check back after a few more scans.',
    )
  }

  const avg = (low + high) / 2

  // Rule 1 — near all-time low (within 5%)
  if (current <= low * 1.05 && current < high * 0.95) {
    return _result(
      'buy',
      "Near the lowest price we've ever recorded. Strong buy signal.",
    )
  }

  // Rule 2 — more than 10% below average
  if (current <= avg * 0.90) {
    return _result(
      'buy',
      'Price is more than 10% below average. Good time to buy.',
    )
  }

  // Rule 3 — near all-time high (within 8%)
  if (current >= high * 0.92) {
    return _result(
      'high',
      'Price is near its all-time high. Consider waiting.',
    )
  }

  // Rule 4 — frequent drops
  // Phase 2 will add last_drop_at for recency filtering.
  if (drop_count >= 3) {
    return _result(
      'wait',
      `Price has dropped ${drop_count} times. Another drop may follow.`,
    )
  }

  // Rule 5 — price is stable (low/high band within 3%)
  // A very narrow band means the price barely moves — safe to buy now
  // rather than wait for a drop that may never come.
  const bandPct = high > 0 ? (high - low) / high : 0
  if (bandPct <= 0.03) {
    return _result(
      'neutral',
      'Price has been stable. Unlikely to change significantly soon.',
    )
  }

  // Rule 6 — around historical average (within +/-10%)
  if (current > avg * 0.90 && current < avg * 1.10) {
    return _result(
      'neutral',
      'Price is around its historical average. No strong signal either way.',
    )
  }

  // Rule 7 — fallthrough
  // Product has history but no clear directional signal yet.
  // Different message from guards 0a/0b/0c — data exists, just no strong signal.
  return _result(
    'insufficient',
    'Not enough price variation yet to give a confident signal.',
  )
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
