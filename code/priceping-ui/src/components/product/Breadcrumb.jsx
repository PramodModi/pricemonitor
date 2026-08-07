'use client'

import Link from 'next/link'
import { ChevronRight, ArrowLeft } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'

/**
 * Breadcrumb
 * Mounts below the Navbar on the product detail page.
 * Provides explicit navigation — no browser-back dependency.
 *
 * When userEmail is in store (came from dashboard), shows a
 * "← My Items" back link so the user never needs the browser back button.
 *
 * Props:
 *   productName  string  — full product name (last crumb, not a link)
 *   category     string | null — from product_metadata.category
 *   brand        string | null — from product_metadata.brand OR product.brand
 */
export default function Breadcrumb({ productName, category, brand }) {
  const { userEmail } = useAppStore()

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
        <span className="text-slate-700 font-medium line-clamp-1 max-w-[200px] sm:max-w-none">
          {productName}
        </span>
      </nav>

      {/* Back to dashboard — only shown for logged-in users */}
      {userEmail && (
        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-700 transition-colors font-medium"
        >
          <ArrowLeft size={14} />
          My Items
        </Link>
      )}
    </div>
  )
}
