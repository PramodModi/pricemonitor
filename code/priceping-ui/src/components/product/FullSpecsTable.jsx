'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

/**
 * FullSpecsTable
 * Left column, section ⑦.
 * Collapsible section — collapsed by default.
 * All specs from product_metadata.specs, displayed in a full-width table.
 * Hidden if specs are absent.
 *
 * In Phase 1, specs is a flat key-value dict.
 * Phase 2 may introduce grouped categories — this component handles both:
 *   Flat: { "RAM": "8GB", "Storage": "256GB" }
 *   Grouped: { "Display": { "Size": "6.1\"", "Type": "OLED" }, "Camera": { ... } }
 *
 * Props:
 *   specs  object | null — product_metadata.specs
 */
export default function FullSpecsTable({ specs }) {
  const [isOpen, setIsOpen] = useState(false)

  if (!specs || Object.keys(specs).length === 0) return null

  // Detect if grouped (values are objects) or flat (values are primitives)
  const entries = Object.entries(specs)
  const isGrouped = entries.some(([, v]) => v && typeof v === 'object' && !Array.isArray(v))

  // Total row count for the header badge
  const totalRows = isGrouped
    ? entries.reduce((sum, [, v]) => {
        return sum + (typeof v === 'object' && !Array.isArray(v)
          ? Object.keys(v).length
          : 1)
      }, 0)
    : entries.length

  return (
    <section id="full-specs">
      {/* Clickable header */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between py-3 text-left group"
      >
        <h2 className="text-base font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors">
          Full Specifications
          <span className="ml-2 text-sm font-normal text-slate-400">
            ({totalRows})
          </span>
        </h2>
        {isOpen
          ? <ChevronUp size={18} className="text-slate-400 flex-shrink-0" />
          : <ChevronDown size={18} className="text-slate-400 flex-shrink-0" />
        }
      </button>

      {/* Collapsible content */}
      {isOpen && (
        <div className="mt-1">
          {isGrouped ? (
            // Grouped mode: each top-level key is a category
            <div className="space-y-4">
              {entries.map(([category, categorySpecs]) => {
                const rows = typeof categorySpecs === 'object' && !Array.isArray(categorySpecs)
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
          ) : (
            // Flat mode: one table with all rows
            <div className="card overflow-hidden">
              <SpecRows rows={entries} />
            </div>
          )}
        </div>
      )}

      <hr className="border-slate-100 mt-3" />
    </section>
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
