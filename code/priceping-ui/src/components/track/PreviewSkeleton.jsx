/**
 * PreviewSkeleton — shown during the 10–20 second scrape on the Track page.
 * Matches PreviewCard approximate dimensions to prevent layout shift.
 */
export default function PreviewSkeleton() {
  return (
    <div className="card p-6 space-y-5 animate-fade-in">
      {/* Title bar */}
      <div className="space-y-2">
        <div className="skeleton h-4 w-40 rounded" />
        <div className="skeleton h-3 w-56 rounded" />
      </div>

      {/* Product row */}
      <div className="flex gap-4">
        {/* Image */}
        <div className="skeleton h-28 w-28 shrink-0 rounded-xl" />

        {/* Details */}
        <div className="flex-1 space-y-3 py-1">
          <div className="skeleton h-4 w-full rounded" />
          <div className="skeleton h-4 w-4/5 rounded" />
          <div className="skeleton h-4 w-3/5 rounded" />

          <div className="flex gap-2 pt-1">
            <div className="skeleton h-5 w-24 rounded-full" />
            <div className="skeleton h-5 w-16 rounded-full" />
          </div>

          <div className="skeleton h-8 w-32 rounded" />
        </div>
      </div>

      {/* Catalog context bar */}
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 space-y-2.5">
        <div className="skeleton h-3.5 w-40 rounded" />
        <div className="flex gap-4">
          <div className="skeleton h-3 w-24 rounded" />
          <div className="skeleton h-3 w-20 rounded" />
        </div>
      </div>

      {/* Email field */}
      <div className="skeleton h-11 w-full rounded-xl" />

      {/* Buttons */}
      <div className="flex gap-3">
        <div className="skeleton h-11 w-36 rounded-xl" />
        <div className="skeleton h-11 flex-1 rounded-xl" />
      </div>

      {/* Loading note */}
      <p className="text-center text-xs text-slate-400 animate-pulse">
        Fetching product details — this takes up to 20 seconds…
      </p>
    </div>
  )
}
