export default function ProductCardSkeleton() {
  return (
    <div className="card flex gap-4 animate-pulse">
      {/* Image placeholder */}
      <div className="flex-shrink-0 w-[72px] h-[72px] rounded-lg skeleton" />

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-2.5">
        {/* Name lines */}
        <div className="skeleton h-3.5 w-3/4 rounded" />
        <div className="skeleton h-3.5 w-1/2 rounded" />

        {/* Badges */}
        <div className="flex gap-2">
          <div className="skeleton h-4 w-20 rounded-full" />
          <div className="skeleton h-4 w-14 rounded-full" />
        </div>

        {/* Price */}
        <div className="skeleton h-5 w-24 rounded" />

        {/* Bottom row */}
        <div className="flex justify-between">
          <div className="skeleton h-3 w-32 rounded" />
          <div className="skeleton h-5 w-5 rounded" />
        </div>
      </div>
    </div>
  )
}
