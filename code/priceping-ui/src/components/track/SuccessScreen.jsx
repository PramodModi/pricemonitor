import Link from 'next/link'

/**
 * SuccessScreen — Step 3 of Track flow.
 * Shown after subscription is confirmed.
 *
 * Props:
 *   email       — the email that will receive alerts
 *   productId   — to navigate to product detail page
 *   productSlug — preferred over productId for URL
 *   onTrackAnother() — resets back to Step 1
 */
export default function SuccessScreen({ email, productId, productSlug, onTrackAnother }) {
  const productHref = productSlug
    ? `/products/${productSlug}`
    : productId
      ? `/products/${productId}`
      : null

  return (
    <div className="card p-8 text-center space-y-5 animate-slide-up">
      {/* Icon */}
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl
                       bg-green-100 text-3xl">
        ✅
      </div>

      {/* Heading */}
      <div>
        <h2 className="font-display text-xl font-semibold text-slate-900">
          You're now tracking this product!
        </h2>
        {email && (
          <p className="mt-2 text-sm text-slate-500">
            We'll email{' '}
            <span className="font-medium text-slate-700">{email}</span>{' '}
            the moment the price drops.
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        {productHref && (
          <Link href={productHref} className="btn-primary justify-center">
            View product details →
          </Link>
        )}
        <button onClick={onTrackAnother} className="btn-outline justify-center">
          Track another item
        </button>
        <Link href="/dashboard" className="btn-ghost justify-center text-slate-500">
          Go to my dashboard
        </Link>
      </div>
    </div>
  )
}
