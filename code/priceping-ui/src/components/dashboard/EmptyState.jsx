import Link from 'next/link'

export default function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center px-4">
      <div className="text-6xl mb-4">🔔</div>
      <h3 className="text-xl font-semibold text-slate-700 mb-2">
        No items monitored yet
      </h3>
      <p className="text-slate-500 text-sm max-w-xs mb-6">
        Paste any Amazon or Flipkart product URL and we&apos;ll ping you when
        the price drops.
      </p>
      <Link href="/track" className="btn-primary">
        ➕ Monitor Your First Item
      </Link>
    </div>
  )
}
