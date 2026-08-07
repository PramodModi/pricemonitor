import Navbar               from '@/components/landing/Navbar'
import HeroSection          from '@/components/landing/HeroSection'
import HowItWorks           from '@/components/landing/HowItWorks'
import RecommendationPreview from '@/components/landing/RecommendationPreview'
import FooterCTA            from '@/components/landing/FooterCTA'
import Footer               from '@/components/landing/Footer'

/**
 * Landing page — priceping.in/
 * Phase: 1 (core) · Rendering: SSG
 *
 * Hidden for now (re-enable in Phase 2):
 *   TrustBar         — static stats (misleading before real data)
 *   CategoryPills    — browse by category (no category pages yet)
 *   DealsPlaceholder — placeholder for Phase 2 deals section
 *   BankOffersRow    — static bank offer cards
 *   StatsSection     — dark background stats section
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        <HeroSection />
        <HowItWorks />
        <RecommendationPreview />
        <FooterCTA />
      </main>
      <Footer />
    </div>
  )
}
