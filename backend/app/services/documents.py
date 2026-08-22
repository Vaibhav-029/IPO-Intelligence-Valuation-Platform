from __future__ import annotations
import hashlib
from datetime import datetime
from pathlib import Path
import fitz
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.models import Document, Job, Source


def chunk_page(text: str, size: int = 1200) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size) if text[i:i + size].strip()]


def process_document(db: Session, document_id: int) -> None:
    document = db.get(Document, document_id)
    if not document:
        return
    job = db.query(Job).filter_by(entity_id=document.id, job_type="document_processing").order_by(Job.id.desc()).first()
    document.processing_status = "processing"
    if job:
        job.status, job.attempt_count, job.started_at = "processing", job.attempt_count + 1, datetime.utcnow()
    db.commit()
    try:
        pdf = fitz.open(document.storage_url)
        document.page_count = len(pdf)
        db.execute(delete(Source).where(Source.document_id == document.id))
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            # OCR is intentionally a pluggable fallback; this records low quality instead of inventing text.
            confidence = 1.0 if len(text) > 100 else 0.35
            if not text:
                text = "No extractable text. OCR fallback must be configured for this page."
            for chunk_number, chunk in enumerate(chunk_page(text), start=1):
                digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                db.add(Source(document_id=document.id, page=page_number, section="Extracted page text", chunk_id=f"doc-{document.id}-p{page_number}-c{chunk_number}", text=chunk, source_text_hash=digest, confidence=confidence))
        document.processing_status = "completed"
        if job:
            job.status, job.finished_at = "completed", datetime.utcnow()
        db.commit()
    except Exception as exc:
        document.processing_status = "failed"; document.failure_reason = str(exc)[:1000]
        if job:
            job.status, job.error, job.finished_at = "failed", str(exc)[:1000], datetime.utcnow()
        db.commit()

