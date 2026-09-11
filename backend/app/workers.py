from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings
from app.db import SessionLocal
from app.services.documents import process_document
from app.services.discovery import find_candidate_pdf_urls, validate_filing_url
from app.services.financial_extractor import extract_financials
from app.services.risk_extractor import extract_risks
from app.models import IPO, Document
import logging
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

settings = get_settings()
celery_app = Celery("ipo_intelligence", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"

# Beat schedule for periodic refresh
celery_app.conf.beat_schedule = {
    'refresh-active-ipos-daily': {
        'task': 'ipos.refresh_active',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
    'sync-live-ipos-hourly': {
        'task': 'ipos.sync_live',
        'schedule': crontab(minute=0),  # Run every hour
    }
}


@celery_app.task(name="documents.process", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_document_task(document_id: int) -> None:
    db = SessionLocal()
    try:
        process_document(db, document_id)
        doc = db.get(Document, document_id)
        if doc and doc.ipo_id and doc.processing_status == "completed":
            enrich_ipo_task.delay(doc.ipo_id, doc.id)
    finally:
        db.close()


@celery_app.task(name="ipos.check_filings", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def check_filings_task(ipo_id: int) -> None:
    db = SessionLocal()
    try:
        ipo = db.get(IPO, ipo_id)
        if not ipo:
            return

        company = ipo.company
        urls = find_candidate_pdf_urls(company.name)
        if not urls:
            logger.info("Pending filing: No candidate filing URLs found for %s (IPO ID %s). Will retry on scheduled refresh.", company.name, ipo_id)
            return

        found = False
        for url in urls:
            candidate = validate_filing_url(url, company.name)
            if candidate:
                found = True
                download_filing_task.delay(ipo_id, candidate.url, candidate.doc_type)
                break  # Stop after first valid candidate is queued

        if not found:
            logger.info("Pending filing: No candidate passed validation for %s (IPO ID %s). Will retry on scheduled refresh.", company.name, ipo_id)

    finally:
        db.close()


@celery_app.task(name="ipos.download_filing", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def download_filing_task(ipo_id: int, url: str, doc_type: str) -> None:
    db = SessionLocal()
    try:
        ipo = db.get(IPO, ipo_id)
        if not ipo:
            return

        # Re-validate to get bytes safely
        candidate = validate_filing_url(url, ipo.company.name)
        if not candidate or not candidate.pdf_bytes:
            return

        pdf_bytes = candidate.pdf_bytes
        checksum = hashlib.sha256(pdf_bytes).hexdigest()

        # Deduplication check
        existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
        if existing_doc:
            return  # Already exists, do nothing

        # Save to disk
        from pathlib import Path
        storage_dir = Path("./data/uploads")
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = str(storage_dir / f"ipo_doc_{ipo_id}_{checksum[:8]}.pdf")
        with open(storage_path, "wb") as f:
            f.write(pdf_bytes)

        # Create Document record
        doc = Document(
            company_id=ipo.company_id,
            ipo_id=ipo.id,
            type=doc_type,
            filename=f"{ipo.company.slug}-{doc_type.lower()}.pdf",
            storage_url=storage_path,
            checksum=checksum,
            processing_status="queued"
        )
        db.add(doc)
        db.commit()

        # Trigger processing
        process_document_task.delay(doc.id)

    finally:
        db.close()


@celery_app.task(name="ipos.enrich", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def enrich_ipo_task(ipo_id: int, document_id: int) -> None:
    db = SessionLocal()
    try:
        ipo = db.get(IPO, ipo_id)
        if not ipo:
            return

        # Extract Financials
        from app.models import FinancialPeriod, RiskFactor, IPOSCore
        from app.agent.providers import RateLimitError
        
        has_financials = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).first() is not None
        has_risks = db.query(RiskFactor).filter_by(ipo_id=ipo_id).first() is not None
        
        if not has_financials:
            try:
                from app.services.financial_extractor import extract_financials
                res = extract_financials(db, document_id, ipo.company_id)
                logger.info(f"Financials extraction result: {res.status if res else 'None'} - {res.errors if res else ''}")
            except RateLimitError:
                logger.warning(f"Rate limit hit during financials extraction for IPO {ipo_id}")
        
        if not has_risks:
            try:
                from app.services.risk_extractor import extract_risks
                res_r = extract_risks(db, document_id, ipo_id)
                logger.info(f"Risks extraction result: {res_r}")
            except RateLimitError:
                logger.warning(f"Rate limit hit during risk extraction for IPO {ipo_id}")

        db.commit()

        # Recalculate score
        from app.analytics.scoring import generate_ipo_score
        generate_ipo_score(db, ipo_id)
        db.commit()

    finally:
        db.close()


def reconcile_active_ipo(db, ipo_id: int) -> dict:
    """Reconcile an active IPO through the autonomous enrichment pipeline.
    
    Adheres strictly to the required flow:
    1. Check whether a valid filing exists.
    2. If no filing exists, attempt filing discovery.
    3. If a new valid filing exists, download/process/enrich.
    4. If a filing exists but financials/risks/score are missing, trigger enrichment.
    5. If enrichment is partial, retry only the missing stages.
    6. If no filing is currently available, leave a safe "pending filing" state.
    7. Never fabricate financials or scores.
    8. Never overwrite existing verified data with NULL.
    """
    from app.models import IPO, Document, FinancialPeriod, RiskFactor, IPOSCore
    from pathlib import Path

    ipo = db.get(IPO, ipo_id)
    if not ipo:
        return {"status": "error", "message": f"IPO {ipo_id} not found"}

    # Check for existing document
    doc = db.query(Document).filter(Document.ipo_id == ipo.id).order_by(Document.created_at.desc()).first()
    
    # 1. If no filing exists, attempt discovery
    if not doc:
        urls = find_candidate_pdf_urls(ipo.company.name)
        valid_candidate = None
        for u in urls:
            c = validate_filing_url(u, ipo.company.name)
            if c and c.pdf_bytes:
                valid_candidate = c
                break
        
        if not valid_candidate:
            logger.info("Pending filing: No authoritative filing discovered for %s (IPO %d)", ipo.company.name, ipo.id)
            return {
                "ipo_id": ipo.id,
                "company": ipo.company.name,
                "status": "pending_filing",
                "message": "No authoritative DRHP/RHP currently available on repositories"
            }
        
        # Save discovered filing
        checksum = hashlib.sha256(valid_candidate.pdf_bytes).hexdigest()
        existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
        if existing_doc:
            doc = existing_doc
            if not doc.ipo_id:
                doc.ipo_id = ipo.id
                db.commit()
        else:
            storage_dir = Path("./data/uploads")
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = str(storage_dir / f"ipo_doc_{ipo.id}_{checksum[:8]}.pdf")
            with open(storage_path, "wb") as f:
                f.write(valid_candidate.pdf_bytes)
            doc = Document(
                company_id=ipo.company_id,
                ipo_id=ipo.id,
                type=valid_candidate.doc_type or "RHP",
                filename=f"{ipo.company.slug}-{(valid_candidate.doc_type or 'rhp').lower()}.pdf",
                storage_url=storage_path,
                checksum=checksum,
                processing_status="queued"
            )
            db.add(doc)
            db.commit()

    # 2. If doc exists and not completed, process document
    if doc.processing_status != "completed":
        process_document(db, doc.id)
        db.refresh(doc)

    # 3. Check partial enrichment and extract missing stages only
    has_financials = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).first() is not None
    has_risks = db.query(RiskFactor).filter_by(ipo_id=ipo.id).first() is not None

    if not has_financials:
        try:
            extract_financials(db, doc.id, ipo.company_id)
            db.commit()
        except Exception as e:
            logger.warning("Error extracting financials for IPO %d: %s", ipo.id, e)

    if not has_risks:
        try:
            extract_risks(db, doc.id, ipo.id)
            db.commit()
        except Exception as e:
            logger.warning("Error extracting risks for IPO %d: %s", ipo.id, e)

    # 4. Generate/recalculate score if missing or after extraction
    from app.analytics.scoring import generate_ipo_score
    generate_ipo_score(db, ipo.id)
    db.commit()

    # Refresh and summarize state
    periods = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).all()
    risks = db.query(RiskFactor).filter_by(ipo_id=ipo.id).all()
    score = db.query(IPOSCore).filter_by(ipo_id=ipo.id).first()

    return {
        "ipo_id": ipo.id,
        "company": ipo.company.name,
        "document_id": doc.id,
        "document_status": doc.processing_status,
        "financial_periods": len(periods),
        "risks": len(risks),
        "score": score.overall_score if score else None,
        "coverage": score.coverage if score else None
    }


@celery_app.task(name="ipos.refresh_active")
def refresh_active_ipos_task() -> None:
    db = SessionLocal()
    try:
        from app.models import Document, FinancialPeriod, RiskFactor, IPOSCore
        # Get active IPOs
        ipos = db.query(IPO).filter(IPO.status.in_(["Upcoming", "Ongoing"])).all()
        for ipo in ipos:
            # Check for existing document
            latest_doc = db.query(Document).filter(Document.ipo_id == ipo.id).order_by(Document.created_at.desc()).first()
            if latest_doc:
                if latest_doc.processing_status == "completed":
                    has_financials = db.query(FinancialPeriod).filter_by(company_id=ipo.company_id).first() is not None
                    has_risks = db.query(RiskFactor).filter_by(ipo_id=ipo.id).first() is not None
                    has_score = db.query(IPOSCore).filter_by(ipo_id=ipo.id).first() is not None
                    if not has_financials or not has_risks or not has_score:
                        enrich_ipo_task.delay(ipo.id, latest_doc.id)
                else:
                    process_document_task.delay(latest_doc.id)
            else:
                # No document exists! Trigger filing discovery for active IPO
                check_filings_task.delay(ipo.id)
    finally:
        db.close()


@celery_app.task(name="ipos.sync_live")
def sync_live_ipos_task() -> None:
    db = SessionLocal()
    try:
        from app.providers.live import LiveIPOProvider
        from app.services.sync import sync_ipos
        provider = LiveIPOProvider()
        sync_ipos(db, provider)
    finally:
        db.close()
