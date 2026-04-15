"""
MCX (Multi Commodity Exchange) data fetcher.

MCX does not publish a public REST API. This module scrapes the MCX website
commodity futures page and falls back to a hardcoded instrument catalogue
(with null prices) so the frontend always has a complete list to display.

Spot prices for physical commodities are sourced from MCX's own
market-data pages where available.

MCX expiry conventions used for reference:
  Gold / Silver    – last trading day before the 5th of the delivery month
  Crude Oil        – 19th (or prev business day) of the delivery month
  Copper / Zinc /
  Lead / Aluminium – last day of the delivery month
  Natural Gas      – 25th (or prev) of the delivery month
"""

import logging
import time
import threading
from datetime import date, datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
MCX_BASE = "https://www.mcxindia.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.mcxindia.com/",
}

# Master list of tradeable MCX commodities with their Yahoo Finance tickers
# (used as fallback when MCX website scraping fails)
MCX_INSTRUMENTS = [
    {"symbol": "GOLD",     "name": "Gold",          "unit": "10 grams", "lot_size": 1,   "category": "Precious Metals"},
    {"symbol": "GOLDM",    "name": "Gold Mini",     "unit": "10 grams", "lot_size": 1,   "category": "Precious Metals"},
    {"symbol": "SILVER",   "name": "Silver",        "unit": "1 kg",     "lot_size": 30,  "category": "Precious Metals"},
    {"symbol": "SILVERM",  "name": "Silver Mini",   "unit": "1 kg",     "lot_size": 5,   "category": "Precious Metals"},
    {"symbol": "CRUDEOIL", "name": "Crude Oil",     "unit": "1 barrel", "lot_size": 100, "category": "Energy"},
    {"symbol": "CRUDEOILM","name": "Crude Oil Mini","unit": "1 barrel", "lot_size": 10,  "category": "Energy"},
    {"symbol": "NATURALGAS","name": "Natural Gas",  "unit": "mmBtu",    "lot_size": 1250,"category": "Energy"},
    {"symbol": "COPPER",   "name": "Copper",        "unit": "1 kg",     "lot_size": 2500,"category": "Base Metals"},
    {"symbol": "ZINC",     "name": "Zinc",          "unit": "1 kg",     "lot_size": 5000,"category": "Base Metals"},
    {"symbol": "LEAD",     "name": "Lead",          "unit": "1 kg",     "lot_size": 5000,"category": "Base Metals"},
    {"symbol": "ALUMINIUM","name": "Aluminium",     "unit": "1 kg",     "lot_size": 5000,"category": "Base Metals"},
    {"symbol": "NICKEL",   "name": "Nickel",        "unit": "1 kg",     "lot_size": 1500,"category": "Base Metals"},
    {"symbol": "COTTON",   "name": "Cotton",        "unit": "1 bale",   "lot_size": 25,  "category": "Agri"},
    {"symbol": "MENTHAOIL","name": "Mentha Oil",    "unit": "1 kg",     "lot_size": 360, "category": "Agri"},
    {"symbol": "CASTORSEED","name": "Castor Seed",  "unit": "1 quintal","lot_size": 100, "category": "Agri"},
]


class MCXClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cached(self, key: str, fetch_fn):
        with self._lock:
            if key in self._cache:
                data, ts = self._cache[key]
                if time.time() - ts < CACHE_TTL:
                    return data
        result = fetch_fn()
        with self._lock:
            self._cache[key] = (result, time.time())
        return result

    def _get_html(self, path: str, timeout: int = 15) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(MCX_BASE + path, timeout=timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            logger.warning("MCX HTML fetch %s failed: %s", path, exc)
            return None

    def _get_json(self, path: str, timeout: int = 15) -> Optional[dict]:
        try:
            resp = self.session.get(MCX_BASE + path, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("MCX JSON fetch %s failed: %s", path, exc)
            return None

    # ------------------------------------------------------------------
    # Live price scraping
    # ------------------------------------------------------------------

    def _scrape_live_prices(self) -> Dict[str, Dict]:
        """
        Scrape MCX commodity-wise futures page.
        Returns {symbol: {near_price, near_expiry, mid_price, ...}}
        """
        soup = self._get_html("/market-data/commodity-wise-futures")
        if not soup:
            return {}
        results = {}
        try:
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cols = [c.get_text(strip=True) for c in row.find_all("td")]
                    if len(cols) < 4:
                        continue
                    symbol = cols[0].upper().replace(" ", "")
                    try:
                        price = float(cols[1].replace(",", ""))
                    except (ValueError, IndexError):
                        continue
                    results[symbol] = {
                        "near_price": price,
                        "near_expiry": cols[2] if len(cols) > 2 else "",
                        "change_pct": _safe_float(cols[3]) if len(cols) > 3 else None,
                    }
        except Exception as exc:
            logger.warning("MCX scrape parse error: %s", exc)
        return results

    def get_live_prices(self) -> Dict[str, Dict]:
        return self._cached("mcx_live", self._scrape_live_prices)

    # ------------------------------------------------------------------
    # Futures chain via MCX API (undocumented but publicly accessible)
    # ------------------------------------------------------------------

    def _fetch_commodity_futures(self, symbol: str) -> List[Dict]:
        """
        Try MCX's commodity detail page to get futures contracts.
        Falls back to empty list.
        """
        today = date.today()
        data = self._get_json(
            f"/apiservices/sitemap/GetContractDetails?commodityCode={symbol}"
        )
        futures = []
        if data and isinstance(data, list):
            for item in data:
                try:
                    expiry = datetime.strptime(
                        item.get("ExpiryDate", ""), "%d %b %Y"
                    ).date()
                    if expiry < today:
                        continue
                    price = float(item.get("LastPrice") or item.get("ClosePrice") or 0)
                    if price <= 0:
                        continue
                    futures.append({
                        "expiry": expiry.isoformat(),
                        "last_price": price,
                        "days_to_expiry": (expiry - today).days,
                        "open": _safe_float(item.get("OpenPrice")),
                        "high": _safe_float(item.get("HighPrice")),
                        "low": _safe_float(item.get("LowPrice")),
                        "volume": _safe_float(item.get("Volume")),
                        "oi": _safe_float(item.get("OpenInterest")),
                        "change_pct": _safe_float(item.get("PriceChange")),
                    })
                except (TypeError, ValueError, KeyError):
                    continue
            futures.sort(key=lambda x: x["expiry"])
        return futures

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_all_instruments(self) -> List[Dict]:
        """
        Return all MCX instruments with latest prices and futures chains.
        """
        live = self.get_live_prices()
        results = []
        for inst in MCX_INSTRUMENTS:
            sym = inst["symbol"]
            live_data = live.get(sym, {})

            # Spot / near-month price
            spot = live_data.get("near_price")

            # Try to get full futures chain from MCX API
            futures = self._cached(
                f"mcx_fut_{sym}",
                lambda s=sym: self._fetch_commodity_futures(s),
            )

            # If API gives no futures, construct a synthetic entry from scraped price
            if not futures and spot:
                near_exp = live_data.get("near_expiry", "")
                futures = [{
                    "expiry": near_exp,
                    "last_price": spot,
                    "days_to_expiry": _days_to_expiry_approx(near_exp),
                    "open": None,
                    "high": None,
                    "low": None,
                    "volume": None,
                    "oi": None,
                    "change_pct": live_data.get("change_pct"),
                }]

            results.append({
                **inst,
                "spot": spot,
                "change_pct": live_data.get("change_pct"),
                "futures": futures,
                # MCX commodities don't have equity dividends
                "dividends": [],
            })
        return results


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _days_to_expiry_approx(expiry_str: str) -> int:
    """Best-effort parse of expiry string to days from today."""
    today = date.today()
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            exp = datetime.strptime(expiry_str, fmt).date()
            return max(0, (exp - today).days)
        except (ValueError, TypeError):
            continue
    return 30  # default assumption
