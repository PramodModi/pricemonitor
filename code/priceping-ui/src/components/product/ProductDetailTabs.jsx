'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

/**
 * ProductDetailTabs
 * Left column — replaces separate ProductDescription (⑥) and FullSpecsTable (⑦).
 *
 * Tab behaviour:
 *   Both sections have data → two tabs, user switches between them
 *   Only description/features → rendered directly, no tabs
 *   Only specs → rendered directly, no tabs
 *   Nothing → returns null
 *
 * Props:
 *   description  string | null
 *   features     string[] | null
 *   specs        object | null  — flat or grouped key-value dict
 */
export default function ProductDetailTabs({ description, features, specs }) {
  const [activeTab, setActiveTab]         = useState('description')
  const [showAllFeatures, setShowAllFeatures] = useState(false)

  const hasDescription = !!(description && description.trim().length > 0)
  const hasFeatures    = !!(features && features.length > 0)
  const hasSpecs       = !!(specs && Object.keys(specs).length > 0)
  const hasContent     = hasDescription || hasFeatures
  const showTabs       = hasContent && hasSpecs

  if (!hasContent && !hasSpecs) return null

  // ── Tab definitions (only built when both sides have data) ─────────────
  const tabs = [
    { id: 'description', label: 'Description & Features' },
    { id: 'specs',       label: 'Full Specifications'    },
  ]

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <section>
      {showTabs ? (
        // Both sections present — render tab headers
        <div className="flex border-b border-slate-200 mb-5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors
                ${activeTab === tab.id
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      ) : (
        // Single section — plain heading (Amazon/Myntra have no specs)
        <h2 className="text-base font-semibold text-slate-800 mb-4">
          {hasContent ? 'Description & Features' : 'Full Specifications'}
        </h2>
      )}

      {/* ── Description & Features ──────────────────────────────────────── */}
      {(!showTabs || activeTab === 'description') && hasContent && (
        <DescriptionContent
          description={description}
          features={features}
          hasDescription={hasDescription}
          hasFeatures={hasFeatures}
          showAllFeatures={showAllFeatures}
          setShowAllFeatures={setShowAllFeatures}
        />
      )}

      {/* ── Full Specifications ─────────────────────────────────────────── */}
      {(!showTabs || activeTab === 'specs') && hasSpecs && (
        <SpecsContent specs={specs} />
      )}
    </section>
  )
}

// ── Description + Features panel ────────────────────────────────────────────

const FEATURES_PREVIEW = 6

function DescriptionContent({
  description, features,
  hasDescription, hasFeatures,
  showAllFeatures, setShowAllFeatures,
}) {
  const visibleFeatures = showAllFeatures
    ? features ?? []
    : (features ?? []).slice(0, FEATURES_PREVIEW)

  return (
    <div className="card p-5 space-y-4">
      {hasDescription && (
        <p className="text-sm text-slate-700 leading-relaxed">{description}</p>
      )}

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
  )
}

// ── Full Specifications panel ────────────────────────────────────────────────

function SpecsContent({ specs }) {
  const entries  = Object.entries(specs)
  const isGrouped = entries.some(
    ([, v]) => v && typeof v === 'object' && !Array.isArray(v)
  )

  if (isGrouped) {
    return (
      <div className="space-y-4">
        {entries.map(([category, categorySpecs]) => {
          const rows =
            typeof categorySpecs === 'object' && !Array.isArray(categorySpecs)
              ? Object.entries(categorySpecs)
              : [[category, String(categorySpecs)]]
          return (
            <div key={category} className="card overflow-hidden">
              <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                <h3 className="text-sm font-semibold text-slate-700">{category}</h3>
              </div>
              <SpecRows rows={rows} />
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <SpecRows rows={entries} />
    </div>
  )
}

function SpecRows({ rows }) {
  return (
    <div className="divide-y divide-slate-50">
      {rows.map(([label, value], i) => (
        <div
          key={label}
          className={`flex px-4 py-3 gap-6 text-sm ${
            i % 2 === 0 ? 'bg-white' : 'bg-slate-50/60'
          }`}
        >
          <span className="text-slate-500 w-36 flex-shrink-0 capitalize leading-relaxed">
            {label}
          </span>
          <span className="text-slate-800 font-medium leading-relaxed">
            {Array.isArray(value) ? value.join(', ') : String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}
