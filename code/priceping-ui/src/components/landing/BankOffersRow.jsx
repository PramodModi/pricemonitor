/**
 * BankOffersRow — horizontally scrollable bank offer cards.
 * Phase 1: static example cards (real data via GET /v1/coupons in Phase 2).
 * Hidden entirely if no offers are available.
 */

const OFFERS = [
  {
    bank: 'HDFC Bank',
    icon: '🏦',
    offer: '10% instant discount on HDFC Credit & Debit Cards',
    platforms: ['Amazon', 'Flipkart'],
    cap: 'Max ₹1,500',
  },
  {
    bank: 'SBI Card',
    icon: '🏦',
    offer: '5% cashback on SBI Credit Cards',
    platforms: ['Amazon'],
    cap: 'Max ₹750/month',
  },
  {
    bank: 'ICICI Bank',
    icon: '🏦',
    offer: '10% off on ICICI Bank Credit Cards',
    platforms: ['Flipkart'],
    cap: 'Max ₹1,250',
  },
  {
    bank: 'Axis Bank',
    icon: '🏦',
    offer: '5% unlimited cashback on Axis Ace Card',
    platforms: ['Amazon', 'Myntra'],
    cap: 'No cap',
  },
  {
    bank: 'Kotak Bank',
    icon: '🏦',
    offer: '7.5% off on Kotak Cards',
    platforms: ['Flipkart'],
    cap: 'Max ₹2,000',
  },
]

export default function BankOffersRow() {
  return (
    <section className="section-sm bg-white">
      <div className="container">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
              Bank offers
            </p>
            <h2 className="mt-0.5 font-display text-lg font-semibold text-slate-900">
              Save more with card discounts
            </h2>
          </div>
          <a
            href="/coupons"
            className="shrink-0 text-sm font-medium text-primary-600 hover:text-primary-800"
          >
            All offers →
          </a>
        </div>

        {/* Scrollable row */}
        <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-2 -mb-2">
          {OFFERS.map(({ bank, icon, offer, platforms, cap }) => (
            <div
              key={bank}
              className="flex w-64 shrink-0 flex-col gap-2 rounded-xl border border-slate-100
                         bg-slate-50 p-4 transition-shadow hover:shadow-card-md"
            >
              <div className="flex items-center gap-2">
                <span className="text-xl">{icon}</span>
                <span className="text-sm font-semibold text-slate-800">{bank}</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{offer}</p>
              <div className="flex flex-wrap items-center gap-1.5 mt-auto">
                {platforms.map((p) => (
                  <span
                    key={p}
                    className="rounded-full bg-white border border-slate-200 px-2 py-0.5
                               text-[10px] font-medium text-slate-500"
                  >
                    {p}
                  </span>
                ))}
                <span className="ml-auto text-[10px] font-medium text-primary-600">{cap}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
