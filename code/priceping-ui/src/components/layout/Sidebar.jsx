'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, LayoutDashboard, PlusCircle, Tag, User, X } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'

const NAV_LINKS = [
  { href: '/',          label: 'Home',       icon: Home },
  { href: '/dashboard', label: 'Dashboard',  icon: LayoutDashboard },
  { href: '/track',     label: 'Track Item', icon: PlusCircle },
  { href: '/offers',    label: 'Offers',     icon: Tag },
  { href: '/profile',   label: 'Profile',    icon: User },
]

const STORE_LINKS = [
  { label: 'Amazon India',    url: 'https://link.amazon/B0cuMTrYO'},
  { label: 'Flipkart',        url: 'http://dl.flipkart.com/dl/?affid=pramodkmo'},
  { label: 'Vijay Sales',     url: 'https://clnk.in/BYvg'},
  { label: 'Reliance Digital',url: 'https://clnk.in/BYvW'},
  { label: 'Croma',           url: 'https://crma.clnk.in/BYw0'},
  { label: 'Tata CliQ',       url: 'https://clnk.in/BYUI'},
  { label: 'pepperfry',       url: 'https://clnk.in/BYUO'},
  { label: 'Meesho',          url: 'https://www.meesho.com/'},
  { label: 'Myntra',          url: 'https://www.myntra.com/' },
]

export default function Sidebar({ isOpen, onClose }) {
  const pathname  = usePathname()
  const userEmail = useAppStore((state) => state.userEmail)

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed top-0 left-0 z-40 flex h-screen w-[var(--sidebar-width)] flex-col',
          'border-r border-slate-100 bg-white',
          'hidden md:flex',
          isOpen && '!flex',
          'transition-transform duration-200',
          !isOpen && 'md:translate-x-0 -translate-x-full',
          isOpen  && 'translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex h-[var(--navbar-height)] items-center justify-between px-5 border-b border-slate-100">
          <Link
            href="/"
            className="flex items-center gap-2 font-display text-xl font-bold text-primary-700"
            onClick={onClose}
          >
            <span className="text-2xl">🔔</span>
            PricePing
          </Link>
          <button
            onClick={onClose}
            className="md:hidden text-slate-400 hover:text-slate-700 p-1"
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">

          {/* Primary nav links */}
          <ul className="space-y-1">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive =
                href === '/'
                  ? pathname === '/'
                  : pathname === href || pathname.startsWith(href + '/')
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onClose}
                    className={cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium',
                      'transition-colors duration-150',
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    )}
                  >
                    <Icon size={18} className={isActive ? 'text-primary-600' : 'text-slate-400'} />
                    {label}
                  </Link>
                </li>
              )
            })}
          </ul>

          {/* Stores section */}
          <div className="mt-5 mb-2 px-3">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
              Stores
            </p>
          </div>

          <ul className="space-y-0.5">
            {STORE_LINKS.map(({ label, url }) => (
              <li key={label}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm
                             text-slate-500 hover:bg-slate-50 hover:text-slate-900
                             transition-colors duration-150"
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* User email */}
        {userEmail && (
          <div className="border-t border-slate-100 px-4 py-3">
            <p className="truncate text-xs text-slate-400">{userEmail}</p>
          </div>
        )}
      </aside>
    </>
  )
}
