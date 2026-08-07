import { formatPrice, formatMonthYear } from '@/lib/utils'

/**
 * SidebarPriceStats
 * Sidebar box 3: price stats table.
 *
 * Props:
 *   priceStats    object | null — price_stats from GET /v1/products/{id}
 *   currentPrice  number
 */
export default function SidebarPriceStats({ priceStats, currentPrice }) {
  if (!priceStats) return null

  const { all_time_low, all_time_high, drop_count, first_tracked_at } = priceStats

  // Badges are only meaningful when there is a genuine price range (low < high).
  // When low === high only one price point has been recorded — both badges
  // would fire simultaneously, which is confusing and wrong.
  const hasRange =
    all_time_low != null &&
    all_time_high != null &&
    Number(all_time_low) < Number(all_time_high)

  const isAtLow =
    hasRange && Number(currentPrice) <= Number(all_time_low) * 1.05
  const isAtHigh =
    hasRange && Number(currentPrice) >= Number(all_time_high) * 0.92

  return (
    <div className="card p-4">
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
        Price Stats
      </h3>

      <div className="space-y-2.5">
        {/* Current price */}
        <StatRow
          label="Current price"
          value={formatPrice(currentPrice)}
        />

        {/* All-time low */}
        {all_time_low != null && (
          <StatRow
            label="All-time low"
            value={formatPrice(all_time_low)}
            badge={
              isAtLow ? (
                <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">
                  ✅ Low
                </span>
              ) : null
            }
          />
        )}

        {/* All-time high */}
        {all_time_high != null && (
          <StatRow
            label="All-time high"
            value={formatPrice(all_time_high)}
            badge={
              isAtHigh ? (
                <span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                  ❌ High
                </span>
              ) : null
            }
          />
        )}

        {/* Price drops */}
        {drop_count != null && (
          <StatRow
            label="Price drops"
            value={`${drop_count} time${drop_count !== 1 ? 's' : ''}`}
          />
        )}

        {/* Tracked since */}
        {first_tracked_at && (
          <StatRow
            label="Tracked since"
            value={formatMonthYear(first_tracked_at)}
          />
        )}
      </div>
    </div>
  )
}

function StatRow({ label, value, badge }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="font-medium text-slate-800">{value}</span>
        {badge}
      </div>
    </div>
  )
}
