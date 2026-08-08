import './globals.css'
import Providers from './providers'

/**
 * Root layout — Server Component (no 'use client').
 * Next.js 15 requirement: root layout must be a Server Component.
 * Client-side providers are isolated in providers.jsx.
 */
export const metadata = {
  title: 'PricePing — Smart Price Tracking for Amazon, Flipkart & Myntra',
  description:
    'Track product prices on Amazon India, Flipkart, and Myntra. Get email alerts the moment a price drops.',
  metadataBase: new URL('https://priceping.in'),
  icons: {
    icon: '/favicon.svg',
    apple: '/favicon.svg',
  },
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
