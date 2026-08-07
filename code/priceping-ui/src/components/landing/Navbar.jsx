'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Menu, X, LayoutDashboard, PlusCircle, Lock, LogOut, ChevronDown } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'

const NAV_LINKS = [
  { href: '/offers',  label: 'Offers' },           // live — Phase 1
  { href: '/coupons', label: 'Coupons', phase: 2 },
  { href: '/blog',    label: 'Blog',    phase: 3 },
]

/**
 * Navbar — shared across Landing page and Product detail page.
 *
 * Right side states:
 *   State A — no email → "Track a price" CTA
 *   State B — email stored → avatar dropdown (My Items, Track new, Set password, Switch email)
 *   State C — JWT (future, DEF-003) → logout option added
 *
 * Nav links (Deals, Coupons, Blog) are disabled until Phase 2/3.
 */
export default function Navbar() {
  const userEmail    = useAppStore((state) => state.userEmail)
  const setUserEmail = useAppStore((state) => state.setUserEmail)
  const router = useRouter()

  const [drawerOpen,   setDrawerOpen]   = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [scrolled,     setScrolled]     = useState(false)

  const dropdownRef = useRef(null)

  // Shadow on scroll
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close drawer on resize to desktop
  useEffect(() => {
    const onResize = () => { if (window.innerWidth >= 768) setDrawerOpen(false) }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    if (dropdownOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [dropdownOpen])

  function handleSwitchEmail() {
    setDropdownOpen(false)
    setDrawerOpen(false)
    setUserEmail(null)
    router.push('/dashboard')
  }

  return (
    <>
      <header
        className={cn(
          'sticky top-0 z-40 w-full bg-white/95 backdrop-blur-sm',
          'border-b border-transparent transition-all duration-200',
          scrolled && 'border-slate-100 shadow-sm'
        )}
      >
        <div className="container flex h-[var(--navbar-height)] items-center justify-between">

          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2 font-display text-xl font-bold text-primary-700"
          >
            <span className="text-2xl">🔔</span>
            PricePing
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map(({ href, label, phase }) =>
              phase ? (
                <span
                  key={href}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300
                             cursor-not-allowed select-none"
                  title="Coming soon"
                >
                  {label}
                </span>
              ) : (
                <Link
                  key={href}
                  href={href}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600
                             hover:bg-slate-50 hover:text-slate-900 transition-colors"
                >
                  {label}
                </Link>
              )
            )}
          </nav>

          {/* Desktop right — State A or State B */}
          <div className="hidden md:flex items-center gap-3">

            {/* State A — no email */}
            {!userEmail && (
              <Link href="/track" className="btn-primary text-sm px-4 py-2">
                Track a price
              </Link>
            )}

            {/* State B — email stored, show avatar dropdown */}
            {userEmail && (
              <div ref={dropdownRef} className="relative">
                <button
                  onClick={() => setDropdownOpen((o) => !o)}
                  className="flex items-center gap-2 rounded-xl border border-slate-200
                             px-3 py-1.5 text-sm hover:bg-slate-50 transition-colors"
                >
                  <div className="h-6 w-6 rounded-full bg-primary-100 flex items-center justify-center">
                    <span className="text-[11px] font-bold text-primary-700">
                      {userEmail.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <span className="max-w-[140px] truncate text-slate-700 font-medium">
                    {userEmail.split('@')[0]}
                  </span>
                  <ChevronDown
                    size={14}
                    className={cn('text-slate-400 transition-transform duration-150',
                      dropdownOpen && 'rotate-180')}
                  />
                </button>

                {/* Dropdown */}
                {dropdownOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border
                                  border-slate-100 bg-white shadow-lg py-1 z-50">
                    {/* Email display */}
                    <div className="px-3 py-2 border-b border-slate-100">
                      <p className="text-xs text-slate-400 truncate">{userEmail}</p>
                    </div>

                    <Link
                      href="/dashboard"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-3 py-2.5 text-sm
                                 text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <LayoutDashboard size={15} className="text-slate-400" />
                      My Items
                    </Link>

                    <Link
                      href="/track"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-3 py-2.5 text-sm
                                 text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <PlusCircle size={15} className="text-slate-400" />
                      Track new item
                    </Link>

                    <Link
                      href="/profile"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-3 py-2.5 text-sm
                                 text-slate-700 hover:bg-slate-50 transition-colors border-t border-slate-100"
                    >
                      <Lock size={15} className="text-slate-400" />
                      <div>
                        <p>Set a password</p>
                        <p className="text-[11px] text-slate-400">Protect your dashboard</p>
                      </div>
                    </Link>

                    <button
                      onClick={handleSwitchEmail}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm
                                 text-slate-500 hover:bg-slate-50 transition-colors border-t border-slate-100"
                    >
                      <LogOut size={15} className="text-slate-400" />
                      Switch email
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Mobile: hamburger */}
          <button
            onClick={() => setDrawerOpen(true)}
            className="md:hidden p-2 text-slate-500 hover:text-slate-800"
            aria-label="Open navigation"
          >
            <Menu size={22} />
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      {drawerOpen && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/40 md:hidden"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 z-50 w-72 bg-white shadow-card-lg md:hidden
                          animate-fade-in flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <Link
                href="/"
                onClick={() => setDrawerOpen(false)}
                className="font-display text-lg font-bold text-primary-700"
              >
                🔔 PricePing
              </Link>
              <button
                onClick={() => setDrawerOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1"
              >
                <X size={20} />
              </button>
            </div>

            {/* Mobile nav links */}
            <nav className="p-4 space-y-1 border-b border-slate-100">
              {NAV_LINKS.map(({ href, label, phase }) =>
                phase ? (
                  <span
                    key={label}
                    className="flex items-center rounded-lg px-4 py-3 text-sm font-medium
                               text-slate-300 cursor-not-allowed select-none"
                  >
                    {label}
                    <span className="ml-auto text-[10px] text-slate-300">Soon</span>
                  </span>
                ) : (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setDrawerOpen(false)}
                    className="flex items-center rounded-lg px-4 py-3 text-sm font-medium
                               text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    {label}
                  </Link>
                )
              )}
            </nav>

            {/* Mobile user section */}
            <div className="flex-1 p-4 space-y-1">
              {!userEmail ? (
                <Link
                  href="/track"
                  onClick={() => setDrawerOpen(false)}
                  className="btn-primary w-full justify-center"
                >
                  Track a price
                </Link>
              ) : (
                <>
                  {/* Email identity */}
                  <div className="flex items-center gap-2 px-3 py-2 mb-2">
                    <div className="h-7 w-7 rounded-full bg-primary-100 flex items-center justify-center">
                      <span className="text-xs font-bold text-primary-700">
                        {userEmail.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <span className="text-sm text-slate-600 truncate">{userEmail}</span>
                  </div>

                  <Link
                    href="/dashboard"
                    onClick={() => setDrawerOpen(false)}
                    className="flex items-center gap-2.5 rounded-lg px-4 py-3 text-sm
                               font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <LayoutDashboard size={16} className="text-slate-400" />
                    My Items
                  </Link>

                  <Link
                    href="/track"
                    onClick={() => setDrawerOpen(false)}
                    className="flex items-center gap-2.5 rounded-lg px-4 py-3 text-sm
                               font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <PlusCircle size={16} className="text-slate-400" />
                    Track new item
                  </Link>

                  <Link
                    href="/profile"
                    onClick={() => setDrawerOpen(false)}
                    className="flex items-center gap-2.5 rounded-lg px-4 py-3 text-sm
                               font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <Lock size={16} className="text-slate-400" />
                    Set a password
                  </Link>

                  <button
                    onClick={handleSwitchEmail}
                    className="flex w-full items-center gap-2.5 rounded-lg px-4 py-3 text-sm
                               font-medium text-slate-500 hover:bg-slate-50 transition-colors"
                  >
                    <LogOut size={16} className="text-slate-400" />
                    Switch email
                  </button>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}
