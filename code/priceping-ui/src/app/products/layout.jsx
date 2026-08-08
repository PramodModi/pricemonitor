import Navbar from '@/components/landing/Navbar'

/**
 * Layout for /products/[id] pages.
 * Uses Navbar (public header) since product pages are publicly accessible
 * and not part of the authenticated AppShell.
 * Navbar already handles the user email avatar dropdown in State B.
 */
export default function ProductsLayout({ children }) {
  return (
    <>
      <Navbar />
      <main>{children}</main>
    </>
  )
}
