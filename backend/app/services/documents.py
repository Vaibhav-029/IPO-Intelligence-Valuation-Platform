from __future__ import annotations
import hashlib
from datetime import datetime
from pathlib import Path
import fitz
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.models import Document, Job, Source


def is_likely_heading(text: str) -> bool:
    """Heuristic for section heading detection."""
    clean = text.strip()
    return len(clean) > 0 and len(clean) < 120 and clean.isupper()


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
            blocks = page.get_text("blocks")
            text_blocks = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
            
            if not text_blocks:
                # Empty page - do not invent text, mark as empty
                db.add(Source(
                    document_id=document.id, page=page_number, section=None,
                    chunk_id=f"doc-{document.id}-p{page_number}-empty",
                    text="", source_text_hash="empty", confidence=0.0, is_empty=True
                ))
                continue
                
            current_section = None
            current_chunk = []
            current_len = 0
            chunk_number = 1
            
            for block_text in text_blocks:
                if is_likely_heading(block_text):
                    current_section = block_text
                
                current_chunk.append(block_text)
                current_len += len(block_text)
                
                if current_len >= 1500:
                    chunk_text = "\n\n".join(current_chunk)
                    digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    db.add(Source(
                        document_id=document.id, page=page_number, section=current_section,
                        chunk_id=f"doc-{document.id}-p{page_number}-c{chunk_number}",
                        text=chunk_text, source_text_hash=digest, confidence=1.0, is_empty=False
                    ))
                    chunk_number += 1
                    current_chunk = []
                    current_len = 0
                    
            if current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                db.add(Source(
                    document_id=document.id, page=page_number, section=current_section,
                    chunk_id=f"doc-{document.id}-p{page_number}-c{chunk_number}",
                    text=chunk_text, source_text_hash=digest, confidence=1.0, is_empty=False
                ))
        document.processing_status = "completed"
        if job:
            job.status, job.finished_at = "completed", datetime.utcnow()
        db.commit()
    except Exception as exc:
        document.processing_status = "failed"; document.failure_reason = str(exc)[:1000]
        if job:
            job.status, job.error, job.finished_at = "failed", str(exc)[:1000], datetime.utcnow()
        db.commit()

