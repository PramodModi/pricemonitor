import { computeRecommendation, VERDICT_CONFIG } from '@/lib/recommendation'

/**
 * SidebarRecommendation
 * Sidebar box 2: AI buying recommendation verdict card.
 * Phase 1: rule-based, computed client-side from price_stats.
 *
 * Props:
 *   priceStats    object | null — price_stats from GET /v1/products/{id}
 *   currentPrice  number
 */
export default function SidebarRecommendation({ priceStats, currentPrice }) {
  const rec = computeRecommendation(priceStats, currentPrice)
  const config = VERDICT_CONFIG[rec.verdict]

  return (
    <div className={`card p-4 border ${config.cardClass}`}>
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-2">
        <span
          className={`w-8 h-8 rounded-full flex items-center justify-center text-lg flex-shrink-0 ${config.iconClass}`}
        >
          {config.icon}
        </span>
        <span className={`text-sm font-semibold ${config.labelClass}`}>
          {config.label}
        </span>
      </div>

      {/* Message */}
      <p className="text-sm text-slate-700 leading-snug">{rec.message}</p>

      {/* Attribution */}
      <p className="text-[10px] text-slate-400 mt-2">PricePing Recommendation · Rule-based</p>
    </div>
  )
}
