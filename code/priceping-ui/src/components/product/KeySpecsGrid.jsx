/**
 * KeySpecsGrid
 * Left column, section ②.
 * 2-column key-value table showing the top 6–8 specs.
 *
 * Props:
 *   specs  object — product_metadata.specs (key → value dict)
 *          null/undefined → section is hidden
 */
export default function KeySpecsGrid({ specs }) {
  if (!specs || Object.keys(specs).length === 0) return null

  const entries = Object.entries(specs).slice(0, 8)

  // Split into two columns: first ceil(n/2) on left, rest on right
  const mid = Math.ceil(entries.length / 2)
  const leftEntries = entries.slice(0, mid)
  const rightEntries = entries.slice(mid)

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-slate-800">Key Specifications</h2>
        <a
          href="#full-specs"
          className="text-sm text-indigo-600 hover:text-indigo-700 transition-colors"
        >
          View all specs ↓
        </a>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 border border-slate-200 rounded-xl overflow-hidden">
        {/* Left spec column */}
        <div className="divide-y divide-slate-100">
          {leftEntries.map(([key, value]) => (
            <SpecRow key={key} label={key} value={value} />
          ))}
        </div>
        {/* Right spec column */}
        {rightEntries.length > 0 && (
          <div className="divide-y divide-slate-100 border-t sm:border-t-0 sm:border-l border-slate-200">
            {rightEntries.map(([key, value]) => (
              <SpecRow key={key} label={key} value={value} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function SpecRow({ label, value }) {
  return (
    <div className="flex items-start px-4 py-3 gap-4 bg-white hover:bg-slate-50 transition-colors">
      <span className="text-xs text-slate-500 min-w-[100px] flex-shrink-0 mt-0.5 capitalize leading-relaxed">
        {label}
      </span>
      <span className="text-sm font-medium text-slate-800 leading-relaxed">
        {String(value)}
      </span>
    </div>
  )
}
