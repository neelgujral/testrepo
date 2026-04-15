"""
Cost of Borrowing (COB) Calculator for Futures

Theory (Cost-of-Carry Model):
  F = (S - PV_div) * (1 + r)^(T/365)

Solving for r (the implied financing / borrow rate):
  r = (F / (S - PV_div))^(365/T) - 1

Interpretation:
  COB > RFR  →  Futures are RICH  →  Stock is cheap to borrow (easy to short)
  COB < RFR  →  Futures are CHEAP →  Stock is EXPENSIVE to borrow (high short demand,
                                      borrow cost depresses the futures premium)

For cash-and-carry arb (buy spot, sell futures):
  High COB is good — you earn more than the risk-free rate.
For leveraged longs via futures:
  Low COB is good — cheaper to hold.
"""

from datetime import date, timedelta
from typing import List, Dict, Optional


# RBI repo rate used as the Indian risk-free rate proxy
RISK_FREE_RATE = 0.065  # 6.5%


def pv_of_dividends(
    dividends: List[Dict],
    today: date,
    expiry: date,
    rfr: float = RISK_FREE_RATE,
) -> tuple[float, List[Dict]]:
    """
    Return (total_PV, list_of_qualifying_dividends).
    Only dividends whose ex-date falls in [today, expiry] are included.
    """
    total_pv = 0.0
    qualifying = []
    for div in dividends:
        ex = div.get("ex_date")
        amount = float(div.get("amount") or 0)
        if not ex or amount <= 0:
            continue
        # ex_date may be a date object or ISO string
        if isinstance(ex, str):
            try:
                from datetime import datetime
                ex = datetime.strptime(ex, "%Y-%m-%d").date()
            except ValueError:
                continue
        if today <= ex <= expiry:
            days = (ex - today).days
            pv = amount / ((1 + rfr) ** (days / 365))
            total_pv += pv
            qualifying.append({
                "ex_date": ex.isoformat(),
                "amount": round(amount, 4),
                "pv": round(pv, 4),
                "days_to_ex": days,
            })
    return round(total_pv, 4), qualifying


def calculate_cob(
    spot: float,
    futures_price: float,
    days_to_expiry: int,
    dividends: List[Dict],
    rfr: float = RISK_FREE_RATE,
) -> Optional[Dict]:
    """
    Compute all cost-of-carry metrics for one futures contract.

    Returns a dict with:
      cob_pct            – implied annualised financing rate (%)
      cob_vs_rfr         – COB minus risk-free rate (pp); positive = rich futures
      basis              – F - S
      basis_pct          – basis as % of spot
      annualised_basis   – basis_pct × (365 / T)
      pv_dividends       – present value of dividends to expiry
      fair_value         – theoretical futures price at RFR
      premium_to_fair    – F - fair_value  (positive = futures rich)
      premium_to_fair_pct
      dividend_details   – list of qualifying dividends
      days_to_expiry
    """
    if days_to_expiry <= 0 or spot <= 0 or futures_price <= 0:
        return None

    today = date.today()
    expiry = today + timedelta(days=days_to_expiry)
    T = days_to_expiry / 365.0

    total_pv_div, div_details = pv_of_dividends(dividends, today, expiry, rfr)

    adjusted_spot = spot - total_pv_div
    if adjusted_spot <= 0:
        return None

    # Implied COB
    cob = (futures_price / adjusted_spot) ** (1 / T) - 1

    # Fair value at risk-free rate
    fair_value = adjusted_spot * (1 + rfr) ** T

    basis = futures_price - spot
    basis_pct = (basis / spot) * 100
    annualised_basis = basis_pct * (365 / days_to_expiry)

    premium_to_fair = futures_price - fair_value
    premium_to_fair_pct = (premium_to_fair / fair_value) * 100

    return {
        "cob_pct": round(cob * 100, 2),
        "rfr_pct": round(rfr * 100, 2),
        "cob_vs_rfr": round((cob - rfr) * 100, 2),
        "basis": round(basis, 4),
        "basis_pct": round(basis_pct, 4),
        "annualised_basis": round(annualised_basis, 2),
        "pv_dividends": total_pv_div,
        "fair_value": round(fair_value, 4),
        "premium_to_fair": round(premium_to_fair, 4),
        "premium_to_fair_pct": round(premium_to_fair_pct, 4),
        "dividend_details": div_details,
        "days_to_expiry": days_to_expiry,
    }


def enrich_futures_with_cob(
    symbol: str,
    spot: float,
    futures_list: List[Dict],
    dividends: List[Dict],
) -> List[Dict]:
    """
    Attach COB metrics to each futures contract in futures_list.
    """
    enriched = []
    for fut in futures_list:
        dte = fut.get("days_to_expiry", 0)
        fp = fut.get("last_price", 0)
        cob_data = calculate_cob(spot, fp, dte, dividends)
        enriched.append({**fut, "cob": cob_data})
    return enriched
