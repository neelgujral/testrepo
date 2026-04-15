"""
NSE India data fetcher.

Fetches from NSE's public (unofficial) JSON API with proper browser-like session
handling. All data is cached in-process for CACHE_TTL seconds to avoid hammering
NSE's servers and getting rate-limited.

Key endpoints used:
  /api/equity-stockIndices?index=NIFTY+50               – Nifty 50 constituents
  /api/equity-stockIndices?index=SECURITIES+IN+F%26O    – All F&O eligible stocks
  /api/quote-equity?symbol=RELIANCE                     – Live spot quote
  /api/quote-derivative?symbol=RELIANCE                 – Futures + options chain
  /api/corporates-corporateActions?index=equities&symbol=RELIANCE – Dividends
"""

import time
import logging
import threading
from datetime import date, datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
CACHE_TTL = 300  # 5 minutes

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# Nifty 50 symbols as a reliable fallback when the API is unavailable
NIFTY50_FALLBACK = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "ULTRACEMCO", "WIPRO", "ZOMATO",
]


class NSEClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()
        self._session_refreshed_at = 0.0
        self._refresh_session()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _refresh_session(self):
        """Visit NSE homepage to obtain required cookies."""
        try:
            self.session.get(NSE_BASE + "/", timeout=15)
            time.sleep(0.3)
            self.session.get(
                NSE_BASE + "/market-data/pre-open-market", timeout=10
            )
            self._session_refreshed_at = time.time()
            logger.info("NSE session initialised")
        except Exception as exc:
            logger.warning("NSE session init failed: %s", exc)

    def _ensure_session(self):
        if time.time() - self._session_refreshed_at > 900:  # 15 min
            self._refresh_session()

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict = None, retries: int = 3) -> Optional[dict]:
        self._ensure_session()
        url = NSE_BASE + path
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=20)
                if resp.status_code in (401, 403):
                    self._refresh_session()
                    time.sleep(1)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.JSONDecodeError:
                logger.warning("Non-JSON from %s", url)
                return None
            except Exception as exc:
                logger.warning("GET %s attempt %d failed: %s", url, attempt + 1, exc)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None

    def _cached_get(self, key: str, path: str, params: dict = None) -> Optional[dict]:
        with self._lock:
            if key in self._cache:
                data, ts = self._cache[key]
                if time.time() - ts < CACHE_TTL:
                    return data
        result = self._get(path, params)
        if result is not None:
            with self._lock:
                self._cache[key] = (result, time.time())
        return result

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_nifty50_symbols(self) -> List[str]:
        data = self._cached_get("nifty50", "/api/equity-stockIndices", {"index": "NIFTY 50"})
        if not data:
            return list(NIFTY50_FALLBACK)
        rows = data.get("data", [])
        # Row 0 is the index summary; actual stocks start at row 1
        symbols = [r["symbol"] for r in rows[1:] if "symbol" in r]
        return symbols or list(NIFTY50_FALLBACK)

    def get_fo_symbols(self) -> List[str]:
        """Return all securities eligible for F&O trading on NSE."""
        data = self._cached_get(
            "fo_sec",
            "/api/equity-stockIndices",
            {"index": "SECURITIES IN F&O"},
        )
        if not data:
            return []
        return [r["symbol"] for r in data.get("data", []) if "symbol" in r]

    def get_spot_price(self, symbol: str) -> Optional[float]:
        data = self._cached_get(
            f"eq_{symbol}", "/api/quote-equity", {"symbol": symbol}
        )
        if not data:
            return None
        try:
            raw = data["priceInfo"]["lastPrice"]
            return float(str(raw).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            return None

    def get_spot_quote(self, symbol: str) -> Optional[Dict]:
        """Return full spot quote dict (includes change%, 52w hi/lo, etc.)."""
        data = self._cached_get(
            f"eq_{symbol}", "/api/quote-equity", {"symbol": symbol}
        )
        if not data:
            return None
        pi = data.get("priceInfo", {})
        try:
            spot = float(str(pi.get("lastPrice", 0)).replace(",", ""))
            change_pct = float(pi.get("pChange", 0) or 0)
            week52_high = float(str(pi.get("weekHighLow", {}).get("max", 0)).replace(",", ""))
            week52_low = float(str(pi.get("weekHighLow", {}).get("min", 0)).replace(",", ""))
        except (TypeError, ValueError):
            return None
        return {
            "spot": spot,
            "change_pct": change_pct,
            "week52_high": week52_high,
            "week52_low": week52_low,
        }

    # ------------------------------------------------------------------
    # Futures chain
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(s: str) -> Optional[date]:
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    def get_futures_chain(self, symbol: str) -> List[Dict]:
        """Return list of futures contracts sorted by expiry (near → far)."""
        data = self._cached_get(
            f"deriv_{symbol}", "/api/quote-derivative", {"symbol": symbol}
        )
        if not data:
            return []
        today = date.today()
        futures = []
        for stock in data.get("stocks", []):
            meta = stock.get("metadata", {})
            itype = meta.get("instrumentType", "")
            if "FUT" not in itype.upper():
                continue
            expiry = self._parse_date(meta.get("expiryDate", ""))
            if not expiry or expiry < today:
                continue
            try:
                last_price = float(
                    str(meta.get("lastPrice") or meta.get("closePrice") or 0)
                    .replace(",", "")
                )
            except (TypeError, ValueError):
                continue
            if last_price <= 0:
                continue
            dte = (expiry - today).days
            futures.append({
                "expiry": expiry.isoformat(),
                "last_price": last_price,
                "days_to_expiry": dte,
                "open": _safe_float(meta.get("open")),
                "high": _safe_float(meta.get("high")),
                "low": _safe_float(meta.get("low")),
                "volume": _safe_float(meta.get("numberOfContractsTraded")),
                "oi": _safe_float(meta.get("openInterest")),
                "change_pct": _safe_float(meta.get("pChange")),
            })
        futures.sort(key=lambda x: x["expiry"])
        return futures

    # ------------------------------------------------------------------
    # Corporate actions / dividends
    # ------------------------------------------------------------------

    def get_dividends(self, symbol: str) -> List[Dict]:
        """
        Return upcoming dividends (ex-date >= today) for the given symbol.
        Each item: {ex_date (ISO str), amount (₹ per share), purpose}
        """
        data = self._cached_get(
            f"corp_{symbol}",
            "/api/corporates-corporateActions",
            {"index": "equities", "symbol": symbol},
        )
        if not data or not isinstance(data, list):
            return []
        today = date.today()
        dividends = []
        for action in data:
            purpose = (action.get("purpose") or "").upper()
            if "DIVIDEND" not in purpose:
                continue
            ex_date = self._parse_date(action.get("exDate", ""))
            if not ex_date or ex_date < today:
                continue
            try:
                amount = float(action.get("dividend") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                continue
            dividends.append({
                "ex_date": ex_date.isoformat(),
                "amount": amount,
                "purpose": action.get("purpose", ""),
                "record_date": action.get("recordDate", ""),
                "payment_date": action.get("paymentDate", ""),
            })
        return dividends

    # ------------------------------------------------------------------
    # Convenience: full instrument data
    # ------------------------------------------------------------------

    def get_instrument(self, symbol: str) -> Optional[Dict]:
        """
        Fetch spot quote, futures chain, and dividends for one symbol.
        Returns None if the symbol has no valid spot price.
        """
        quote = self.get_spot_quote(symbol)
        if not quote or quote["spot"] <= 0:
            return None
        futures = self.get_futures_chain(symbol)
        dividends = self.get_dividends(symbol)
        return {
            "symbol": symbol,
            **quote,
            "futures": futures,
            "dividends": dividends,
        }


def _safe_float(val) -> Optional[float]:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None
