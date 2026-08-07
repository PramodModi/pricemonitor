import { ExternalLink } from 'lucide-react'
import { formatPrice, getPlatformLabel } from '@/lib/utils'

/**
 * MobileBottomBar
 * Pinned to the bottom of the viewport on mobile (hidden on desktop).
 * Shows only: current price | Buy button | Track button.
 *
 * Props:
 *   product   — product object from GET /v1/products/{id}
 */
export default function MobileBottomBar({ product }) {
  const { current_price, url, platform } = product
  const trackUrl = `/track?url=${encodeURIComponent(url)}`

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 md:hidden bg-white border-t border-slate-200 shadow-[0_-4px_24px_rgba(0,0,0,0.08)]">
      <div className="flex items-center px-4 py-3 gap-3 max-w-2xl mx-auto">
        {/* Price */}
        <div className="flex-shrink-0">
          <p className="text-xs text-slate-500 leading-none mb-0.5">Current price</p>
          <p className="text-lg font-bold text-slate-900 leading-none">
            {formatPrice(current_price)}
          </p>
        </div>

        <div className="flex-1 flex gap-2">
          {/* Buy button */}
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-accent flex-1 flex items-center justify-center gap-1.5 text-sm"
          >
            Buy on {getPlatformLabel(platform)}
            <ExternalLink size={13} />
          </a>

          {/* Track button */}
          <a
            href={trackUrl}
            className="btn-outline flex-shrink-0 px-3 text-sm flex items-center gap-1"
          >
            🔔 Monitor
          </a>
        </div>
      </div>
    </div>
  )
}
