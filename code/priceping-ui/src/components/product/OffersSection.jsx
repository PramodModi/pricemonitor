'use client'

import { useState } from 'react'
import { Tag, ChevronDown, ChevronUp } from 'lucide-react'

/**
 * OffersSection
 * Left column, section ⑤.
 * Collapsible section — collapsed by default.
 * Click header to expand/collapse.
 *
 * Props:
 *   offers  array | null — from product.offers (v3.0 affiliate enrichment)
 */
export default function OffersSection({ offers }) {
  const [isOpen, setIsOpen] = useState(false)

  if (!offers || offers.length === 0) return null

  // Normalise: offers can be array of strings or array of objects
  const normalised = offers.map((o, i) => {
    if (typeof o === 'string') return { id: i, text: o }
    return {
      id: i,
      text: o.description ?? o.text ?? o.offer ?? JSON.stringify(o),
      bank: o.bank ?? o.card ?? null,
      expires: o.expires ?? o.expiry ?? null,
    }
  })

  return (
    <section>
      {/* Clickable header */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between py-3 text-left group"
      >
        <h2 className="text-base font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors">
          Bank Offers &amp; Coupons
          <span className="ml-2 text-sm font-normal text-slate-400">
            ({normalised.length})
          </span>
        </h2>
        {isOpen
          ? <ChevronUp size={18} className="text-slate-400 flex-shrink-0" />
          : <ChevronDown size={18} className="text-slate-400 flex-shrink-0" />
        }
      </button>

      {/* Collapsible content */}
      {isOpen && (
        <div className="space-y-2 mt-1">
          {normalised.map((offer) => (
            <div
              key={offer.id}
              className="flex items-start gap-3 p-3 rounded-xl bg-amber-50 border border-amber-100"
            >
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-amber-100 flex items-center justify-center mt-0.5">
                <Tag size={13} className="text-amber-600" />
              </div>
              <div className="flex-1 min-w-0">
                {offer.bank && (
                  <p className="text-xs font-semibold text-amber-800 mb-0.5">
                    {offer.bank}
                  </p>
                )}
                <p className="text-sm text-slate-700 leading-snug">{offer.text}</p>
                {offer.expires && (
                  <p className="text-[11px] text-slate-400 mt-1">
                    Expires: {offer.expires}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <hr className="border-slate-100 mt-3" />
    </section>
  )
}
