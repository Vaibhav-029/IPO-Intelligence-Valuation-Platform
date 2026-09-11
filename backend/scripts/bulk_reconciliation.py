"""Bulk Active-IPO Reconciliation Script.

Runs the autonomous reconciliation pipeline across every active IPO (Upcoming & Ongoing).
Adheres strictly to invariants:
- Never fabricates data
- Never overwrites existing valid records
- Leaves truthful explicit reasons for pending or insufficient data
"""
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import IPO, Company, Document, FinancialPeriod, RiskFactor, IPOSCore, ValuationMetric
from app.workers import reconcile_active_ipo

def run_bulk_reconciliation():
    db = SessionLocal()
    try:
        active_ipos = (
            db.query(IPO)
            .join(Company)
            .filter(IPO.status.in_(["Upcoming", "Ongoing"]))
            .order_by(IPO.id)
            .all()
        )
        print(f"Starting bulk reconciliation for {len(active_ipos)} active IPOs...\n")

        results = []
        for ipo in active_ipos:
            company_name = ipo.company.name
            print(f"[{ipo.id}] Checking {company_name} ({ipo.status})...")
            
            # Check existing state
            existing_doc = db.query(Document).filter_by(ipo_id=ipo.id).first()
            existing_periods = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).all()
            existing_risks = db.query(RiskFactor).filter_by(ipo_id=ipo.id).all()
            existing_score = db.query(IPOSCore).filter_by(ipo_id=ipo.id).first()
            
            # If already enriched, skip expensive re-extraction
            if existing_doc and existing_periods and existing_score and existing_score.overall_score is not None:
                print(f"  -> Already enriched: Score {existing_score.overall_score}, {len(existing_periods)} periods, {len(existing_risks)} risks")
                val = db.query(ValuationMetric).filter_by(company_id=ipo.company_id).first()
                results.append({
                    "id": ipo.id,
                    "name": company_name,
                    "status": ipo.status,
                    "filing": f"Yes ({existing_doc.type})",
                    "document": f"Doc {existing_doc.id} ({existing_doc.page_count} pages)",
                    "financials": f"{len(existing_periods)} periods",
                    "risks": f"{len(existing_risks)} risks",
                    "valuation": "IPO_AT_ISSUE" if val or ipo.price_high else "Pending",
                    "score": f"{existing_score.overall_score:.2f}",
                    "coverage": f"{existing_score.coverage.get('overall_effective_weight', 0):.0f}%" if existing_score.coverage else "N/A",
                    "reason": "Populated"
                })
                continue

            # Run reconciliation
            try:
                rec = reconcile_active_ipo(db, ipo.id)
                status = rec.get("status")
                
                # Check resulting DB state
                doc = db.query(Document).filter_by(ipo_id=ipo.id).first()
                periods = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).all()
                risks = db.query(RiskFactor).filter_by(ipo_id=ipo.id).all()
                score = db.query(IPOSCore).filter_by(ipo_id=ipo.id).first()
                val = db.query(ValuationMetric).filter_by(company_id=ipo.company_id).first()
                
                score_str = f"{score.overall_score:.2f}" if score and score.overall_score is not None else "None"
                coverage_str = f"{score.coverage.get('overall_effective_weight', 0):.0f}%" if score and score.coverage else "0%"
                
                reason = "Populated"
                if not doc:
                    reason = "Pending filing: No authoritative DRHP/RHP currently published on SEBI/BSE"
                elif len(periods) == 0:
                    reason = "Insufficient Data: Filing available but multi-year financial statements pending extraction"
                elif score is None or score.overall_score is None:
                    reason = "Insufficient Data: Incomplete dimensions for quantitative scoring threshold"

                results.append({
                    "id": ipo.id,
                    "name": company_name,
                    "status": ipo.status,
                    "filing": f"Yes ({doc.type})" if doc else "No",
                    "document": f"Doc {doc.id} ({doc.page_count} pages)" if doc else "None",
                    "financials": f"{len(periods)} periods" if len(periods) > 0 else "0 periods",
                    "risks": f"{len(risks)} risks",
                    "valuation": "IPO_AT_ISSUE" if (val or ipo.price_high) else "Pending",
                    "score": score_str,
                    "coverage": coverage_str,
                    "reason": reason
                })
                print(f"  -> Reconciled: Score {score_str}, Reason: {reason}")
            except Exception as e:
                print(f"  -> Error reconciling {company_name}: {e}")
                results.append({
                    "id": ipo.id,
                    "name": company_name,
                    "status": ipo.status,
                    "filing": "Unknown",
                    "document": "None",
                    "financials": "0 periods",
                    "risks": "0 risks",
                    "valuation": "None",
                    "score": "None",
                    "coverage": "0%",
                    "reason": f"Reconciliation error: {str(e)[:60]}"
                })

        print("\n" + "="*120)
        print("RECONCILIATION SUMMARY")
        print("="*120)
        for r in results:
            print(f"{r['id']:2d} | {r['name']:30s} | {r['status']:8s} | {r['filing']:10s} | {r['document']:16s} | {r['financials']:11s} | {r['risks']:8s} | {r['score']:6s} | {r['reason']}")
            
        return results
    finally:
        db.close()

if __name__ == "__main__":
    run_bulk_reconciliation()
