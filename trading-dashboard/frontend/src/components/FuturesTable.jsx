import React, { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown, Search, Info } from 'lucide-react'

// ─── COB colour coding ──────────────────────────────────────────────────────
// Green  = COB ≥ 9%  → Rich futures / great cash-and-carry arb
// Yellow = COB 7-9%  → Above RFR, decent carry
// Orange = COB 5-7%  → Near or below RFR  (futures slightly cheap)
// Red    = COB < 5%  → Cheap futures / expensive borrow / high short interest
function cobBadge(pct) {
  if (pct == null) return <span className="text-slate-500">—</span>
  let cls = 'badge '
  if (pct >= 9)       cls += 'bg-accent-green/15 text-accent-green'
  else if (pct >= 7)  cls += 'bg-yellow-500/15 text-yellow-400'
  else if (pct >= 5)  cls += 'bg-accent-orange/15 text-accent-orange'
  else                cls += 'bg-accent-red/15 text-accent-red'
  return <span className={cls}>{pct.toFixed(2)}%</span>
}

function vsRfrBadge(diff) {
  if (diff == null) return <span className="text-slate-500">—</span>
  const pos = diff >= 0
  return (
    <span className={`text-xs ${pos ? 'text-accent-green' : 'text-accent-orange'}`}>
      {pos ? '+' : ''}{diff.toFixed(2)}pp
    </span>
  )
}

function priceFmt(n) {
  if (n == null) return '—'
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// ─── Sort icon ───────────────────────────────────────────────────────────────
function SortIcon({ col, sortCol, sortDir }) {
  if (sortCol !== col) return <ChevronsUpDown size={11} className="text-slate-600 ml-1" />
  return sortDir === 'asc'
    ? <ChevronUp size={11} className="text-accent-blue ml-1" />
    : <ChevronDown size={11} className="text-accent-blue ml-1" />
}

// ─── Futures mini-cells ───────────────────────────────────────────────────────
function FutCell({ fut, labels }) {
  if (!fut) return <td className="td text-slate-600">—</td>
  const cob = fut.cob
  return (
    <td className="td">
      <div className="flex flex-col gap-0.5">
        <span className="text-slate-200 font-medium">{priceFmt(fut.last_price)}</span>
        <span className="text-slate-500 text-xs">{fut.expiry} · {fut.days_to_expiry}d</span>
        <div className="flex gap-1 items-center">
          {cobBadge(cob?.cob_pct)}
          {vsRfrBadge(cob?.cob_vs_rfr)}
        </div>
      </div>
    </td>
  )
}

// ─── Component ───────────────────────────────────────────────────────────────
export default function FuturesTable({ instruments = [], onSelect, showDividends = true }) {
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState('near_cob_pct')
  const [sortDir, setSortDir] = useState('desc')

  function toggleSort(col) {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return instruments.filter(i =>
      i.symbol.toLowerCase().includes(q) ||
      (i.name ?? '').toLowerCase().includes(q)
    )
  }, [instruments, search])

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol]
      if (av == null) av = sortDir === 'asc' ? Infinity : -Infinity
      if (bv == null) bv = sortDir === 'asc' ? Infinity : -Infinity
      return sortDir === 'asc' ? av - bv : bv - av
    })
  }, [filtered, sortCol, sortDir])

  function Th({ col, label }) {
    return (
      <th className="th" onClick={() => toggleSort(col)}>
        <span className="flex items-center">{label}<SortIcon col={col} sortCol={sortCol} sortDir={sortDir} /></span>
      </th>
    )
  }

  return (
    <div className="card">
      {/* Search */}
      <div className="p-3 border-b border-surface-border flex items-center gap-2">
        <Search size={13} className="text-slate-500" />
        <input
          className="bg-transparent outline-none text-slate-200 placeholder-slate-600 text-xs flex-1"
          placeholder="Search symbol…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <span className="text-slate-500 text-xs">{sorted.length} / {instruments.length}</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-card z-10">
            <tr>
              <th className="th w-28">Symbol</th>
              <Th col="spot" label="Spot ₹" />
              <Th col="change_pct" label="Chg %" />
              <th className="th">Near Future</th>
              <th className="th">Mid Future</th>
              <th className="th">Far Future</th>
              {showDividends && <th className="th">Dividends</th>}
              <Th col="near_cob_pct" label="Near COB" />
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={showDividends ? 8 : 7} className="td text-slate-500 py-8 text-center">
                  No data available
                </td>
              </tr>
            )}
            {sorted.map(inst => {
              const [near, mid, far] = inst.futures ?? []
              const divCount = (inst.dividends ?? []).length
              const nearDivs = near?.cob?.dividend_details ?? []

              return (
                <tr
                  key={inst.symbol}
                  className="tr-hover"
                  onClick={() => onSelect && onSelect(inst)}
                >
                  {/* Symbol */}
                  <td className="td">
                    <div className="flex flex-col">
                      <span className="font-semibold text-slate-100">{inst.symbol}</span>
                      {inst.name && <span className="text-slate-500 text-xs">{inst.name}</span>}
                    </div>
                  </td>

                  {/* Spot */}
                  <td className="td font-medium text-slate-200">
                    {priceFmt(inst.spot)}
                  </td>

                  {/* Change */}
                  <td className={`td font-medium ${(inst.change_pct ?? 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    {inst.change_pct != null
                      ? `${inst.change_pct >= 0 ? '+' : ''}${inst.change_pct.toFixed(2)}%`
                      : '—'}
                  </td>

                  {/* Futures cells */}
                  <FutCell fut={near} />
                  <FutCell fut={mid} />
                  <FutCell fut={far} />

                  {/* Dividends */}
                  {showDividends && (
                    <td className="td">
                      {divCount === 0 ? (
                        <span className="text-slate-600">—</span>
                      ) : (
                        <div className="flex flex-col gap-0.5">
                          {nearDivs.slice(0, 2).map((d, i) => (
                            <span key={i} className="text-accent-green text-xs">
                              ₹{d.amount} · ex {d.ex_date}
                            </span>
                          ))}
                          {nearDivs.length === 0 && divCount > 0 && (
                            <span className="text-slate-400 text-xs">{divCount} upcoming</span>
                          )}
                        </div>
                      )}
                    </td>
                  )}

                  {/* Near COB summary */}
                  <td className="td text-right">
                    <div className="flex flex-col items-end gap-0.5">
                      {cobBadge(inst.near_cob_pct)}
                      {near?.cob && vsRfrBadge(near.cob.cob_vs_rfr)}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="p-3 border-t border-surface-border flex flex-wrap gap-4 text-xs text-slate-500">
        <span>COB = Cost of Borrowing (implied annualised financing rate from futures)</span>
        <span className="flex gap-2">
          <span className="text-accent-green">≥9% rich</span>
          <span className="text-yellow-400">7-9%</span>
          <span className="text-accent-orange">5-7%</span>
          <span className="text-accent-red">&lt;5% cheap futures / exp borrow</span>
        </span>
      </div>
    </div>
  )
}
