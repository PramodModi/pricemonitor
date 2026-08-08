'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ChevronRight, ArrowLeft } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'

/**
 * Breadcrumb
 * Mounts below the Navbar on the product detail page.
 *
 * Back link logic:
 *   - Came from /dashboard → "← My Items"
 *   - Came from /offers or anywhere else → "← Offers"
 *   - userEmail not set → "← Offers" (no dashboard link)
 *
 * Props:
 *   productName  string        — full product name (last crumb, not a link)
 *   category     string | null — from product_metadata.category
 *   brand        string | null — from product_metadata.brand OR product.brand
 */
export default function Breadcrumb({ productName, category, brand }) {
  const { userEmail } = useAppStore()

  const searchParams = useSearchParams()
  const from = searchParams.get('from')

  const backHref  = (userEmail && from === 'dashboard') ? '/dashboard' : '/offers'
  const backLabel = (userEmail && from === 'dashboard') ? 'My Items'   : 'Offers'

  const crumbs = [
    { label: 'Home', href: '/' },
    category
      ? { label: category, href: `/offers?category=${encodeURIComponent(category.toLowerCase())}` }
      : null,
    brand
      ? { label: brand, href: `/offers?brand=${encodeURIComponent(brand.toLowerCase())}` }
      : null,
  ].filter(Boolean)

  return (
    <div className="flex items-center justify-between flex-wrap gap-2">

      {/* Main breadcrumb trail */}
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1 text-sm text-slate-500 flex-wrap"
      >
        {crumbs.map((crumb) => (
          <span key={crumb.href} className="flex items-center gap-1">
            <Link
              href={crumb.href}
              className="hover:text-indigo-600 transition-colors truncate max-w-[120px]"
            >
              {crumb.label}
            </Link>
            <ChevronRight size={13} className="text-slate-300 flex-shrink-0" />
          </span>
        ))}
        {/* Current page — not a link */}
        <span className="text-slate-700 font-medium line-clamp-1 max-w-[160px] sm:max-w-[320px]">
          {productName}
        </span>
      </nav>

      {/* Single back link — contextual */}
      <Link
        href={backHref}
        className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-700 transition-colors font-medium"
      >
        <ArrowLeft size={14} />
        {backLabel}
      </Link>

    </div>
  )
}
