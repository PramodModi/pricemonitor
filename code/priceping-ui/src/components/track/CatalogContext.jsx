import { Users, TrendingDown, BarChart2, Calendar } from 'lucide-react'
import { formatPrice, formatTrackedSince } from '@/lib/utils'

/**
 * CatalogContext — the "social proof" section inside PreviewCard.
 * Shows watcher count, drop count, all-time low, and tracked-since date.
 * Only rendered when catalog_data is present (product exists in DB).
 */
export default function CatalogContext({ catalogData }) {
  if (!catalogData) {
    return (
      <div className="rounded-xl border border-primary-100 bg-primary-50 px-4 py-3">
        <p className="flex items-center gap-2 text-sm font-medium text-primary-700">
          <span className="text-base">✨</span>
          Be the first to track this product!
        </p>
        <p className="mt-0.5 text-xs text-primary-500">
          You'll get price drop alerts as soon as the price changes.
        </p>
      </div>
    )
  }

  const {
    watcher_count,
    price_stats,
    last_tracked_price,
    price_change_indicator,
    price_change_amount,
  } = catalogData

  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 space-y-2.5">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        PricePing catalog data
      </p>

      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {/* Watcher count */}
        {watcher_count > 0 && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <Users size={13} className="text-slate-400" />
            <span>
              <span className="font-semibold text-slate-800">{watcher_count}</span>{' '}
              {watcher_count === 1 ? 'person' : 'people'} watching
            </span>
          </div>
        )}

        {/* Drop count */}
        {price_stats?.drop_count > 0 && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <TrendingDown size={13} className="text-slate-400" />
            <span>
              <span className="font-semibold text-slate-800">{price_stats.drop_count}</span>{' '}
              price {price_stats.drop_count === 1 ? 'drop' : 'drops'} recorded
            </span>
          </div>
        )}

        {/* All-time low */}
        {price_stats?.all_time_low && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <BarChart2 size={13} className="text-slate-400" />
            <span>
              Lowest ever:{' '}
              <span className="font-semibold text-green-700">
                {formatPrice(price_stats.all_time_low)}
              </span>
            </span>
          </div>
        )}

        {/* Tracked since */}
        {price_stats?.first_tracked_at && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600">
            <Calendar size={13} className="text-slate-400" />
            <span>Tracked since {formatTrackedSince(price_stats.first_tracked_at)}</span>
          </div>
        )}
      </div>

      {/* Price change indicator vs last tracked price */}
      {last_tracked_price && price_change_indicator && price_change_indicator !== 'unchanged' && (
        <div className={`text-xs font-medium ${
          price_change_indicator === 'down'
            ? 'text-green-600'
            : 'text-red-500'
        }`}>
          {price_change_indicator === 'down'
            ? `↓ ${formatPrice(price_change_amount)} cheaper than last tracked`
            : `↑ ${formatPrice(price_change_amount)} higher than last tracked`}
        </div>
      )}
    </div>
  )
}
