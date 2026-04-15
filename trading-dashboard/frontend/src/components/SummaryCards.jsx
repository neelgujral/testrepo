import React from 'react'
import { TrendingUp, TrendingDown, Activity, DollarSign } from 'lucide-react'

function Stat({ label, value, sub, color = 'text-slate-200' }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-slate-500 text-xs">{label}</span>
      <span className={`text-lg font-semibold ${color}`}>{value ?? '—'}</span>
      {sub && <span className="text-slate-500 text-xs">{sub}</span>}
    </div>
  )
}

export default function SummaryCards({ summary, exchange }) {
  if (!summary) return null
  const data = summary[exchange?.toLowerCase()]
  if (!data) return null
  const rfr = summary.risk_free_rate_pct ?? 6.5

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
      <div className="card p-3">
        <Stat label="Instruments" value={data.count} sub={`${exchange} F&O`} />
      </div>
      <div className="card p-3">
        <Stat
          label="Avg COB"
          value={data.avg_cob != null ? `${data.avg_cob}%` : '—'}
          sub="annualised"
          color={
            data.avg_cob > rfr
              ? 'text-accent-green'
              : data.avg_cob < rfr
              ? 'text-accent-red'
              : 'text-slate-200'
          }
        />
      </div>
      <div className="card p-3">
        <Stat
          label="Max COB"
          value={data.max_cob != null ? `${data.max_cob}%` : '—'}
          sub="best carry"
          color="text-accent-green"
        />
      </div>
      <div className="card p-3">
        <Stat
          label="Min COB"
          value={data.min_cob != null ? `${data.min_cob}%` : '—'}
          sub="cheapest long"
          color="text-accent-blue"
        />
      </div>
      <div className="card p-3">
        <Stat
          label="Rich Futures"
          value={data.above_rfr}
          sub={`COB > ${rfr}% RFR`}
          color="text-accent-green"
        />
      </div>
      <div className="card p-3">
        <Stat
          label="Cheap Futures"
          value={data.below_rfr}
          sub={`COB < ${rfr}% RFR`}
          color="text-accent-orange"
        />
      </div>
    </div>
  )
}
