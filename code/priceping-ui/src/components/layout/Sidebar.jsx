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
  
  { href: 'https://link.amazon/B03xA93Nr',
    label: 'Amazon offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer' 
  },
  { href: 'https://clnk.in/BYvg',
    label: 'Vijay Sales offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer' 
  },
  { href: 'https://clnk.in/BYvW',
    label: 'Reliance Digital offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer'
  },
  { href: 'https://crma.clnk.in/BYw0',
    label: 'Croma offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer'
  },
  { href: 'https://clnk.in/BYUI',
    label: 'Tata CliQ offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer'
  },
  { href: 'https://clnk.in/BYUO',
    label: 'pepperfry offers',
    icon: User, 
    target: '_blank',
    rel: 'noopener noreferrer'
  },
  
]

/**
 * Sidebar — fixed left column on desktop.
 * On mobile: becomes a slide-in drawer when isOpen = true.
 */
export default function Sidebar({ isOpen, onClose }) {
  const pathname   = usePathname()
  const userEmail  = useAppStore((state) => state.userEmail)

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
          // Desktop: fixed left sidebar
          'fixed top-0 left-0 z-40 flex h-screen w-[var(--sidebar-width)] flex-col',
          'border-r border-slate-100 bg-white',
          // Desktop: always visible
          'hidden md:flex',
          // Mobile: drawer that slides in
          isOpen && '!flex',
          // Mobile transition
          'transition-transform duration-200',
          !isOpen && 'md:translate-x-0 -translate-x-full',
          isOpen  && 'translate-x-0'
        )}
      >
        {/* Logo area */}
        <div className="flex h-[var(--navbar-height)] items-center justify-between px-5 border-b border-slate-100">
          <Link
            href="/"
            className="flex items-center gap-2 font-display text-xl font-bold text-primary-700"
            onClick={onClose}
          >
            <span className="text-2xl">🔔</span>
            PricePing
          </Link>
          {/* Close button — mobile only */}
          <button
            onClick={onClose}
            className="md:hidden text-slate-400 hover:text-slate-700 p-1"
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <ul className="space-y-1">
            {NAV_LINKS.map(({ href, label, icon: Icon, phase }) => {
              const isActive = href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(href + '/')
              // Phase 2 items — not yet functional, render as non-clickable
              if (phase === 2) {
                return (
                  <li key={href}>
                    <div className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm
                                    font-medium text-slate-400 cursor-not-allowed select-none">
                      <Icon size={18} className="text-slate-300" />
                      {label}
                      <span className="ml-auto rounded-full bg-slate-100 px-1.5 py-0.5
                                       text-[10px] font-medium text-slate-400">
                        Soon
                      </span>
                    </div>
                  </li>
                )
              }

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
        </nav>

        {/* User email at bottom */}
        {userEmail && (
          <div className="border-t border-slate-100 px-4 py-3">
            <p className="truncate text-xs text-slate-400">{userEmail}</p>
          </div>
        )}
      </aside>
    </>
  )
}
