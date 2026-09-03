"""Deterministic financial calculations. Values are stored in INR crore."""
from __future__ import annotations
from math import isfinite


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    result = float(numerator) / float(denominator)
    return round(result, 4) if isfinite(result) else None


def revenue_cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or start <= 0 or end < 0 or years <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 2)


def yoy_revenue_growth(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0:
        return None
    return round(((current / previous) - 1) * 100, 2)


def extract_2y_cagr(periods: list[dict]) -> float | None:
    annuals = [p for p in periods if p.get("period_type") in ("Annual", "FY")]
    if len(annuals) < 2:
        return None
        
    for i in range(len(annuals)):
        start = annuals[i]
        for j in range(i + 1, len(annuals)):
            end = annuals[j]
            try:
                start_year = int(str(start["period_end"])[:4])
                end_year = int(str(end["period_end"])[:4])
                if end_year - start_year == 2:
                    return revenue_cagr(start.get("revenue"), end.get("revenue"), 2)
            except (ValueError, TypeError):
                pass
    return None



def margin(value: float | None, revenue: float | None) -> float | None:
    ratio = safe_divide(value, revenue)
    return round(ratio * 100, 2) if ratio is not None else None


def roe(pat: float | None, equity: float | None) -> float | None:
    ratio = safe_divide(pat, equity)
    return round(ratio * 100, 2) if ratio is not None else None


def roce(ebit: float | None, total_debt: float | None, equity: float | None, cash: float | None) -> float | None:
    if None in (ebit, total_debt, equity, cash):
        return None
    capital_employed = total_debt + equity - cash
    ratio = safe_divide(ebit, capital_employed)
    return round(ratio * 100, 2) if ratio is not None else None


def debt_to_equity(total_debt: float | None, equity: float | None) -> float | None:
    return safe_divide(total_debt, equity)


def net_debt(total_debt: float | None, cash: float | None) -> float | None:
    if total_debt is None or cash is None:
        return None
    return round(total_debt - cash, 4)


def net_debt_to_ebitda(total_debt: float | None, cash: float | None, ebitda: float | None) -> float | None:
    nd = net_debt(total_debt, cash)
    return safe_divide(nd, ebitda)


def enterprise_value(market_cap: float | None, total_debt: float | None, cash: float | None) -> float | None:
    if None in (market_cap, total_debt, cash):
        return None
    return round(market_cap + total_debt - cash, 2)


def valuation_multiples(market_cap: float | None, debt: float | None, cash: float | None, revenue: float | None, ebitda: float | None, pat: float | None) -> dict:
    ev = enterprise_value(market_cap, debt, cash)
    return {
        "market_cap": round(market_cap, 2) if market_cap is not None else None,
        "enterprise_value": ev,
        "pe": safe_divide(market_cap, pat),
        "ps": safe_divide(market_cap, revenue),
        "ev_ebitda": safe_divide(ev, ebitda),
        "ev_sales": safe_divide(ev, revenue),
    }


def ipo_implied_market_cap(offer_price: float | None, post_issue_shares: int | None) -> float | None:
    if offer_price is None or post_issue_shares is None:
        return None
    return round((offer_price * post_issue_shares) / 10000000.0, 2)


def derive_post_issue_shares(pre_issue_shares: int | None, fresh_issue_shares: int | None) -> int | None:
    if pre_issue_shares is None or fresh_issue_shares is None:
        return None
    return pre_issue_shares + fresh_issue_shares


def premium_discount(company_multiple: float | None, peer_median: float | None) -> float | None:
    ratio = safe_divide((company_multiple or 0) - (peer_median or 0), peer_median)
    return round(ratio * 100, 2) if ratio is not None else None


import re

def parse_indian_number(raw: str | None) -> float | None:
    """Convert common Indian filing formats to INR crore; returns None for unavailable values."""
    if raw is None or str(raw).strip().lower() in ("", "-", "na", "n/a", "null", "none", "nil"):
        return None
        
    normalized = str(raw).lower().replace(",", "").replace("₹", "").replace("inr", "").strip()
    
    # Handle negative in parentheses (e.g. "(100)")
    is_negative = False
    if normalized.startswith("(") and normalized.endswith(")"):
        is_negative = True
        normalized = normalized[1:-1].strip()
    elif normalized.startswith("-"):
        is_negative = True
        normalized = normalized[1:].strip()
        
    multiplier = 1.0
    if "lakh" in normalized or "lac" in normalized:
        multiplier = 0.01
    elif "crore" in normalized or "cr" in normalized:
        multiplier = 1.0
    elif "million" in normalized or "mn" in normalized:
        multiplier = 0.1
    elif "billion" in normalized or "bn" in normalized:
        multiplier = 100.0
        
    match = re.search(r'([0-9]*\.?[0-9]+)', normalized)
    if not match:
        return None
        
    val = float(match.group(1)) * multiplier
    return round(-val if is_negative else val, 4)


from statistics import median

def calculate_peer_statistics(peer_metrics: list[dict]) -> dict:
    """Calculate median and observation counts for peer valuation multiples. Ignore NULLs."""
    stats = {}
    for key in ["pe", "ps", "ev_ebitda", "ev_sales"]:
        valid_vals = [m[key] for m in peer_metrics if m.get(key) is not None]
        if valid_vals:
            stats[key] = {
                "median": round(median(valid_vals), 2),
                "observations": len(valid_vals)
            }
        else:
            stats[key] = {
                "median": None,
                "observations": 0
            }
    return stats


def calculate_band_comparison(target_lower: dict, target_upper: dict, peer_stats: dict) -> dict:
    """Calculate premium/discount for lower and upper bands vs peer medians."""
    comparison = {"lower_band": {}, "upper_band": {}}
    for key in ["pe", "ps", "ev_ebitda", "ev_sales"]:
        peer_median = peer_stats.get(key, {}).get("median")
        comparison["lower_band"][key] = premium_discount(target_lower.get(key), peer_median)
        comparison["upper_band"][key] = premium_discount(target_upper.get(key), peer_median)
    return comparison
