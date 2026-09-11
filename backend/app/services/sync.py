"""IPO sync service — upserts provider data into the database.

This module is the bridge between IPO providers (external data sources)
and the database. It handles:
    - Matching by company slug (unique key)
    - Creating new companies + IPOs for first-time records
    - Updating status and pricing for existing records
    - Skipping exact duplicates
    - Safe error handling (never crashes on bad data)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lifecycle import compute_lifecycle_status, parse_date_safe
from app.models import Company, IPO
from app.providers import IPOProvider, NormalizedIPO

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """Summary of a sync operation."""
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.added + self.updated + self.skipped + len(self.errors)

    def to_dict(self) -> dict:
        return {
            "added": self.added,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "total_processed": self.total_processed,
        }


def _parse_date(date_str: str | None) -> date | None:
    return parse_date_safe(date_str)


def _needs_update(ipo: IPO, record: NormalizedIPO) -> bool:
    """Check if the IPO record has changed and needs updating."""
    return (
        ipo.status != record.status
        or float(ipo.price_low) != record.price_low
        or float(ipo.price_high) != record.price_high
        or float(ipo.issue_size) != record.issue_size_crore
    )

def _infer_lifecycle_status(record: NormalizedIPO) -> str:
    """Infer the lifecycle status dynamically from dates.
    
    Uses the shared compute_lifecycle_status — never trusts static status
    when dates are available.
    """
    return compute_lifecycle_status(
        open_date=parse_date_safe(record.open_date),
        close_date=parse_date_safe(record.close_date),
        listing_date=parse_date_safe(record.listing_date),
        issue_date=parse_date_safe(record.issue_date),
        static_status=record.status,
    )


def sync_ipos(db: Session, provider: IPOProvider) -> SyncReport:
    """Sync IPO records from a provider into the database.

    This function is the core sync logic:
    1. Fetch normalized records from the provider
    2. For each record, match by company slug
    3. If new → create Company + IPO
    4. If exists but changed → update IPO fields
    5. If exists and unchanged → skip
    6. Catch and log any per-record errors

    Args:
        db: SQLAlchemy session
        provider: An IPOProvider implementation

    Returns:
        SyncReport with counts of added, updated, skipped, and errors
    """
    report = SyncReport()

    try:
        records = provider.fetch_current_ipos()
    except Exception as exc:
        logger.error("Provider failed to fetch IPOs: %s", exc)
        report.errors.append(f"Provider failure: {exc}")
        return report

    for record in records:
        try:
            _sync_single_record(db, record, report)
        except Exception as exc:
            logger.warning("Error syncing '%s': %s", record.name, exc)
            report.errors.append(f"{record.name}: {exc}")
            db.rollback()

    db.commit()

    logger.info(
        "Sync complete: added=%d, updated=%d, skipped=%d, errors=%d",
        report.added, report.updated, report.skipped, len(report.errors),
    )
    return report


def _ipo_kwargs(record: NormalizedIPO) -> dict:
    """Build the common kwargs for creating/updating an IPO record."""
    status = _infer_lifecycle_status(record)
    
    # We must also update the record's status so _needs_update works correctly
    record.status = status
    
    return dict(
        status=status,
        listing_segment=record.listing_segment,
        issue_size=record.issue_size_crore,
        price_low=record.price_low,
        price_high=record.price_high,
        issue_date=_parse_date(record.issue_date),
        open_date=_parse_date(record.open_date),
        close_date=_parse_date(record.close_date),
        listing_date=_parse_date(record.listing_date),
        fresh_issue=record.fresh_issue_crore,
        ofs=record.ofs_crore,
        lot_size=record.lot_size,
        min_investment=record.min_investment,
        face_value=record.face_value,
        shares_offered=record.shares_offered,
        data_source=record.data_source,
        source_url=record.source_url,
        last_synced_at=datetime.utcnow(),
    )


_redis_available: bool | None = None

def _is_redis_available() -> bool:
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    try:
        import redis
        from app.core.config import get_settings
        client = redis.from_url(get_settings().redis_url, socket_connect_timeout=0.2)
        client.ping()
        _redis_available = True
    except Exception:
        _redis_available = False
    return _redis_available


def _dispatch_filing_check(ipo_id: int) -> None:
    if not _is_redis_available():
        return
    try:
        from app.workers import check_filings_task
        check_filings_task.apply_async(args=[ipo_id], retry=False)
    except Exception as exc:
        logger.warning("Could not dispatch check_filings_task for IPO %s: %s", ipo_id, exc)


def _sync_single_record(db: Session, record: NormalizedIPO, report: SyncReport) -> None:
    """Process a single normalized IPO record."""
    # Look up by slug
    company = db.scalar(select(Company).where(Company.slug == record.slug))

    if company is None:
        # New company — create both Company and IPO
        company = Company(
            name=record.name,
            slug=record.slug,
            sector=record.sector or "Unknown",
            exchange=record.exchange,
            description=record.description,
        )
        db.add(company)
        db.flush()

        ipo = IPO(company_id=company.id, **_ipo_kwargs(record))
        db.add(ipo)
        db.flush()
        report.added += 1

        # Trigger autonomous discovery for new IPO
        _dispatch_filing_check(ipo.id)
        return

    # Company exists — find the IPO record
    ipo = db.scalar(select(IPO).where(IPO.company_id == company.id))

    # Enrich company sector and description if enriched and previously unknown
    if record.sector and (not company.sector or company.sector == "Unknown"):
        company.sector = record.sector
    if record.description and not company.description:
        company.description = record.description

    if ipo is None:
        # Company exists but no IPO — shouldn't happen normally, but handle it
        ipo = IPO(company_id=company.id, **_ipo_kwargs(record))
        db.add(ipo)
        db.flush()
        report.added += 1

        # Trigger autonomous discovery for new IPO
        _dispatch_filing_check(ipo.id)
        return

    # Guard: Never overwrite live records with seed records
    if ipo.data_source == "live" and record.data_source == "seed":
        report.skipped += 1
        return

    # IPO exists — check if it needs updating
    if _needs_update(ipo, record):
        status_changed = ipo.status != record.status
        for key, value in _ipo_kwargs(record).items():
            setattr(ipo, key, value)
        report.updated += 1

        # Trigger autonomous discovery on lifecycle update
        if status_changed:
            _dispatch_filing_check(ipo.id)
    else:
        # No changes — just update sync timestamp
        ipo.last_synced_at = datetime.utcnow()
        report.skipped += 1

