"""Research service — tool-augmented LLM research for IPO analysis.

Architecture:
    1. Deterministic tool functions gather structured context (financials, valuation, peers, risks, scores, evidence)
    2. A system prompt injects all tool outputs as structured JSON
    3. The LLM explains and reasons about the pre-computed data
    4. If no LLM is available, falls back to deterministic template mode

The LLM NEVER calculates financial metrics — it only explains them.
"""
from __future__ import annotations

import json
import logging
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.providers import get_llm_provider
from app.analytics.financials import margin, premium_discount, revenue_cagr
from app.models import (
    Document,
    FinancialMetric,
    FinancialPeriod,
    IPO,
    IPOSCore,
    Peer,
    RiskFactor,
    Source,
    ValuationMetric,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# TOOL FUNCTIONS — deterministic, pre-computed
# These are the "structured tools" the research layer uses.
# Each returns a dict of facts the LLM can reference.
# ──────────────────────────────────────────────


def company_snapshot(db: Session, ipo: IPO) -> dict:
    """Gather company profile + latest financials."""
    rows = db.execute(
        select(FinancialPeriod, FinancialMetric)
        .join(FinancialMetric)
        .where(FinancialPeriod.company_id == ipo.company_id)
        .order_by(FinancialPeriod.period_end)
    ).all()
    latest = rows[-1][1] if rows else None
    valuation = db.scalar(
        select(ValuationMetric)
        .where(ValuationMetric.company_id == ipo.company_id)
        .order_by(ValuationMetric.date.desc())
    )

    financials_series = []
    for period, metric in rows:
        financials_series.append({
            "fiscal_year": period.fiscal_year,
            "revenue_crore": float(metric.revenue),
            "ebitda_crore": float(metric.ebitda),
            "pat_crore": float(metric.pat),
            "ebitda_margin_pct": margin(float(metric.ebitda), float(metric.revenue)),
            "pat_margin_pct": margin(float(metric.pat), float(metric.revenue)),
        })

    return {
        "company": ipo.company.name,
        "sector": ipo.company.sector,
        "description": ipo.company.description,
        "exchange": ipo.company.exchange,
        "ipo_status": ipo.status,
        "issue_size_crore": float(ipo.issue_size),
        "price_band": [float(ipo.price_low), float(ipo.price_high)],
        "financials_series": financials_series,
        "latest_revenue_crore": float(latest.revenue) if latest else None,
        "latest_ebitda_crore": float(latest.ebitda) if latest else None,
        "latest_pat_crore": float(latest.pat) if latest else None,
        "revenue_cagr_2y_pct": revenue_cagr(
            float(rows[0][1].revenue), float(rows[-1][1].revenue), len(rows) - 1
        ) if len(rows) > 1 else None,
        "ebitda_margin_pct": margin(float(latest.ebitda), float(latest.revenue)) if latest else None,
        "pe": valuation.pe if valuation else None,
        "ps": valuation.ps if valuation else None,
        "ev_ebitda": valuation.ev_ebitda if valuation else None,
        "market_cap_crore": float(valuation.market_cap) if valuation else None,
        "enterprise_value_crore": float(valuation.ev) if valuation else None,
    }


def peer_comparison(db: Session, company_id: int) -> dict:
    """Compare company's valuation multiples against sector peers."""
    peer_ids = db.scalars(
        select(Peer.peer_company_id).where(Peer.company_id == company_id, Peer.active == True)
    ).all()
    vals = (
        db.scalars(select(ValuationMetric).where(ValuationMetric.company_id.in_(peer_ids))).all()
        if peer_ids else []
    )
    target = db.scalar(
        select(ValuationMetric)
        .where(ValuationMetric.company_id == company_id)
        .order_by(ValuationMetric.date.desc())
    )
    median_pe = median([v.pe for v in vals if v.pe is not None]) if vals else None

    return {
        "peer_count": len(vals),
        "peer_median_pe": round(median_pe, 2) if median_pe else None,
        "company_pe": target.pe if target else None,
        "pe_premium_discount_pct": premium_discount(
            target.pe if target else None, median_pe
        ),
    }


def get_risks(db: Session, ipo_id: int) -> list[dict]:
    """Retrieve risk factors for the IPO."""
    risks = db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == ipo_id)).all()
    return [
        {"category": r.category, "severity": r.severity, "summary": r.summary, "source_page": r.source_page}
        for r in risks
    ]


def get_score(db: Session, ipo_id: int) -> dict | None:
    """Retrieve the IPO scorecard."""
    score = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    if not score:
        return None
    return {
        "overall_score": score.overall_score,
        "financial_quality": score.profitability_score,
        "growth": score.growth_score,
        "valuation": score.valuation_score,
        "balance_sheet": score.notes.get("balance_sheet_score"),
        "business_quality": score.business_score,
        "risk": score.risk_score,
        "methodology_version": score.methodology_version,
        "methodology": "Financial quality 20%, Growth 20%, Valuation 20%, Balance sheet 15%, Business quality 15%, Risk 10%.",
    }


def retrieve_evidence(db: Session, company_id: int, query: str, limit: int = 4) -> list[dict]:
    """Keyword-ranked retrieval from ingested filing documents."""
    terms = {word.lower() for word in query.split() if len(word) > 3}
    sources = db.scalars(
        select(Source).join_from(Source, Document).where(Document.company_id == company_id)
    ).all()
    ranked = sorted(sources, key=lambda s: sum(term in s.text.lower() for term in terms), reverse=True)
    return [
        {
            "document_id": source.document_id,
            "page": source.page,
            "section": source.section,
            "excerpt": source.text[:380],
            "confidence": source.confidence,
        }
        for source in ranked[:limit]
    ]


# ──────────────────────────────────────────────
# CONTEXT GATHERING — runs all tools, builds trace
# ──────────────────────────────────────────────


def _gather_context(db: Session, ipo: IPO, question: str) -> tuple[dict, list[str]]:
    """Run all research tools and return (context_dict, tool_trace)."""
    trace: list[str] = []

    # Always gather full context — let the LLM decide what's relevant
    trace.append("get_company_profile")
    snapshot = company_snapshot(db, ipo)

    trace.append("get_financial_series")
    # financials_series is already inside snapshot

    trace.append("compare_peers")
    peers = peer_comparison(db, ipo.company_id)

    trace.append("get_risk_factors")
    risks = get_risks(db, ipo.id)

    trace.append("get_ipo_score")
    score = get_score(db, ipo.id)

    trace.append("retrieve_filing_evidence")
    evidence = retrieve_evidence(db, ipo.company_id, question)

    context = {
        "company_profile": {
            "name": snapshot["company"],
            "sector": snapshot["sector"],
            "description": snapshot["description"],
            "exchange": snapshot["exchange"],
            "ipo_status": snapshot["ipo_status"],
            "issue_size_crore": snapshot["issue_size_crore"],
            "price_band_inr": snapshot["price_band"],
        },
        "financials": {
            "series": snapshot["financials_series"],
            "latest_revenue_crore": snapshot["latest_revenue_crore"],
            "latest_ebitda_crore": snapshot["latest_ebitda_crore"],
            "latest_pat_crore": snapshot["latest_pat_crore"],
            "revenue_cagr_2y_pct": snapshot["revenue_cagr_2y_pct"],
            "ebitda_margin_pct": snapshot["ebitda_margin_pct"],
        },
        "valuation": {
            "pe": snapshot["pe"],
            "ps": snapshot["ps"],
            "ev_ebitda": snapshot["ev_ebitda"],
            "market_cap_crore": snapshot["market_cap_crore"],
            "enterprise_value_crore": snapshot["enterprise_value_crore"],
        },
        "peer_comparison": peers,
        "risk_factors": risks,
        "ipo_score": score,
        "filing_evidence": evidence,
    }

    return context, trace


# ──────────────────────────────────────────────
# SYSTEM PROMPT — constrains the LLM
# ──────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a senior equity research analyst specializing in Indian IPOs.

## Your role
You answer investor research questions about {company_name} using ONLY the structured data provided below. You explain trends, compare metrics, assess risks, and provide analytical context.

## Critical rules
1. **NEVER calculate your own financial metrics.** All numbers below are pre-computed by deterministic financial engines. Use them exactly as provided.
2. **Reference specific numbers** from the data when making claims. For example: "Revenue grew at a {cagr}% CAGR" — not "Revenue grew quickly."
3. **If filing evidence is available**, reference it. State the document and page.
4. **If data is missing or unavailable**, say so explicitly. Never invent values.
5. **Be concise and analytical.** Write 2-4 focused paragraphs, not a wall of text.
6. **Tone**: Professional research note. Not financial advice.

## Structured data (pre-computed, deterministic)

{context_json}

## User question
{question}"""


def _build_system_prompt(context: dict, question: str) -> str:
    """Build the system prompt with injected tool outputs."""
    company_name = context["company_profile"]["name"]
    cagr = context["financials"].get("revenue_cagr_2y_pct", "N/A")

    # Serialize context as readable JSON for the LLM
    context_json = json.dumps(context, indent=2, default=str)

    return SYSTEM_PROMPT_TEMPLATE.format(
        company_name=company_name,
        cagr=cagr,
        context_json=context_json,
        question=question,
    )


# ──────────────────────────────────────────────
# DETERMINISTIC FALLBACK — existing keyword logic
# Used when no LLM provider is configured
# ──────────────────────────────────────────────


def _deterministic_fallback(context: dict, question: str) -> str:
    """Generate a template-based answer from structured context (no LLM needed)."""
    q = question.lower()
    facts: list[str] = []
    name = context["company_profile"]["name"]
    fin = context["financials"]
    val = context["valuation"]
    peers = context["peer_comparison"]
    score = context["ipo_score"]
    risks = context["risk_factors"]

    # Always include a profile line
    facts.append(
        f"{name} is a {context['company_profile']['sector']} company "
        f"with a ₹{context['company_profile']['issue_size_crore']} Cr IPO "
        f"(status: {context['company_profile']['ipo_status']})."
    )

    if any(term in q for term in ("valuation", "premium", "p/e", "peers", "expensive", "cheap")):
        facts.append(
            f"The P/E is {val.get('pe', 'N/A')}x versus a peer median of "
            f"{peers.get('peer_median_pe', 'N/A')}x "
            f"({peers.get('pe_premium_discount_pct', 'N/A')}% premium/discount)."
        )

    if any(term in q for term in ("growth", "revenue", "financial", "margin", "profit")):
        facts.append(
            f"Revenue CAGR is {fin.get('revenue_cagr_2y_pct', 'N/A')}% "
            f"and latest EBITDA margin is {fin.get('ebitda_margin_pct', 'N/A')}%."
        )

    if any(term in q for term in ("risk", "concern", "worry")):
        if risks:
            risk_summaries = "; ".join(r["summary"] for r in risks[:3])
            facts.append(f"Key risks: {risk_summaries}.")

    if "score" in q and score:
        facts.append(
            f"The IPO score is {score['overall_score']}/10 "
            f"(methodology {score['methodology_version']})."
        )

    if len(facts) == 1:
        # Only the profile line — add general guidance
        facts.append(
            "I can analyze valuation, financial trends, peer comparison, "
            "risk factors, and IPO scoring. Try asking a more specific question."
        )

    evidence = context.get("filing_evidence", [])
    if evidence:
        facts.append("Filing evidence is attached below for reference.")
    else:
        facts.append("No filing evidence is available; analysis is based on structured data only.")

    return " ".join(facts)


# ──────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────


def answer_question(db: Session, ipo: IPO, question: str) -> dict:
    """Answer a research question about an IPO.

    Flow:
        1. Gather all structured context (deterministic tools)
        2. Try to call the LLM with tool outputs as context
        3. If LLM unavailable or fails, fall back to deterministic mode
        4. Return answer + tool_trace + citations + confidence
    """
    # Step 1: Gather context from all tools
    context, trace = _gather_context(db, ipo, question)

    # Step 2: Try LLM
    llm = get_llm_provider()
    llm_used = False
    answer_text = ""

    if llm.is_available:
        system_prompt = _build_system_prompt(context, question)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        try:
            answer_text = llm.generate_sync(messages=messages)
            llm_used = bool(answer_text)  # empty string = failure
        except Exception as exc:
            logger.warning("LLM call failed, falling back to deterministic mode: %s", exc)

    # Step 3: Fallback if needed
    if not llm_used:
        answer_text = _deterministic_fallback(context, question)

    # Step 4: Build response (same shape the frontend already expects)
    citations = context.get("filing_evidence", [])

    return {
        "answer": answer_text,
        "key_metrics": {
            "company": context["company_profile"]["name"],
            "sector": context["company_profile"]["sector"],
            "issue_size_crore": context["company_profile"]["issue_size_crore"],
            "latest_revenue_crore": context["financials"]["latest_revenue_crore"],
            "latest_pat_crore": context["financials"]["latest_pat_crore"],
            "revenue_cagr_2y": context["financials"]["revenue_cagr_2y_pct"],
            "ebitda_margin": context["financials"]["ebitda_margin_pct"],
            "pe": context["valuation"]["pe"],
            "ps": context["valuation"]["ps"],
        },
        "claims": citations,
        "confidence": "high" if llm_used and citations else "medium" if llm_used else "low",
        "disclaimer": "Research support only, not financial advice.",
        "tool_trace": list(dict.fromkeys(trace)),
        "mode": "llm" if llm_used else "deterministic",
    }
