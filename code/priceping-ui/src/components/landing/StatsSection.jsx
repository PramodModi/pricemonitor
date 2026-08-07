/**
 * StatsSection — three metric tiles + supported platform chips.
 * Phase 1: static numbers. Phase 2: driven by GET /v1/stats.
 */

const METRICS = [
  {
    value: '₹8,400',
    label: 'Average saving per user',
    icon: '💰',
    sub: 'Across all tracked products',
  },
  {
    value: '~6 hrs',
    label: 'Average ping time after drop',
    icon: '⚡',
    sub: 'Checks run every 4 hours',
  },
  {
    value: '3',
    label: 'Platforms tracked',
    icon: '🛒',
    sub: 'Amazon · Flipkart · Myntra',
  },
]

const PLATFORMS = [
  { name: 'Amazon India', icon: '🛒', color: 'text-orange-700 bg-orange-50 border-orange-100' },
  { name: 'Flipkart',     icon: '🛍️', color: 'text-blue-700 bg-blue-50 border-blue-100' },
  { name: 'Myntra',       icon: '👗', color: 'text-pink-700 bg-pink-50 border-pink-100' },
]

export default function StatsSection() {
  return (
    <section className="section bg-primary-950">
      <div className="container">
        <div className="mb-10 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary-400">
            By the numbers
          </p>
          <h2 className="mt-2 font-display text-display-md text-white">
            Built for Indian shoppers
          </h2>
        </div>

        {/* Metric tiles */}
        <div className="grid gap-4 md:grid-cols-3">
          {METRICS.map(({ value, label, icon, sub }) => (
            <div
              key={label}
              className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center"
            >
              <div className="mb-3 text-3xl">{icon}</div>
              <div className="font-display text-3xl font-bold text-white">{value}</div>
              <div className="mt-1.5 text-sm font-medium text-primary-200">{label}</div>
              <div className="mt-1 text-xs text-primary-400">{sub}</div>
            </div>
          ))}
        </div>

        {/* Platform chips */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <span className="text-sm text-primary-400">Tracks prices on:</span>
          {PLATFORMS.map(({ name, icon, color }) => (
            <span
              key={name}
              className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5
                          text-sm font-medium ${color}`}
            >
              {icon} {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
