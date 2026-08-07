/**
 * RecommendationPreview — two static example recommendation cards.
 * Demonstrates the buy/wait intelligence before a visitor has tracked anything.
 * Phase 1, SSG. No API call. All content is illustrative.
 */

const EXAMPLES = [
  {
    verdict: 'buy',
    label: 'Great time to buy',
    icon: '✅',
    bgClass: 'bg-green-50',
    borderClass: 'border-green-200',
    textClass: 'text-green-800',
    labelClass: 'text-green-700',
    product: 'boAt Airdopes 141',
    message: "Near the lowest price we've ever recorded. Strong buy signal.",
    detail: 'Current ₹999 · All-time low ₹949 · Tracked 4 months',
  },
  {
    verdict: 'wait',
    label: 'Consider waiting',
    icon: '⏳',
    bgClass: 'bg-amber-50',
    borderClass: 'border-amber-200',
    textClass: 'text-amber-800',
    labelClass: 'text-amber-700',
    product: 'Samsung Galaxy S24 FE',
    message: 'Price has dropped 4 times recently. Another drop may follow.',
    detail: 'Current ₹34,999 · 4 drops in 3 months · All-time low ₹29,999',
  },
]

export default function RecommendationPreview() {
  return (
    <section className="section bg-white">
      <div className="container">
        <div className="mb-10 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary-500">
            Smart recommendations
          </p>
          <h2 className="mt-2 font-display text-display-md text-slate-900">
            Know when to buy. Know when to wait.
          </h2>
          <p className="mt-3 text-slate-500 max-w-lg mx-auto">
            PricePing analyses price history and tells you whether the current
            price is a deal or a trap — automatically, for every product you track.
          </p>
        </div>

        <div className="mx-auto grid max-w-2xl gap-4 md:grid-cols-2">
          {EXAMPLES.map(({ verdict, label, icon, bgClass, borderClass, textClass, labelClass, product, message, detail }) => (
            <div
              key={verdict}
              className={`rounded-2xl border p-5 ${bgClass} ${borderClass}`}
            >
              {/* Header */}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">{icon}</span>
                <span className={`font-display text-base font-bold ${labelClass}`}>
                  {label}
                </span>
              </div>

              {/* Product name */}
              <p className={`text-sm font-semibold ${textClass} mb-1`}>{product}</p>

              {/* Message */}
              <p className={`text-sm ${textClass} opacity-80 leading-snug`}>{message}</p>

              {/* Detail */}
              <p className={`mt-3 text-xs ${textClass} opacity-60`}>{detail}</p>

              {/* Label */}
              <p className={`mt-3 text-[10px] font-semibold uppercase tracking-wider ${textClass} opacity-50`}>
                Example · PricePing recommendation
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
