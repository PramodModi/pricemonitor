'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

/**
 * ProductDescription
 * Left column, section ⑥.
 * Description paragraph + features bulleted list.
 * Hidden if both description and features are absent.
 *
 * Props:
 *   description  string | null
 *   features     string[] | null
 */
export default function ProductDescription({ description, features }) {
  const [isOpen, setIsOpen] = useState(false)
  const [showAllFeatures, setShowAllFeatures] = useState(false)

  const hasDescription = description && description.trim().length > 0
  const hasFeatures = features && features.length > 0

  if (!hasDescription && !hasFeatures) return null

  const FEATURES_PREVIEW = 6
  const visibleFeatures =
    hasFeatures && !showAllFeatures
      ? features.slice(0, FEATURES_PREVIEW)
      : features ?? []

  return (
    <section>
      {/* Clickable header */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between py-3 text-left group"
      >
        <h2 className="text-base font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors">
          Description &amp; Features
        </h2>
        {isOpen
          ? <ChevronUp size={18} className="text-slate-400 flex-shrink-0" />
          : <ChevronDown size={18} className="text-slate-400 flex-shrink-0" />
        }
      </button>

      {/* Collapsible content */}
      {isOpen && (
        <div className="card p-5 space-y-4 mt-1">
          {/* Description paragraph */}
          {hasDescription && (
            <p className="text-sm text-slate-700 leading-relaxed">{description}</p>
          )}

          {/* Features list */}
          {hasFeatures && (
            <div>
              {hasDescription && <hr className="border-slate-100 mb-4" />}
              <ul className="space-y-2">
                {visibleFeatures.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="text-indigo-500 mt-0.5 flex-shrink-0">•</span>
                    <span className="leading-snug">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* Show more / less toggle */}
              {features.length > FEATURES_PREVIEW && (
                <button
                  onClick={() => setShowAllFeatures((v) => !v)}
                  className="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 mt-3 transition-colors"
                >
                  {showAllFeatures ? (
                    <><ChevronUp size={15} />Show fewer features</>
                  ) : (
                    <><ChevronDown size={15} />Show all {features.length} features</>
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <hr className="border-slate-100 mt-3" />
    </section>
  )
}
