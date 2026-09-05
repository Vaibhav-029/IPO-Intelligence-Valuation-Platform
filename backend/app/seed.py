"""
Seed the database with real Indian IPO company data.

WHY THIS FILE EXISTS
--------------------
Instead of hardcoding company data in Python (the old approach), we now
read from `backend/data/ipo_companies.json`. This follows a core engineering
principle: separate DATA from LOGIC.

- Data lives in a JSON file → easy to update, review, and version-control.
- Logic lives here → reads the file, validates it, and inserts into the DB.

HOW THE SCORING WORKS
---------------------
Each company gets a transparent composite score (0-10) using weighted factors:
  - Financial Quality (profitability):  20%
  - Growth:                             20%
  - Valuation (lower = better value):   20%
  - Balance Sheet health:               15%
  - Business Quality:                   15%
  - Risk (higher = safer):              10%
"""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models import (
    Company,
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

import re

def _normalize_period(fiscal_year: str) -> tuple[str, str | None]:
    """Return (period_type, interim_period)."""
    fy = fiscal_year.upper()
    match = re.search(r'(Q[1-4]|H[12]|9M)', fy)
    if match:
        return "Interim", match.group(1)
    return "Annual", None


# ── Where the data lives ──────────────────────────────────────────────
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "ipo_companies.json"

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────
SCORE_WEIGHTS = {
    "profitability": 0.20,
    "growth": 0.20,
    "valuation": 0.20,
    "balance_sheet": 0.15,
    "business_quality": 0.15,
    "risk": 0.10,
}


def _load_company_data() -> list[dict]:
    """
    Read and return the company list from our JSON data file.

    We do basic validation here so bad data doesn't silently corrupt the DB.
    """
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"IPO data file not found at {DATA_FILE}. "
            "Run from the backend/ directory or check the path."
        )

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    companies = data.get("companies", [])
    if not companies:
        raise ValueError("No companies found in the data file.")

    # Quick sanity check on required fields
    for company in companies:
        assert "name" in company, f"Company missing 'name': {company}"
        assert "ipo" in company, f"{company['name']} missing 'ipo' data"
        assert "financials" in company, f"{company['name']} missing 'financials'"
        assert len(company["financials"]) >= 1, (
            f"{company['name']} needs at least 1 financial period"
        )

    return companies


def _compute_overall_score(score_inputs: dict) -> float:
    """
    Compute the weighted composite score.

    This is DETERMINISTIC — no AI involved. Given the same inputs,
    you always get the same output. This is a deliberate design choice:
    the scoring methodology is transparent and auditable.
    """
    total = sum(
        score_inputs.get(factor, 0) * weight
        for factor, weight in SCORE_WEIGHTS.items()
    )
    return round(total, 2)


def _parse_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD string into a Python date object."""
    return date.fromisoformat(date_str)


def seed_demo_data(db: Session) -> None:
    """
    Populate the database with real IPO company data.

    This function is IDEMPOTENT — if data already exists, it does nothing.
    This is important because the server calls this on every startup.
    """
    # ── Guard: don't re-seed if data exists ──
    if db.scalar(select(Company.id).limit(1)):
        return

    companies_data = _load_company_data()
    db_companies: list[Company] = []

    for entry in companies_data:
        # ── 1. Create the Company record ──────────────────────────────
        company = Company(
            name=entry["name"],
            slug=entry["slug"],
            sector=entry["sector"],
            exchange=entry.get("exchange", "NSE / BSE"),
            description=entry["description"],
        )
        db.add(company)
        db.flush()  # Get the auto-generated company.id

        # ── 2. Create the IPO record ──────────────────────────────────
        ipo_data = entry["ipo"]
        from datetime import date as date_type
        from app.lifecycle import compute_lifecycle_status, parse_date_safe
        
        issue_d = _parse_date(ipo_data["issue_date"]) if ipo_data.get("issue_date") else None
        listing_d = _parse_date(ipo_data["listing_date"]) if ipo_data.get("listing_date") else None
        open_d = _parse_date(ipo_data["open_date"]) if ipo_data.get("open_date") else None
        close_d = _parse_date(ipo_data["close_date"]) if ipo_data.get("close_date") else None
        
        # CRITICAL: Compute lifecycle status from dates, NEVER trust static JSON
        computed_status = compute_lifecycle_status(
            open_date=open_d,
            close_date=close_d,
            listing_date=listing_d,
            issue_date=issue_d,
            static_status=ipo_data.get("status"),
        )
        
        ipo = IPO(
            company_id=company.id,
            status=computed_status,
            listing_segment=ipo_data.get("listing_segment"),
            issue_size=ipo_data["issue_size_crore"],
            price_low=ipo_data["price_low"],
            price_high=ipo_data["price_high"],
            issue_date=issue_d,
            open_date=open_d,
            close_date=close_d,
            listing_date=listing_d,
            fresh_issue=ipo_data.get("fresh_issue_crore", 0),
            ofs=ipo_data.get("ofs_crore", 0),
            data_source="seed",
            last_synced_at=datetime.utcnow(),
        )
        db.add(ipo)
        db.flush()


        # ── 3. Create Financial Periods + Metrics ─────────────────────
        for fin in entry["financials"]:
            ptype, interim = _normalize_period(fin["fiscal_year"])
            period = FinancialPeriod(
                company_id=company.id,
                period_end=_parse_date(fin["period_end"]),
                period_type=ptype,
                interim_period=interim,
                fiscal_year=fin["fiscal_year"],
            )
            db.add(period)
            db.flush()

            db.add(
                FinancialMetric(
                    period_id=period.id,
                    revenue=fin.get("revenue"),
                    ebitda=fin.get("ebitda"),
                    ebit=fin.get("ebit"), 
                    pat=fin.get("pat"),
                    eps=fin.get("eps"), 
                    total_debt=fin.get("total_debt"),
                    cash=fin.get("cash"),
                    equity=fin.get("equity"),
                    assets=fin.get("assets"), 
                    source_type="Curated Structured Dataset",
                    source_reference="ipo_companies.json",
                    derived_fields={}
                )
            )

        # ── 4. Create Valuation Metrics ───────────────────────────────
        val = entry.get("valuation", {})
        if val:
            debt = entry["financials"][-1].get("total_debt")
            cash = entry["financials"][-1].get("cash")
            ev = None
            if debt is not None and cash is not None:
                ev = val["market_cap"] + debt - cash
            db.add(
                ValuationMetric(
                    company_id=company.id,
                    date=_parse_date(val["date"]),
                    market_cap=val["market_cap"],
                    ev=ev,
                    pe=val.get("pe"),
                    ps=val.get("ps"),
                    ev_ebitda=val.get("ev_ebitda"),
                    ev_sales=val.get("ev_sales"),
                )
            )

        # ── 5. Create Risk Factors ────────────────────────────────────
        for risk in entry.get("risk_factors", []):
            db.add(
                RiskFactor(
                    ipo_id=ipo.id,
                    category=risk["category"],
                    severity=risk["severity"],
                    summary=risk["summary"],
                    source_page=risk.get("source_page"),
                )
            )

        # Note: Score calculation (generate_ipo_score) happens dynamically below AFTER peers are set up,
        # but we preserve the manually seeded business quality score.
        scores = entry.get("score_inputs", {})
        bq_score = scores.get("business_quality", None)
        setattr(ipo, "_manual_bq_score", bq_score)

        db_companies.append(company)

    # ── 7. Create Peer relationships ──────────────────────────────────
    # Clean up any existing peer relationships to remove stale all-to-all data
    db.execute(delete(Peer))
    db.flush()
    
    # Create peers strictly based on same sector
    for company in db_companies:
        for peer in db_companies:
            if company.id != peer.id and company.sector and company.sector == peer.sector:
                db.add(
                    Peer(
                        company_id=company.id,
                        peer_company_id=peer.id,
                        rationale=(
                            f"Same-sector comparable ({company.sector})."
                        ),
                        active=True
                    )
                )
    # ── 8. Compute and store the IPO Score ───────────────────────
    from app.analytics.scoring import generate_ipo_score
    for company in db_companies:
        for ipo in company.ipos:
            generate_ipo_score(db, ipo.id, getattr(ipo, "_manual_bq_score", None))
    db.flush()
    # ── 8. Create a demo Source document for evidence retrieval ────────
    if db_companies:
        first = db_companies[0]
        first_entry = companies_data[0]

        demo_doc = Document(
            company_id=first.id,
            type="Research note",
            storage_url=f"seed://{first_entry['slug']}-research-note",
            checksum=f"seed-{first_entry['slug']}-2024",
            processing_status="completed",
            page_count=2,
        )
        db.add(demo_doc)
        db.flush()

        # Create citation-ready text chunks from the company description
        evidence_texts = [
            (
                f"{first_entry['name']}: revenue grew from "
                f"₹{first_entry['financials'][0]['revenue']:.0f} crore in "
                f"{first_entry['financials'][0]['fiscal_year']} to "
                f"₹{first_entry['financials'][-1]['revenue']:.0f} crore in "
                f"{first_entry['financials'][-1]['fiscal_year']}. "
                f"{first_entry['description']}"
            ),
            (
                f"Key risk factors for {first_entry['name']}: "
                + " ".join(r["summary"] for r in first_entry.get("risk_factors", [])[:2])
            ),
        ]

        for page, text in enumerate(evidence_texts, start=1):
            db.add(
                Source(
                    document_id=demo_doc.id,
                    page=page,
                    section="Seed research note",
                    chunk_id=f"seed-{first_entry['slug']}-{page}",
                    text=text,
                    source_text_hash=hashlib.sha256(text.encode()).hexdigest(),
                    confidence=0.75,
                )
            )

    db.commit()
