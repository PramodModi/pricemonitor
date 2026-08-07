'use client'

import { useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import { useProductHistory } from '@/hooks/useProductHistory'
import { formatPrice, formatDateShort, formatDateIST } from '@/lib/utils'

const PERIODS = [
  { label: '1M', value: '1m' },
  { label: '3M', value: '3m' },
  { label: '6M', value: '6m' },
  { label: 'All', value: 'all' },
]

/**
 * PriceHistoryChart
 * Left column, section ③.
 *
 * Props:
 *   productId   string — used to fetch history
 *   allTimeLow  number | null — draws reference line on chart
 */
export default function PriceHistoryChart({ productId, allTimeLow }) {
  const [period, setPeriod] = useState('3m')
  const { data: history, isLoading, isError } = useProductHistory(productId, period)

  // Sort by date ascending, use numeric timestamp for X axis
  const chartData = (history ?? [])
    .slice()
    .sort((a, b) => new Date(a.checked_at) - new Date(b.checked_at))
    .map((row) => ({
      ...row,
      timestamp: new Date(row.checked_at).getTime(),
      price: Number(row.price),
    }))

  // One tick per unique calendar day (IST) — placed at midnight UTC of each day.
  // This gives clean "5 Aug" labels without duplicates, while each data point
  // still has its own unique timestamp X position (matching Altair's behaviour).
  const dayTicks = [
    ...new Map(
      chartData.map((d) => {
        const ist = new Date(d.timestamp + 5.5 * 60 * 60 * 1000)  // shift to IST
        const dayKey = ist.toISOString().slice(0, 10)              // "YYYY-MM-DD"
        const dayStart = new Date(dayKey + 'T00:00:00Z').getTime() - 5.5 * 60 * 60 * 1000
        return [dayKey, dayStart]
      })
    ).values(),
  ]

  // Y-axis domain: pad 5% above/below min/max
  const prices = chartData.map((d) => d.price)
  const minPrice = prices.length ? Math.min(...prices) : 0
  const maxPrice = prices.length ? Math.max(...prices) : 100000
  const pad = (maxPrice - minPrice) * 0.08 || 5000
  const yDomain = [
    Math.floor((minPrice - pad) / 1000) * 1000,
    Math.ceil((maxPrice + pad) / 1000) * 1000,
  ]

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-slate-800">Price History</h2>

        {/* Period toggle */}
        <div className="flex items-center gap-0.5 bg-slate-100 rounded-lg p-0.5">
          {PERIODS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setPeriod(value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                period === value
                  ? 'bg-white text-indigo-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="card p-4">
        {/* Loading */}
        {isLoading && (
          <div className="h-[200px] flex items-center justify-center">
            <div className="skeleton h-[160px] w-full rounded-lg" />
          </div>
        )}

        {/* Error */}
        {isError && !isLoading && (
          <div className="h-[200px] flex items-center justify-center text-slate-400 text-sm">
            Could not load price history.
          </div>
        )}

        {/* Empty state — endpoint not yet built or no data yet */}
        {!isLoading && !isError && chartData.length === 0 && (
          <div className="h-[200px] flex flex-col items-center justify-center text-center gap-2">
            <div className="text-3xl">📈</div>
            <p className="text-sm font-medium text-slate-600">
              Price history coming soon
            </p>
            <p className="text-xs text-slate-400">
              We&apos;ll chart the full price trend as we collect more data.
            </p>
          </div>
        )}

        {/* Chart */}
        {!isLoading && !isError && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={chartData}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f1f5f9"
                vertical={false}
              />
              <XAxis
                dataKey="timestamp"
                type="number"
                scale="time"
                domain={['dataMin', 'dataMax']}
                ticks={dayTicks}
                tickFormatter={(ts) => formatDateShort(new Date(ts + 5.5 * 60 * 60 * 1000).toISOString())}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={yDomain}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                width={46}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: '#6366f1', strokeWidth: 1, strokeDasharray: '4 2' }}
              />
              {/* All-time low reference line */}
              {allTimeLow && (
                <ReferenceLine
                  y={allTimeLow}
                  stroke="#10b981"
                  strokeDasharray="4 3"
                  strokeWidth={1.5}
                  label={{
                    value: 'All-time low',
                    position: 'insideTopRight',
                    fontSize: 10,
                    fill: '#10b981',
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="price"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#6366f1', strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const row = payload[0].payload
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-md px-3 py-2 text-sm">
      <p className="text-slate-500 text-xs mb-0.5">{formatDateIST(row.checked_at)}</p>
      <p className="font-semibold text-slate-800">{formatPrice(row.price)}</p>
    </div>
  )
}
