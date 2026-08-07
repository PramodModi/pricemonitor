/**
 * DealsPlaceholder — shown in Phase 1 where the live deals sections will appear.
 * Replaced by TopDeals + PopularProducts in Phase 2.
 */
export default function DealsPlaceholder() {
  return (
    <section className="section-sm">
      <div className="container">
        <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50
                        px-6 py-10 text-center">
          <div className="text-3xl mb-3">🏷️</div>
          <p className="font-display text-base font-semibold text-slate-500">
            Today's best deals will appear here
          </p>
          <p className="mt-1 text-sm text-slate-400">
            Deal sections go live as more products are tracked on PricePing.
          </p>
        </div>
      </div>
    </section>
  )
}
