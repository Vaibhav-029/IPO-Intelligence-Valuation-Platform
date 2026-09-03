from __future__ import annotations
from typing import Any
import math

METHODOLOGY_VERSION = "v4.0"

# Explicit dimension weights
WEIGHTS = {
    "financial_quality": 0.20,
    "growth": 0.20,
    "valuation": 0.20,
    "balance_sheet": 0.15,
    "business_quality": 0.15,
    "risk": 0.10,
}

def normalize(value: float | None, lower_bound: float, upper_bound: float) -> float | None:
    """
    Normalizes a value to a 0-100 scale based on bounds.
    If value is None, returns None.
    If value is <= lower_bound (or >= for inverse bounds), returns 0.
    If value is >= upper_bound (or <= for inverse bounds), returns 100.
    """
    if value is None:
        return None
        
    value = float(value)
    
    if upper_bound > lower_bound:
        if value <= lower_bound: return 0.0
        if value >= upper_bound: return 100.0
        return round(((value - lower_bound) / (upper_bound - lower_bound)) * 100.0, 2)
    else:
        # Inverse mapping: lower_bound is actually the "worst" value (e.g. +50% premium) 
        # and upper_bound is the "best" (e.g. -50% discount)
        if value >= lower_bound: return 0.0
        if value <= upper_bound: return 100.0
        return round(((lower_bound - value) / (lower_bound - upper_bound)) * 100.0, 2)

def avg_valid(scores: list[float | None]) -> float | None:
    valid = [s for s in scores if s is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)

def score_financial_quality(ebitda_margin: float | None, pat_margin: float | None, roe: float | None, roce: float | None) -> dict:
    scores = {
        "ebitda_margin": normalize(ebitda_margin, 0, 30),
        "pat_margin": normalize(pat_margin, 0, 20),
        "roe": normalize(roe, 0, 25),
        "roce": normalize(roce, 0, 25)
    }
    dim_score = avg_valid(list(scores.values()))
    return {"score": dim_score, "sub_metrics": scores}

def score_growth(revenue_cagr: float | None, yoy_growth: float | None) -> dict:
    scores = {
        "revenue_cagr": normalize(revenue_cagr, 0, 40),
        "yoy_growth": normalize(yoy_growth, 0, 40)
    }
    dim_score = avg_valid(list(scores.values()))
    return {"score": dim_score, "sub_metrics": scores}

def score_valuation(pe_premium_discount: float | None) -> dict:
    # Valuation: lower is better. +50% premium -> 0, -50% discount -> 100
    # Note: lower_bound is 50, upper_bound is -50
    scores = {
        "pe_premium_discount": normalize(pe_premium_discount, 50, -50)
    }
    dim_score = avg_valid(list(scores.values()))
    return {"score": dim_score, "sub_metrics": scores}

def score_balance_sheet(debt_to_equity: float | None) -> dict:
    # Less leverage is better. 2.0x -> 0, 0.0x -> 100
    scores = {
        "debt_to_equity": normalize(debt_to_equity, 2.0, 0.0)
    }
    dim_score = avg_valid(list(scores.values()))
    return {"score": dim_score, "sub_metrics": scores}

def score_business_quality(manual_seed_score: float | None) -> dict:
    # Manual seed score is 0-10.
    val = None
    if manual_seed_score is not None:
        val = normalize(manual_seed_score, 0, 10)
    scores = {"manual_business_quality": val}
    return {"score": val, "sub_metrics": scores}

def score_risk(risk_factors: list[dict]) -> dict:
    if risk_factors is None or len(risk_factors) == 0:
        return {"score": None, "sub_metrics": {"risk_penalties": None}}
    
    penalties = 0
    for rf in risk_factors:
        sev = rf.get("severity", "").lower()
        if sev == "high": penalties += 20
        elif sev == "medium": penalties += 10
        elif sev == "low": penalties += 5
        
    score = max(0.0, 100.0 - penalties)
    return {"score": round(score, 2), "sub_metrics": {"risk_penalties": score}}

def calculate_overall_score(dimensions: dict) -> dict:
    total_weight = 0.0
    weighted_sum = 0.0
    coverage_details = {}
    
    for dim, weight in WEIGHTS.items():
        dim_data = dimensions.get(dim, {})
        val = dim_data.get("score")
        
        subs = dim_data.get("sub_metrics", {})
        total_subs = len(subs)
        avail_subs = len([v for v in subs.values() if v is not None])
        
        if val is not None:
            total_weight += weight
            weighted_sum += val * weight
            coverage_details[dim] = {"available": avail_subs, "total": total_subs, "sub_metrics": subs}
        else:
            reason = "manual assessment unavailable" if dim == "business_quality" else "not assessed" if dim == "risk" else "insufficient data"
            coverage_details[dim] = {"available": False, "reason": reason}
            
    if total_weight == 0:
        overall = None
    else:
        # Exact proportional redistribution
        overall = round(weighted_sum / total_weight, 2)
        
    coverage_details["overall_effective_weight"] = round(total_weight * 100, 2)
    return {"overall_score": overall, "coverage": coverage_details}

def generate_explanations(dimensions: dict) -> dict:
    explanations = {}
    for dim in WEIGHTS.keys():
        val = dimensions.get(dim, {}).get("score")
        if val is not None:
            subs = dimensions.get(dim, {}).get("sub_metrics", {})
            valid = [k for k, v in subs.items() if v is not None]
            explanations[dim] = f"Scored {val}/100 based on valid metrics: {', '.join(valid)}."
        else:
            explanations[dim] = "Not scored due to insufficient data."
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import IPO, FinancialPeriod, FinancialMetric, ValuationMetric, RiskFactor, Peer, IPOSCore
from app.analytics.financials import margin, roe, roce, extract_2y_cagr, yoy_revenue_growth, debt_to_equity
from app.main import valuation

def generate_ipo_score(db: Session, ipo_id: int, manual_business_quality: float | None = None) -> IPOSCore:
    ipo = db.get(IPO, ipo_id)
    if not ipo:
        raise ValueError("IPO not found")

    # 1. Financial Quality & Growth & Balance Sheet
    fm = None
    row = db.execute(
        select(FinancialPeriod, FinancialMetric)
        .join(FinancialMetric)
        .where(FinancialPeriod.company_id == ipo.company_id)
        .order_by(FinancialPeriod.period_end.desc())
        .limit(1)
    ).first()
    if row:
        _, fm = row
        
    all_fms_row = db.execute(
        select(FinancialPeriod, FinancialMetric)
        .join(FinancialMetric)
        .where(FinancialPeriod.company_id == ipo.company_id)
        .order_by(FinancialPeriod.period_end.desc())
    ).all()
    periods_for_cagr = [{"period_type": p.period_type, "period_end": p.period_end, "revenue": m.revenue} for p, m in all_fms_row]
    
    rev_cagr = extract_2y_cagr(periods_for_cagr)
    yoy_g = None
    if len(all_fms_row) >= 2:
        yoy_g = yoy_revenue_growth(all_fms_row[1][1].revenue, all_fms_row[0][1].revenue)

    if fm:
        eq = fm.equity
        debt = fm.total_debt
        cash = fm.cash
        rev = fm.revenue
        ebitda = fm.ebitda
        pat = fm.pat
        ebit = fm.ebitda # Using EBITDA as proxy for EBIT where missing
        
        ebitda_m = margin(ebitda, rev)
        pat_m = margin(pat, rev)
        r_oe = roe(pat, eq)
        r_oce = roce(ebit, debt, eq, cash)
        dte = debt_to_equity(debt, eq)
    else:
        ebitda_m, pat_m, r_oe, r_oce, dte = None, None, None, None, None

    fin_q = score_financial_quality(ebitda_m, pat_m, r_oe, r_oce)
    grw = score_growth(rev_cagr, yoy_g)
    bs = score_balance_sheet(dte)

    # 2. Valuation
    val_data = valuation(ipo_id, db)
    lower_band = val_data.get("IPO_AT_ISSUE", {}).get("lower_band", {})
    
    from app.main import peers as get_peers
    peers_data = get_peers(ipo_id, db)
    comp = peers_data.get("comparison", {}).get("lower_band", {})
    pe_prem = comp.get("pe")
    val_score = score_valuation(pe_prem)

    # 3. Business Quality
    bq_score = score_business_quality(manual_business_quality)

    # 4. Risk
    risks = db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == ipo_id)).all()
    risk_dicts = [{"severity": r.severity} for r in risks]
    rsk_score = score_risk(risk_dicts if risks else None)

    # Compile Overall
    dimensions = {
        "financial_quality": fin_q,
        "growth": grw,
        "valuation": val_score,
        "balance_sheet": bs,
        "business_quality": bq_score,
        "risk": rsk_score
    }
    
    overall_res = calculate_overall_score(dimensions)
    expls = generate_explanations(dimensions)
    
    existing = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    if existing:
        existing.financial_quality_score = fin_q.get("score")
        existing.growth_score = grw.get("score")
        existing.valuation_score = val_score.get("score")
        existing.balance_sheet_score = bs.get("score")
        existing.business_quality_score = bq_score.get("score")
        existing.risk_score = rsk_score.get("score")
        existing.overall_score = overall_res.get("overall_score")
        existing.methodology_version = METHODOLOGY_VERSION
        existing.coverage = overall_res.get("coverage")
        existing.explanations = expls
        return existing
    else:
        new_score = IPOSCore(
            ipo_id=ipo_id,
            financial_quality_score=fin_q.get("score"),
            growth_score=grw.get("score"),
            valuation_score=val_score.get("score"),
            balance_sheet_score=bs.get("score"),
            business_quality_score=bq_score.get("score"),
            risk_score=rsk_score.get("score"),
            overall_score=overall_res.get("overall_score"),
            methodology_version=METHODOLOGY_VERSION,
            coverage=overall_res.get("coverage"),
            explanations=expls
        )
        db.add(new_score)
        return new_score
