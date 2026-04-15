import React from 'react'
import { X, Calendar, IndianRupee } from 'lucide-react'

export default function DividendPanel({ instrument, onClose }) {
  if (!instrument) return null
  const divs = instrument.dividends ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="card w-full max-w-lg max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-border">
          <div>
            <h3 className="font-semibold text-slate-100">{instrument.symbol}</h3>
            <p className="text-xs text-slate-400">Upcoming dividends to futures expiry</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5">
            <X size={14} />
          </button>
        </div>

        {/* Spot */}
        <div className="px-4 py-3 bg-surface-hover/40 border-b border-surface-border">
          <div className="flex gap-8 text-xs">
            <div>
              <span className="text-slate-500">Spot </span>
              <span className="text-slate-100 font-semibold">
                ₹{instrument.spot?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Change </span>
              <span className={instrument.change_pct >= 0 ? 'text-accent-green' : 'text-accent-red'}>
                {instrument.change_pct >= 0 ? '+' : ''}{instrument.change_pct?.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* Futures COB table */}
        <div className="p-4 border-b border-surface-border overflow-x-auto">
          <p className="text-xs text-slate-400 mb-2 font-semibold uppercase tracking-wider">Futures Chain</p>
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="th text-left py-1">Expiry</th>
                <th className="th text-right py-1">Futures ₹</th>
                <th className="th text-right py-1">DTE</th>
                <th className="th text-right py-1">PV Div</th>
                <th className="th text-right py-1">COB %</th>
                <th className="th text-right py-1">vs RFR</th>
              </tr>
            </thead>
            <tbody>
              {(instrument.futures ?? []).map((f, i) => {
                const cob = f.cob
                const labels = ['Near', 'Mid', 'Far']
                return (
                  <tr key={i} className="tr-hover">
                    <td className="td py-1">
                      <span className="text-slate-400 text-xs mr-1">{labels[i] ?? ''}</span>
                      {f.expiry}
                    </td>
                    <td className="td py-1 text-right">
                      {f.last_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="td py-1 text-right text-slate-400">{f.days_to_expiry}d</td>
                    <td className="td py-1 text-right text-slate-300">
                      {cob ? `₹${cob.pv_dividends}` : '—'}
                    </td>
                    <td className={`td py-1 text-right font-semibold ${cobColor(cob?.cob_pct)}`}>
                      {cob ? `${cob.cob_pct}%` : '—'}
                    </td>
                    <td className={`td py-1 text-right ${(cob?.cob_vs_rfr ?? 0) >= 0 ? 'text-accent-green' : 'text-accent-orange'}`}>
                      {cob ? `${cob.cob_vs_rfr >= 0 ? '+' : ''}${cob.cob_vs_rfr}pp` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Dividends */}
        <div className="p-4 flex-1 overflow-y-auto">
          <p className="text-xs text-slate-400 mb-2 font-semibold uppercase tracking-wider">
            Dividends ({divs.length})
          </p>
          {divs.length === 0 ? (
            <p className="text-slate-500 text-xs">No upcoming dividends found.</p>
          ) : (
            <div className="space-y-2">
              {divs.map((d, i) => (
                <div key={i} className="bg-surface-hover/60 rounded p-2.5 flex items-start justify-between">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-200 text-xs font-medium">{d.purpose}</span>
                    <div className="flex gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <Calendar size={10} /> Ex: {d.ex_date}
                      </span>
                      {d.record_date && (
                        <span>Record: {d.record_date}</span>
                      )}
                    </div>
                  </div>
                  <span className="flex items-center gap-0.5 text-accent-green font-semibold text-sm">
                    <IndianRupee size={11} />{d.amount}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function cobColor(pct) {
  if (pct == null) return 'text-slate-400'
  if (pct >= 9)  return 'text-accent-green'
  if (pct >= 7)  return 'text-yellow-400'
  if (pct >= 5)  return 'text-accent-orange'
  return 'text-accent-red'
}
