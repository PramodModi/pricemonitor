/**
 * HowItWorks — 3-step static explainer.
 * Always present. Phase 1, SSG. No API call.
 */

const STEPS = [
  {
    number: '1',
    icon: '📋',
    title: 'Paste the URL',
    description:
      'Copy any product link from Amazon, Flipkart, or Myntra and paste it into PricePing.',
  },
  {
    number: '2',
    icon: '👀',
    title: 'We track the price',
    description:
      'PricePing checks the price every few hours automatically — no action needed from you.',
  },
  {
    number: '3',
    icon: '🔔',
    title: 'Get pinged instantly',
    description:
      'The moment the price drops, we ping you by email with the new price and a direct buy link.',
  },
]

export default function HowItWorks() {
  return (
    <section className="section bg-slate-50">
      <div className="container">
        <div className="mb-12 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary-500">
            How it works
          </p>
          <h2 className="mt-2 font-display text-display-md text-slate-900">
            Three steps. Zero effort.
          </h2>
          <p className="mt-3 text-slate-500">
            Set it up once. PricePing does the rest.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3 md:gap-8">
          {STEPS.map(({ number, icon, title, description }) => (
            <div
              key={number}
              className="relative flex flex-col gap-4 rounded-2xl border border-slate-100
                         bg-white p-6 shadow-card"
            >
              {/* Step number badge */}
              <div className="flex h-10 w-10 items-center justify-center rounded-xl
                              bg-primary-600 font-display text-lg font-bold text-white">
                {number}
              </div>

              {/* Icon */}
              <span className="text-3xl">{icon}</span>

              {/* Content */}
              <div>
                <h3 className="font-display text-lg font-semibold text-slate-900">{title}</h3>
                <p className="mt-1.5 text-sm text-slate-500 leading-relaxed">{description}</p>
              </div>

              {/* Connector arrow — only between steps on desktop */}
              {number !== '3' && (
                <div className="absolute -right-4 top-10 hidden text-slate-200 md:block text-2xl z-10">
                  →
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
