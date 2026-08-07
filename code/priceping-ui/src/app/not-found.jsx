import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="text-6xl">🔍</div>
      <div>
        <h1 className="font-display text-4xl font-bold text-slate-900">Page not found</h1>
        <p className="mt-2 text-slate-500">
          The page you're looking for doesn't exist or has been moved.
        </p>
      </div>
      <div className="flex gap-3">
        <Link href="/" className="btn-primary">
          Go to homepage
        </Link>
        <Link href="/dashboard" className="btn-outline">
          My dashboard
        </Link>
      </div>
    </div>
  )
}
