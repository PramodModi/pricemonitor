/**
 * TrustBar — four social proof numbers in a horizontal strip.
 * Phase 1: static hardcoded. Phase 2: driven by GET /v1/stats.
 */
const STATS = [
  { value: '2,400+',    label: 'products tracked' },
  { value: '₹3.2Cr+',  label: 'total savings found' },
  { value: '18,000+',  label: 'price pings sent' },
  { value: '3',         label: 'platforms supported' },
]

export default function TrustBar() {
  return (
    <div className="border-y border-slate-100 bg-slate-50">
      <div className="container">
        <dl className="grid grid-cols-2 gap-px md:grid-cols-4">
          {STATS.map(({ value, label }) => (
            <div key={label} className="flex flex-col items-center py-5 px-4 text-center">
              <dt className="font-display text-2xl font-bold text-slate-900">{value}</dt>
              <dd className="mt-0.5 text-sm text-slate-500">{label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
