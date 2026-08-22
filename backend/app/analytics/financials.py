"""Deterministic financial calculations. Values are stored in INR crore."""
from __future__ import annotations
from math import isfinite


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    result = float(numerator) / float(denominator)
    return round(result, 4) if isfinite(result) else None


def revenue_cagr(start: float, end: float, years: int) -> float | None:
    if start <= 0 or end < 0 or years <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 2)


def margin(value: float, revenue: float) -> float | None:
    ratio = safe_divide(value, revenue)
    return round(ratio * 100, 2) if ratio is not None else None


def roe(pat: float, opening_equity: float, closing_equity: float) -> float | None:
    average_equity = (opening_equity + closing_equity) / 2
    ratio = safe_divide(pat, average_equity)
    return round(ratio * 100, 2) if ratio is not None else None


def roce(ebit: float, total_debt: float, equity: float, cash: float = 0) -> float | None:
    capital_employed = total_debt + equity - cash
    ratio = safe_divide(ebit, capital_employed)
    return round(ratio * 100, 2) if ratio is not None else None


def debt_to_equity(total_debt: float, equity: float) -> float | None:
    return safe_divide(total_debt, equity)


def enterprise_value(market_cap: float, total_debt: float, cash: float) -> float:
    return round(market_cap + total_debt - cash, 2)


def valuation_multiples(market_cap: float, debt: float, cash: float, revenue: float, ebitda: float, pat: float) -> dict:
    ev = enterprise_value(market_cap, debt, cash)
    return {
        "market_cap": round(market_cap, 2), "enterprise_value": ev,
        "pe": safe_divide(market_cap, pat), "ps": safe_divide(market_cap, revenue),
        "ev_ebitda": safe_divide(ev, ebitda), "ev_sales": safe_divide(ev, revenue),
    }


def premium_discount(company_multiple: float | None, peer_median: float | None) -> float | None:
    ratio = safe_divide((company_multiple or 0) - (peer_median or 0), peer_median)
    return round(ratio * 100, 2) if ratio is not None else None


def parse_indian_number(raw: str) -> float:
    """Convert common Indian filing formats to INR crore; caller retains raw value for audit."""
    normalized = raw.lower().replace(",", "").replace("₹", "").strip()
    multiplier = 1.0
    if "lakh" in normalized or "lac" in normalized:
        multiplier = 0.01
    elif "crore" in normalized or "cr" in normalized:
        multiplier = 1.0
    elif "million" in normalized or "mn" in normalized:
        multiplier = 0.1
    elif "billion" in normalized or "bn" in normalized:
        multiplier = 100.0
    token = normalized.split()[0]
    return round(float(token) * multiplier, 4)

