import React, { useState, useEffect, useCallback } from 'react'
import { RefreshCw, TrendingUp, AlertCircle, Wifi, WifiOff } from 'lucide-react'
import { api } from './api/client'
import SummaryCards from './components/SummaryCards'
import FuturesTable from './components/FuturesTable'
import DividendPanel from './components/DividendPanel'

const TABS = ['NSE', 'MCX']
const REFRESH_MS = 5 * 60 * 1000  // 5 minutes

export default function App() {
  const [tab, setTab] = useState('NSE')
  const [nseData, setNseData] = useState(null)
  const [mcxData, setMcxData] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [selected, setSelected] = useState(null)
  const [online, setOnline] = useState(true)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nse, mcx, sum] = await Promise.all([
        api.nseDashboard(50),
        api.mcxDashboard(),
        api.summary(),
      ])
      setNseData(nse)
      setMcxData(mcx)
      setSummary(sum)
      setLastUpdated(new Date())
      setOnline(true)
    } catch (err) {
      setError(err.message)
      setOnline(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, REFRESH_MS)
    return () => clearInterval(id)
  }, [fetchAll])

  const instruments = tab === 'NSE'
    ? (nseData?.instruments ?? [])
    : (mcxData?.instruments ?? [])

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="border-b border-surface-border px-4 py-3 flex items-center justify-between gap-4 sticky top-0 bg-surface z-20">
        <div className="flex items-center gap-3">
          <TrendingUp size={18} className="text-accent-blue" />
          <span className="font-semibold text-slate-100 text-sm tracking-wide">
            Trading Dashboard
          </span>
          <span className="text-slate-600 text-xs hidden sm:block">
            COB Analyser — Nifty &amp; MCX
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Connection status */}
          {online
            ? <Wifi size={13} className="text-accent-green" />
            : <WifiOff size={13} className="text-accent-red" />
          }

          {/* Last updated */}
          {lastUpdated && (
            <span className="text-slate-500 text-xs hidden sm:block">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}

          {/* Refresh */}
          <button
            className="btn-ghost flex items-center gap-1.5"
            onClick={fetchAll}
            disabled={loading}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            <span className="hidden sm:block">Refresh</span>
          </button>
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────────────────── */}
      <main className="flex-1 p-4 max-w-screen-2xl mx-auto w-full">
        {/* Error banner */}
        {error && (
          <div className="mb-4 flex items-center gap-2 p-3 bg-accent-red/10 border border-accent-red/30 rounded text-accent-red text-xs">
            <AlertCircle size={13} />
            <span>
              Backend unreachable: {error}. Make sure the FastAPI server is running on port 8000.
            </span>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b border-surface-border">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-xs font-semibold transition-colors border-b-2 -mb-px ${
                tab === t
                  ? 'border-accent-blue text-accent-blue'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {t === 'NSE' ? 'NSE Equities' : 'MCX Commodities'}
              {t === 'NSE' && nseData && (
                <span className="ml-2 badge bg-surface-hover text-slate-400">
                  {nseData.count}
                </span>
              )}
              {t === 'MCX' && mcxData && (
                <span className="ml-2 badge bg-surface-hover text-slate-400">
                  {mcxData.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Summary cards */}
        <SummaryCards summary={summary} exchange={tab} />

        {/* What is COB? — info strip */}
        <div className="mb-4 text-xs text-slate-500 leading-relaxed bg-surface-card border border-surface-border rounded p-3 flex gap-3">
          <span className="text-accent-blue shrink-0 font-semibold">What is COB?</span>
          <span>
            <b className="text-slate-300">Cost of Borrowing</b> is the annualised implied financing rate
            derived from futures pricing using the cost-of-carry model:
            <code className="text-accent-blue mx-1">F = (S − PV_div) × (1+r)^(T/365)</code>.
            A <b className="text-accent-green">high COB</b> means futures are <b>rich</b> — great for
            cash-and-carry (buy spot + sell futures) arb.
            A <b className="text-accent-orange">low COB</b> signals cheap futures / expensive stock borrow
            (high short demand). RFR = 6.5% (RBI repo).
            Click any row to see the full futures chain and dividends.
          </span>
        </div>

        {/* Table */}
        {loading && instruments.length === 0 ? (
          <div className="card p-12 text-center text-slate-500">
            <RefreshCw size={20} className="animate-spin mx-auto mb-3" />
            Fetching live market data from NSE &amp; MCX…
          </div>
        ) : (
          <FuturesTable
            instruments={instruments}
            onSelect={setSelected}
            showDividends={tab === 'NSE'}
          />
        )}
      </main>

      {/* ── Dividend / detail panel ──────────────────────────────────────── */}
      {selected && (
        <DividendPanel
          instrument={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-surface-border px-4 py-2 text-xs text-slate-600 flex justify-between">
        <span>Data: NSE India · MCX India · Refreshes every 5 min</span>
        <span>RFR: 6.5% (RBI repo rate)</span>
      </footer>
    </div>
  )
}
