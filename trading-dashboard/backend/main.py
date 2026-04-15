"""
Trading Dashboard — FastAPI backend

Endpoints
---------
GET /api/health                       – liveness check
GET /api/nse/symbols                  – list of all NSE F&O symbols
GET /api/nse/instrument/{symbol}      – full data (spot + futures + dividends + COB)
GET /api/nse/dashboard                – all Nifty 50 instruments in one call
GET /api/mcx/dashboard                – all MCX instruments
GET /api/summary                      – cross-market summary stats
"""

import logging
import concurrent.futures
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from nse_client import NSEClient
from mcx_client import MCXClient
from cob_calculator import enrich_futures_with_cob

# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("dashboard")

app = FastAPI(title="Trading Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared client instances (they manage their own caches + sessions)
nse = NSEClient()
mcx = MCXClient()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_nse_instrument(symbol: str) -> Optional[dict]:
    """Fetch + enrich one NSE symbol. Returns None if data unavailable."""
    data = nse.get_instrument(symbol)
    if not data:
        return None
    enriched_futures = enrich_futures_with_cob(
        symbol=symbol,
        spot=data["spot"],
        futures_list=data["futures"],
        dividends=data["dividends"],
    )
    # Compute near-month COB for summary sorting
    near_cob = None
    if enriched_futures and enriched_futures[0].get("cob"):
        near_cob = enriched_futures[0]["cob"]["cob_pct"]

    return {
        "symbol": symbol,
        "exchange": "NSE",
        "spot": data["spot"],
        "change_pct": data.get("change_pct"),
        "week52_high": data.get("week52_high"),
        "week52_low": data.get("week52_low"),
        "futures": enriched_futures,
        "dividends": data["dividends"],
        "near_cob_pct": near_cob,
    }


def _build_mcx_instrument(inst: dict) -> dict:
    """Attach COB data to an MCX instrument (no dividends for commodities)."""
    spot = inst.get("spot")
    futures = inst.get("futures", [])
    if spot and spot > 0:
        enriched = enrich_futures_with_cob(
            symbol=inst["symbol"],
            spot=spot,
            futures_list=futures,
            dividends=[],  # No dividends for commodities
        )
    else:
        enriched = futures

    near_cob = None
    if enriched and enriched[0].get("cob"):
        near_cob = enriched[0]["cob"]["cob_pct"]

    return {
        **inst,
        "exchange": "MCX",
        "futures": enriched,
        "near_cob_pct": near_cob,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/nse/symbols")
def nse_symbols():
    return {"symbols": nse.get_nifty50_symbols()}


@app.get("/api/nse/instrument/{symbol}")
def nse_instrument(symbol: str):
    symbol = symbol.upper()
    result = _build_nse_instrument(symbol)
    if not result:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    return result


@app.get("/api/nse/dashboard")
def nse_dashboard(limit: int = 50):
    """
    Return all Nifty 50 instruments with COB data.
    Uses a thread-pool for parallel fetching to keep latency low.
    """
    symbols = nse.get_nifty50_symbols()[:limit]
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures_map = {pool.submit(_build_nse_instrument, s): s for s in symbols}
        for fut in concurrent.futures.as_completed(futures_map):
            try:
                result = fut.result(timeout=30)
                if result:
                    results.append(result)
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", futures_map[fut], exc)

    # Sort by near-month COB descending (best carry arb first)
    results.sort(
        key=lambda x: x.get("near_cob_pct") if x.get("near_cob_pct") is not None else -999,
        reverse=True,
    )
    return {"instruments": results, "count": len(results)}


@app.get("/api/mcx/dashboard")
def mcx_dashboard():
    instruments = mcx.get_all_instruments()
    enriched = [_build_mcx_instrument(i) for i in instruments]
    enriched.sort(
        key=lambda x: x.get("near_cob_pct") if x.get("near_cob_pct") is not None else -999,
        reverse=True,
    )
    return {"instruments": enriched, "count": len(enriched)}


@app.get("/api/summary")
def summary():
    """Quick overview stats for the dashboard header cards."""
    nse_data = nse_dashboard()["instruments"]
    mcx_data = mcx_dashboard()["instruments"]

    def cob_stats(instruments):
        cobs = [i["near_cob_pct"] for i in instruments if i.get("near_cob_pct") is not None]
        if not cobs:
            return {}
        return {
            "count": len(cobs),
            "avg_cob": round(sum(cobs) / len(cobs), 2),
            "max_cob": round(max(cobs), 2),
            "min_cob": round(min(cobs), 2),
            "above_rfr": sum(1 for c in cobs if c > 6.5),
            "below_rfr": sum(1 for c in cobs if c < 6.5),
        }

    return {
        "nse": cob_stats(nse_data),
        "mcx": cob_stats(mcx_data),
        "risk_free_rate_pct": 6.5,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
