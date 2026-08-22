from celery import Celery
from app.core.config import get_settings
from app.db import SessionLocal
from app.services.documents import process_document

settings = get_settings()
celery_app = Celery("ipo_intelligence", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"


@celery_app.task(name="documents.process", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_document_task(document_id: int) -> None:
    db = SessionLocal()
    try:
        process_document(db, document_id)
    finally:
        db.close()
