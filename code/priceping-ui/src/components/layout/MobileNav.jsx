'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, PlusCircle, Tag, User } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/track',     label: 'Track',     icon: PlusCircle },
  { href: '/offers',    label: 'Offers',    icon: Tag },
  { href: '/profile',   label: 'Profile',   icon: User },
]

/**
 * MobileNav — sticky bottom navigation bar.
 * Visible only on mobile (hidden on md+).
 */
export default function MobileNav() {
  const pathname = usePathname()

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-100
                    bg-white md:hidden">
      <ul className="flex">
        {NAV_LINKS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href + '/')
          return (
            <li key={href} className="flex-1">
              <Link
                href={href}
                className={cn(
                  'flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium',
                  'transition-colors duration-150',
                  isActive ? 'text-primary-600' : 'text-slate-400'
                )}
              >
                <Icon
                  size={20}
                  className={isActive ? 'text-primary-600' : 'text-slate-400'}
                />
                {label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
