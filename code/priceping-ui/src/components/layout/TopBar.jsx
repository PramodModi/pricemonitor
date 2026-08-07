'use client'

import { useRef, useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { Menu, LogOut } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'

const PAGE_TITLES = {
  '/dashboard': 'My Monitored Items',
  '/track':     'Track New Item',
  '/profile':   'My Profile',
  '/offers':    'Offers & Deals',
}

/**
 * TopBar — sticky header for all (app) pages.
 * Shows: hamburger (mobile), page title, user email dropdown (desktop).
 *
 * Email avatar opens a dropdown with "Switch email" option.
 * Clicking outside the dropdown closes it.
 */
export default function TopBar({ onMenuClick }) {
  const pathname     = usePathname()
  const userEmail    = useAppStore((state) => state.userEmail)
  const setUserEmail = useAppStore((state) => state.setUserEmail)
  const title        = PAGE_TITLES[pathname] ?? 'PricePing'

  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [dropdownOpen])

  return (
    <header className="sticky top-0 z-30 flex h-[var(--navbar-height)] items-center
                        justify-between border-b border-slate-100 bg-white px-4 md:px-6">
      {/* Left: hamburger (mobile) + title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="md:hidden text-slate-500 hover:text-slate-800 p-1 -ml-1"
          aria-label="Open navigation"
        >
          <Menu size={22} />
        </button>
        <h1 className="font-display text-lg font-semibold text-slate-900">{title}</h1>
      </div>

      {/* Right: user email dropdown (desktop) */}
      {userEmail && (
        <div ref={dropdownRef} className="relative hidden md:block">
          {/* Trigger button */}
          <button
            onClick={() => setDropdownOpen((o) => !o)}
            className="flex items-center gap-2 rounded-lg px-2 py-1
                       hover:bg-slate-50 transition-colors duration-150 group"
          >
            <div className="h-7 w-7 rounded-full bg-primary-100 flex items-center justify-center">
              <span className="text-xs font-bold text-primary-700">
                {userEmail.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="max-w-[180px] truncate text-sm text-slate-500 group-hover:text-slate-700">
              {userEmail}
            </span>
          </button>

          {/* Dropdown menu */}
          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1 w-52 rounded-xl border border-slate-100
                            bg-white shadow-lg py-1 z-50">
              {/* Email display */}
              <div className="px-3 py-2 border-b border-slate-100">
                <p className="text-xs text-slate-400 truncate">{userEmail}</p>
              </div>

              {/* Switch email */}
              <button
                onClick={() => {
                  setDropdownOpen(false)
                  setUserEmail(null)
                }}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-sm
                           text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <LogOut size={15} className="text-slate-400" />
                Switch email
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  )
}
