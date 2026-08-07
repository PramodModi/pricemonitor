import Link from 'next/link'

/**
 * Footer — 3-column links + affiliate disclosure.
 * Phase 1, SSG. Static links only.
 *
 * Affiliate disclosure is legally required for Indian affiliate sites
 * using Amazon/Flipkart affiliate programs.
 */

const COLUMNS = [
  {
    heading: 'PricePing',
    links: [
      { label: 'How it works', href: '/#how-it-works' },
      { label: 'Dashboard',    href: '/dashboard' },
      { label: 'Track a price', href: '/track' },
      { label: 'Blog',         href: '/blog' },
    ],
  },
  {
    heading: 'Track prices on',
    links: [
      { label: 'Amazon India', href: '/offers?platform=amazon' },
      { label: 'Flipkart',     href: '/offers?platform=flipkart' },
      { label: 'Myntra',       href: '/offers?platform=myntra' },
      { label: 'Top deals today', href: '/offers' },
    ],
  }
]

export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="border-t border-slate-100 bg-white">
      <div className="container py-12">
        {/* Logo + tagline */}
        <div className="mb-10">
          <Link href="/" className="inline-flex items-center gap-2 font-display text-xl font-bold text-primary-700">
            <span>🔔</span> PricePing
          </Link>
          <p className="mt-1.5 text-sm text-slate-500 max-w-xs">
            Smart price monitoring for Amazon India, Flipkart, and Myntra.
          </p>
        </div>

        {/* Link columns */}
        <div className="grid gap-8 sm:grid-cols-2">
          {COLUMNS.map(({ heading, links }) => (
            <div key={heading}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                {heading}
              </h3>
              <ul className="space-y-2">
                {links.map(({ label, href }) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-sm text-slate-600 hover:text-primary-700 transition-colors"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col gap-2 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-400">
            © {year} PricePing · Prices updated every 4 hours
          </p>

        </div>
      </div>
    </footer>
  )
}
