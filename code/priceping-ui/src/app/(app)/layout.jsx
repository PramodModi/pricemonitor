import AppShell from '@/components/layout/AppShell'

/**
 * Layout for the (app) route group.
 * Wraps Dashboard, Track, and Profile pages in AppShell —
 * which renders the Sidebar, TopBar, and MobileNav.
 *
 * This file was missing, which is why the sidebar and topbar
 * were not appearing on any of the app pages.
 */
export default function AppLayout({ children }) {
  return <AppShell>{children}</AppShell>
}
