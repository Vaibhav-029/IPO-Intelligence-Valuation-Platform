import os
import logging
from unittest.mock import patch
from sqlalchemy.orm import joinedload
from app.db import SessionLocal
from app.models import IPO, Company, Document, FinancialPeriod, FinancialMetric, RiskFactor, IPOSCore

# Patch delay methods to run synchronously
from app.workers import check_filings_task, download_filing_task, process_document_task, enrich_ipo_task

def run_synchronously():
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()

    print("\n--- Selecting Candidate IPO ---")
    candidate = db.query(IPO).options(joinedload(IPO.company)).join(Company).filter(Company.name.ilike('%Rentomojo%')).first()
    if not candidate:
        print("Rentomojo IPO not found. Creating it for testing...")
        company = Company(name="Rentomojo", slug="rentomojo", sector="Technology")
        db.add(company)
        db.commit()
        db.refresh(company)
        candidate = IPO(company_id=company.id, status="Upcoming", issue_size=1000.0)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
    doc_count = db.query(Document).filter(Document.ipo_id == candidate.id).count()

    # Mock the delay functions so they call the underlying task immediately
    with patch('app.workers.check_filings_task.delay') as mock_check, \
         patch('app.workers.download_filing_task.delay') as mock_dl, \
         patch('app.main.process_document_task.delay') as mock_proc, \
         patch('app.workers.enrich_ipo_task.delay') as mock_enrich:
         
        # When check_filings_task.delay is called, just call download_filing_task synchronously
        def mock_dl_side_effect(ipo_id, url, doc_type):
            print(f"-> Moving to download: {url}")
            download_filing_task(ipo_id, url, doc_type)
        mock_dl.side_effect = mock_dl_side_effect
        
        def mock_proc_side_effect(doc_id):
            print(f"-> Moving to process: Document {doc_id}")
            process_document_task(doc_id)
        mock_proc.side_effect = mock_proc_side_effect
        
        def mock_enrich_side_effect(ipo_id, doc_id):
            print(f"-> Moving to enrich: IPO {ipo_id}, Document {doc_id}")
            enrich_ipo_task(ipo_id, doc_id)
        mock_enrich.side_effect = mock_enrich_side_effect

        if doc_count == 0:
            print("\n--- Running Filing Discovery Pipeline ---")
            try:
                check_filings_task(candidate.id)
            except Exception as e:
                print(f"Pipeline failed: {e}")
        else:
            doc = db.query(Document).filter(Document.ipo_id == candidate.id).first()
            print(f"\n--- Reusing existing Document {doc.id} ---")
            print(f"-> Moving to enrich: IPO {candidate.id}, Document {doc.id}")
            enrich_ipo_task(candidate.id, doc.id)

    print("\n--- Verification & Results ---")
    db.refresh(candidate)

    docs = db.query(Document).filter(Document.ipo_id == candidate.id).all()
    print(f"Documents Created: {len(docs)}")
    for d in docs:
        print(f"  - ID: {d.id}, Type: {d.type}, URL: {d.storage_url}")
        print(f"    Validation & Processing Status: {d.processing_status}, Checksum: {d.checksum[:10] if d.checksum else 'None'}...")

    periods = db.query(FinancialPeriod).filter(FinancialPeriod.company_id == candidate.company_id).all()
    print(f"\nFinancial Periods Created: {len(periods)}")
    for p in periods:
        metrics = db.query(FinancialMetric).filter(FinancialMetric.period_id == p.id).all()
        for m in metrics:
            populated_fields = {k: getattr(m, k) for k in FinancialMetric.__table__.columns.keys() if k not in ('id', 'period_id', 'source_type', 'source_reference', 'derived_fields') and getattr(m, k) is not None}
            print(f"  - {p.period_type} {p.fiscal_year}: {len(populated_fields)} metrics extracted: {list(populated_fields.keys())} (Rows: {len(metrics)})")
            
        assert len(metrics) <= 1, f"Duplicate FinancialMetric rows found for period {p.id}"

    risks = db.query(RiskFactor).filter(RiskFactor.ipo_id == candidate.id).all()
    print(f"\nRisks Created: {len(risks)}")
    for r in risks:
        print(f"  - {r.severity}: {r.category} ({len(r.summary)} chars)")

    score = db.query(IPOSCore).filter(IPOSCore.ipo_id == candidate.id).first()
    print(f"\nIPO Score Generated: {score.overall_score if score else 'None'}")
    if score:
        print(f"  Financial Score: {score.financial_quality_score}")
        print(f"  Risk Score: {score.risk_score}")
        cov = score.coverage if score.coverage else {}
        print(f"  Coverage: {cov.get('overall_effective_weight')}% effective weight")
        for k, v in cov.items():
            if k != "overall_effective_weight":
                print(f"    - {k}: {'Available' if v.get('available') else 'Missing (' + str(v.get('reason')) + ')'}")
    else:
        print("\nNo IPO Score Generated.")

if __name__ == '__main__':
    run_synchronously()
