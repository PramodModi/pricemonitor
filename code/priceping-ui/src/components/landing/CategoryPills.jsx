import Link from 'next/link'

/**
 * CategoryPills — horizontally scrollable row of category links.
 * Each pill links to /offers?category={slug}.
 * Phase 1: static list. Adding a new category = one new entry in CATEGORIES.
 */
const CATEGORIES = [
  { label: 'Mobiles',     slug: 'mobiles',     icon: '📱' },
  { label: 'Laptops',     slug: 'laptops',     icon: '💻' },
  { label: 'Audio',       slug: 'audio',       icon: '🎧' },
  { label: 'TVs',         slug: 'tvs',         icon: '📺' },
  { label: 'Fashion',     slug: 'fashion',     icon: '👕' },
  { label: 'Footwear',    slug: 'footwear',    icon: '👟' },
  { label: 'Appliances',  slug: 'appliances',  icon: '🏠' },
  { label: 'Watches',     slug: 'watches',     icon: '⌚' },
  { label: 'Cameras',     slug: 'cameras',     icon: '📷' },
  { label: 'Gaming',      slug: 'gaming',      icon: '🎮' },
]

export default function CategoryPills() {
  return (
    <section className="section-sm border-b border-slate-100">
      <div className="container">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
          Browse by category
        </p>
        {/* Scrollable row — hides scrollbar on all browsers */}
        <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1 -mb-1">
          {CATEGORIES.map(({ label, slug, icon }) => (
            <Link
              key={slug}
              href={`/offers?category=${slug}`}
              className="flex shrink-0 items-center gap-2 rounded-full border border-slate-200
                         bg-white px-4 py-2 text-sm font-medium text-slate-700
                         transition-all duration-150 hover:border-primary-300
                         hover:bg-primary-50 hover:text-primary-700 whitespace-nowrap"
            >
              <span className="text-base leading-none">{icon}</span>
              {label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
