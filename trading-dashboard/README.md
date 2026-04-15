# Trading Dashboard — COB Analyser

A live web dashboard for analysing **Cost of Borrowing (COB)** across all
**Nifty 50** equities and **MCX** commodities.

---

## What it does

| Feature | Detail |
|---------|--------|
| **Spot prices** | Live from NSE / MCX |
| **Futures chain** | Near / Mid / Far month for every F&O instrument |
| **Dividends** | All upcoming ex-dates between today and each futures expiry |
| **COB %** | Implied annualised financing rate per futures contract |
| **vs RFR** | COB vs 6.5% RBI repo rate — positive = rich futures |

### Cost of Borrowing formula

```
F = (S − PV_dividends) × (1 + r)^(T/365)

r (COB) = (F / (S − PV_dividends))^(365/T) − 1
```

| COB range | Meaning |
|-----------|---------|
| ≥ 9% | Futures **rich** — excellent cash-and-carry opportunity |
| 7–9% | Above RFR, decent carry trade |
| 5–7% | Near / below RFR — futures slightly cheap |
| < 5% | Cheap futures — **expensive stock borrow** / high short interest |

---

## Quick start

```bash
chmod +x start.sh
./start.sh
```

Then open **http://localhost:5173**

### Manual start

**Backend (FastAPI)**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

**Frontend (React + Vite)**
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

---

## Architecture

```
trading-dashboard/
├── backend/
│   ├── main.py            FastAPI app — routes + orchestration
│   ├── nse_client.py      NSE India API client (session + caching)
│   ├── mcx_client.py      MCX website scraper + fallback catalogue
│   ├── cob_calculator.py  COB / cost-of-carry mathematics
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx              Main layout + tabs + auto-refresh
│       ├── api/client.js        fetch wrappers
│       └── components/
│           ├── FuturesTable.jsx Sortable / searchable instruments table
│           ├── DividendPanel.jsx Click-through detail modal
│           └── SummaryCards.jsx Top-level stats
└── start.sh               One-command launcher
```

## Data sources

- **NSE**: Unofficial public JSON API (nseindia.com). No API key required.
  Data is cached 5 minutes to stay within rate limits.
- **MCX**: Website scrape + official JSON endpoint where available.
  For production use, subscribe to MCX's official data feed.
- **Dividends**: NSE corporate-actions endpoint filtered to future ex-dates.
- **Risk-free rate**: 6.5% (RBI repo rate) — update `RISK_FREE_RATE` in
  `backend/cob_calculator.py` when the rate changes.

## Notes

- NSE's unofficial API requires browser-like session cookies. The client
  handles this automatically but may occasionally get a 401 — it retries.
- MCX scraping may break if MCX changes their website layout.
- For production / high-frequency use, replace these fetchers with a paid
  market data feed (Zerodha Kite, Upstox, Angel One, etc.).
