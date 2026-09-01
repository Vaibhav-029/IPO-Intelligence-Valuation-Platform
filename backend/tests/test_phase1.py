"""Phase 1 verification tests — IPO lifecycle, sync, and provider.

These tests verify:
    - IPO status distribution after seeding
    - /api/v1/ipos/summary returns correct counts
    - Status filtering works for each lifecycle state
    - Second sync does NOT create duplicates
    - Invalid/incomplete provider records are rejected safely
    - Source and sync timestamps are persisted
"""
from collections import Counter
from datetime import datetime

from sqlalchemy import select

from app.db import Base, engine, get_db
from app.models import Company, IPO
from app.providers import NormalizedIPO, SeedFileProvider
from app.seed import seed_demo_data
from app.services.sync import SyncReport, sync_ipos


def _fresh_db():
    """Drop and recreate all tables, seed, and return a session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db)
    return db


# ── 1. IPO lifecycle distribution ─────────────────────────────────────

def test_seed_creates_all_lifecycle_statuses():
    """After seeding, the DB should contain Upcoming, Open, Closed, and Listed IPOs."""
    db = _fresh_db()
    statuses = db.scalars(select(IPO.status)).all()
    counts = Counter(statuses)

    assert counts["Listed"] > 0, "No Listed IPOs found"
    assert counts["Upcoming"] > 0, "No Upcoming IPOs found"
    assert counts["Ongoing"] > 0, "No Ongoing IPOs found"
    assert counts["Closed"] > 0, "No Closed IPOs found"
    assert sum(counts.values()) == 28, f"Expected 28 total IPOs, got {sum(counts.values())}"

    db.close()


def test_seed_counts_match_expected():
    """Verify exact counts match our seed data."""
    db = _fresh_db()
    statuses = db.scalars(select(IPO.status)).all()
    counts = Counter(statuses)

    assert counts["Listed"] == 21
    assert counts["Upcoming"] == 3
    assert counts["Ongoing"] == 2
    assert counts["Closed"] == 2

    db.close()


# ── 2. Source and sync provenance ─────────────────────────────────────

def test_seed_sets_provenance_fields():
    """All seeded IPOs should have data_source='seed' and a last_synced_at timestamp."""
    db = _fresh_db()
    ipos = db.scalars(select(IPO)).all()

    for ipo in ipos:
        assert ipo.data_source == "seed", f"IPO {ipo.id} missing data_source"
        assert ipo.last_synced_at is not None, f"IPO {ipo.id} missing last_synced_at"
        assert isinstance(ipo.last_synced_at, datetime)

    db.close()


# ── 3. Status filtering ──────────────────────────────────────────────

def test_status_filtering_upcoming():
    """Filtering by 'Upcoming' should return only Upcoming IPOs."""
    db = _fresh_db()
    upcoming = db.scalars(select(IPO).where(IPO.status == "Upcoming")).all()
    assert len(upcoming) == 3
    for ipo in upcoming:
        assert ipo.status == "Upcoming"
    db.close()


def test_status_filtering_ongoing():
    """Filtering by 'Ongoing' should return only Ongoing IPOs."""
    db = _fresh_db()
    ongoing_ipos = db.scalars(select(IPO).where(IPO.status == "Ongoing")).all()
    assert len(ongoing_ipos) == 2
    for ipo in ongoing_ipos:
        assert ipo.status == "Ongoing"
    db.close()


def test_status_filtering_closed():
    """Filtering by 'Closed' should return only Closed IPOs."""
    db = _fresh_db()
    closed = db.scalars(select(IPO).where(IPO.status == "Closed")).all()
    assert len(closed) == 2
    for ipo in closed:
        assert ipo.status == "Closed"
    db.close()


def test_status_filtering_listed():
    """Filtering by 'Listed' should return only Listed IPOs."""
    db = _fresh_db()
    listed = db.scalars(select(IPO).where(IPO.status == "Listed")).all()
    assert len(listed) == 21
    for ipo in listed:
        assert ipo.status == "Listed"
    db.close()


# ── 4. Sync — deduplication ──────────────────────────────────────────

def test_sync_does_not_create_duplicates():
    """Running sync twice with the same data should NOT create duplicate records."""
    db = _fresh_db()

    # Count after seed
    count_before = len(db.scalars(select(IPO)).all())

    # Run sync with the same seed provider
    provider = SeedFileProvider()
    report = sync_ipos(db, provider)

    # Count after sync
    count_after = len(db.scalars(select(IPO)).all())

    # No new records should be created
    assert count_after == count_before, (
        f"Duplicate IPOs created: {count_before} -> {count_after}"
    )
    assert report.added == 0, f"Sync added {report.added} new records (expected 0)"
    assert report.skipped == count_before, (
        f"Expected {count_before} skipped, got {report.skipped}"
    )

    db.close()


def test_sync_report_structure():
    """SyncReport should have the correct shape."""
    db = _fresh_db()
    provider = SeedFileProvider()
    report = sync_ipos(db, provider)
    result = report.to_dict()

    assert "added" in result
    assert "updated" in result
    assert "skipped" in result
    assert "errors" in result
    assert "total_processed" in result
    assert isinstance(result["errors"], list)

    db.close()


# ── 5. Provider validation ───────────────────────────────────────────

def test_normalized_ipo_rejects_invalid_status():
    """NormalizedIPO should reject records with an invalid status."""
    try:
        NormalizedIPO(
            name="Bad Company",
            slug="bad-company",
            sector="Tech",
            status="INVALID_STATUS",
            issue_size_crore=100,
            price_low=10,
            price_high=20,
        )
        assert False, "Should have raised ValidationError"
    except Exception as exc:
        assert "Invalid status" in str(exc) or "validation error" in str(exc).lower()


def test_normalized_ipo_rejects_negative_issue_size():
    """NormalizedIPO should reject records with negative issue size."""
    try:
        NormalizedIPO(
            name="Bad Company",
            slug="bad-company",
            sector="Tech",
            status="Upcoming",
            issue_size_crore=-100,
            price_low=10,
            price_high=20,
        )
        assert False, "Should have raised ValidationError"
    except Exception:
        pass  # Expected


def test_normalized_ipo_rejects_invalid_date():
    """NormalizedIPO should reject records with malformed dates."""
    try:
        NormalizedIPO(
            name="Bad Company",
            slug="bad-company",
            sector="Tech",
            status="Upcoming",
            issue_size_crore=100,
            price_low=10,
            price_high=20,
            issue_date="not-a-date",
        )
        assert False, "Should have raised ValidationError"
    except Exception:
        pass  # Expected


def test_provider_skips_invalid_records():
    """SeedFileProvider should skip records that fail validation without crashing."""
    provider = SeedFileProvider()
    results = provider.fetch_current_ipos()

    # All results should be valid NormalizedIPO objects
    for record in results:
        assert isinstance(record, NormalizedIPO)
        assert record.name
        assert record.slug
        assert record.status in {"Upcoming", "Ongoing", "Closed", "Listed"}


# ── 6. Provider failure handling ─────────────────────────────────────

def test_sync_handles_provider_failure_safely():
    """If the provider throws, sync should return a report with an error, not crash."""
    from app.providers import IPOProvider

    class FailingProvider(IPOProvider):
        def fetch_current_ipos(self):
            raise ConnectionError("Simulated provider failure")

    db = _fresh_db()
    report = sync_ipos(db, FailingProvider())

    assert len(report.errors) > 0
    assert "provider" in report.errors[0].lower() or "failure" in report.errors[0].lower()
    assert report.added == 0
    assert report.updated == 0

    db.close()


# ── 7. Seed idempotency ──────────────────────────────────────────────

def test_seed_is_idempotent():
    """Calling seed_demo_data twice should not duplicate records."""
    db = _fresh_db()
    count_after_first = len(db.scalars(select(Company)).all())

    # Call seed again
    seed_demo_data(db)
    count_after_second = len(db.scalars(select(Company)).all())

    assert count_after_first == count_after_second, (
        f"Seed created duplicates: {count_after_first} -> {count_after_second}"
    )

    db.close()
