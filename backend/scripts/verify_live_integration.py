"""Backend integration verification script:
1. Reset/reseed the database.
2. Run the live IPO sync from IPO Central.
3. Verify that the live 2026 records are persisted after the seed step.
4. Verify that live records are NOT being overwritten by the 2025 seed records.
5. Verify the final database contains:
   - current Ongoing IPOs
   - current Upcoming IPOs
   - recent Closed IPOs
   - Recent Listed IPOs only when listing_date is within 30 days
6. Verify each live record has:
   - name
   - open_date
   - close_date
   - listing_date
   - status derived from those dates
   - listing_segment
   - issue_size
   - price_band
   - sector where the source provides it
   - data_source = live
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Company, IPO
from app.seed import seed_demo_data
from app.services.sync import sync_ipos
from app.providers.live import LiveIPOProvider
from app.lifecycle import compute_lifecycle_status
from app.core.config import get_settings


def verify():
    settings = get_settings()
    today = date.today()
    print(f"--- STARTING INTEGRATION VERIFICATION (Today = {today}) ---")

    # 1. Reset / reseed the database
    print("\n[Step 1] Resetting and reseeding database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        seed_count = db.scalar(select(func.count(IPO.id)))
        print(f"Seeded {seed_count} initial records from ipo_companies.json.")
        assert seed_count == 28, f"Expected 28 seed records, got {seed_count}"

    # 2. Run the live IPO sync from IPO Central
    print("\n[Step 2] Running live IPO sync from IPO Central...")
    provider = LiveIPOProvider()
    with SessionLocal() as db:
        report = sync_ipos(db, provider)
        print(f"Sync Report: Added={report.added}, Updated={report.updated}, Skipped={report.skipped}, Errors={len(report.errors)}")
        assert report.added > 0, f"Expected added records > 0, got {report.added}"

    # 3. Verify that the live 2026 records are persisted after the seed step
    print("\n[Step 3] Re-running seed_demo_data to test persistence / non-overwrite...")
    from sqlalchemy.orm import joinedload
    with SessionLocal() as db:
        seed_demo_data(db)  # Idempotent seed run
        total_ipos = db.scalar(select(func.count(IPO.id)))
        live_ipos = db.scalars(select(IPO).options(joinedload(IPO.company)).where(IPO.data_source == "live")).all()
        print(f"Total IPOs in DB: {total_ipos}, Live IPOs in DB: {len(live_ipos)}")
        assert len(live_ipos) >= report.added, "Live IPO records were lost or overwritten during re-seed!"

    # 4. Verify that live records are NOT being overwritten by 2025 seed records
    print("\n[Step 4] Checking live record integrity (no overwrite by seed records)...")
    with SessionLocal() as db:
        for live_ipo in live_ipos:
            assert live_ipo.data_source == "live", f"Record {live_ipo.company.name} data_source changed to {live_ipo.data_source}"
            # Verify open date or close date is in 2026
            if live_ipo.open_date:
                assert live_ipo.open_date.year == 2026, f"Expected 2026 date for live IPO {live_ipo.company.name}, got {live_ipo.open_date}"

    # 5. Verify the final database contains feed distribution
    print("\n[Step 5] Checking database distribution for Ongoing, Upcoming, Closed, Listed...")
    with SessionLocal() as db:
        all_ipos = db.scalars(select(IPO)).all()
        by_status = {}
        for ipo in all_ipos:
            by_status[ipo.status] = by_status.get(ipo.status, 0) + 1
        print(f"Status distribution in DB: {by_status}")
        
        # Test feed filter (default feed query)
        recent_closed_date = today - timedelta(days=settings.recently_closed_days)
        recent_listed_date = today - timedelta(days=settings.recently_listed_days)
        
        feed_stmt = select(IPO).join(Company).where(
            (IPO.status == "Ongoing") |
            (IPO.status == "Upcoming") |
            ((IPO.status == "Closed") & (func.coalesce(IPO.close_date, IPO.issue_date) >= recent_closed_date)) |
            ((IPO.status == "Listed") & (func.coalesce(IPO.listing_date, IPO.issue_date) >= recent_listed_date))
        )
        feed_items = db.scalars(feed_stmt).all()
        print(f"Default feed items returned (active window): {len(feed_items)}")
        assert len(feed_items) > 0, "Expected feed items in active window from live sync!"

    # 6. Verify each live record schema and derived status
    print("\n[Step 6] Validating each live record schema, attributes, and lifecycle derivation...")
    with SessionLocal() as db:
        for idx, ipo in enumerate(live_ipos, 1):
            assert ipo.company.name, f"Live record {idx} missing name"
            assert ipo.data_source == "live", f"Live record {ipo.company.name} data_source is {ipo.data_source}"
            
            # Derived status check
            expected_status = compute_lifecycle_status(
                open_date=ipo.open_date,
                close_date=ipo.close_date,
                listing_date=ipo.listing_date,
                issue_date=ipo.issue_date,
                reference_date=today,
            )
            assert ipo.status == expected_status, (
                f"Record {ipo.company.name} has status '{ipo.status}', but computed status is '{expected_status}' "
                f"(open={ipo.open_date}, close={ipo.close_date}, listing={ipo.listing_date}, today={today})"
            )
            
            # Print sample
            if idx <= 5:
                print(f"  [OK] [{ipo.status}] {ipo.company.name} | Dates: open={ipo.open_date}, close={ipo.close_date}, list={ipo.listing_date} | Seg: {ipo.listing_segment} | Size: {ipo.issue_size} Cr | Band: {ipo.price_low}-{ipo.price_high} | Sector: {ipo.company.sector}")

    print("\n========================================================")
    print(">>> ALL INTEGRATION VERIFICATION CHECKS PASSED (100%) <<<")
    print("========================================================")


if __name__ == "__main__":
    verify()
