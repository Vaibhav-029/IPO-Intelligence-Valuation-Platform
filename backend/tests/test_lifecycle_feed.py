import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import Base, get_db
from app.models import Company, IPO
from app.seed import seed_demo_data
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def override_db_fixture():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

def _fresh_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    seed_demo_data(db)
    
    today = date.today()
    # Add test SME ongoing IPO
    sme_company = Company(
        name="Test SME Enterprises",
        slug="test-sme-enterprises",
        sector="Manufacturing",
        exchange="NSE Emerge",
        description="A test SME company",
    )
    db.add(sme_company)
    db.flush()
    sme_ipo = IPO(
        company_id=sme_company.id,
        status="Ongoing",
        listing_segment="SME",
        issue_size=50.0,
        price_low=100.0,
        price_high=105.0,
        open_date=today - timedelta(days=1),
        close_date=today + timedelta(days=2),
        data_source="test",
    )
    db.add(sme_ipo)

    # Add test upcoming Mainboard IPO
    upcoming_company = Company(
        name="Test Upcoming Corp",
        slug="test-upcoming-corp",
        sector="Technology",
        exchange="NSE / BSE",
        description="A test upcoming company",
    )
    db.add(upcoming_company)
    db.flush()
    upcoming_ipo = IPO(
        company_id=upcoming_company.id,
        status="Upcoming",
        listing_segment="Mainboard",
        issue_size=500.0,
        price_low=200.0,
        price_high=210.0,
        open_date=today + timedelta(days=3),
        close_date=today + timedelta(days=5),
        data_source="test",
    )
    db.add(upcoming_ipo)

    # Add test unclassified segment IPO
    null_company = Company(
        name="Test Unclassified Corp",
        slug="test-unclassified-corp",
        sector="Services",
        exchange="NSE / BSE",
        description="A test unclassified company",
    )
    db.add(null_company)
    db.flush()
    null_ipo = IPO(
        company_id=null_company.id,
        status="Upcoming",
        listing_segment=None,
        issue_size=150.0,
        price_low=50.0,
        price_high=55.0,
        open_date=today + timedelta(days=7),
        close_date=today + timedelta(days=9),
        data_source="test",
    )
    db.add(null_ipo)

    db.commit()
    return db

def test_listing_segments_seeded():
    db = _fresh_db()
    ipos = db.scalars(select(IPO)).all()
    segments = {ipo.listing_segment for ipo in ipos}
    assert "Mainboard" in segments
    assert "SME" in segments
    assert None in segments
    
    # Verify the API exposes this
    response = client.get("/api/v1/ipos")
    assert response.status_code == 200
    data = response.json()
    assert "listing_segment" in data["items"][0]
    db.close()

def test_recently_listed_boundary_conditions():
    """Prove:
    1. A Listed IPO 5 days ago appears in Recently Listed.
    2. A Listed IPO 31 days ago does not appear.
    3. A Listed IPO from 2025 does not appear.
    4. A Listed IPO from 2024 does not appear.
    5. If zero recent Listed IPOs, API returns zero Listed records.
    6. Historical Listed IPOs remain accessible via explicit status filter and direct ID.
    """
    db = _fresh_db()
    today = date.today()

    # 1. Listed 5 days ago
    c_5d = Company(name="Co 5d Listed", slug="co-5d-listed", sector="IT")
    db.add(c_5d); db.flush()
    ipo_5d = IPO(company_id=c_5d.id, status="Listed", listing_segment="Mainboard", issue_size=100.0, listing_date=today - timedelta(days=5), issue_date=today - timedelta(days=5))
    db.add(ipo_5d)

    # 2. Listed 31 days ago (just outside 30-day window)
    c_31d = Company(name="Co 31d Listed", slug="co-31d-listed", sector="Auto")
    db.add(c_31d); db.flush()
    ipo_31d = IPO(company_id=c_31d.id, status="Listed", listing_segment="Mainboard", issue_size=120.0, listing_date=today - timedelta(days=31), issue_date=today - timedelta(days=31))
    db.add(ipo_31d)

    # 3. Listed in 2025
    c_2025 = Company(name="Co 2025 Listed", slug="co-2025-listed", sector="Energy")
    db.add(c_2025); db.flush()
    ipo_2025 = IPO(company_id=c_2025.id, status="Listed", listing_segment="Mainboard", issue_size=250.0, listing_date=date(2025, 6, 15), issue_date=date(2025, 6, 15))
    db.add(ipo_2025)

    # 4. Listed in 2024
    c_2024 = Company(name="Co 2024 Listed", slug="co-2024-listed", sector="Consumer")
    db.add(c_2024); db.flush()
    ipo_2024 = IPO(company_id=c_2024.id, status="Listed", listing_segment="Mainboard", issue_size=300.0, listing_date=date(2024, 11, 10), issue_date=date(2024, 11, 10))
    db.add(ipo_2024)

    db.commit()

    # Query default feed
    res = client.get("/api/v1/ipos")
    assert res.status_code == 200
    feed_items = res.json()["items"]
    feed_ids = [item["id"] for item in feed_items]
    listed_feed_items = [item for item in feed_items if item["status"] == "Listed"]

    # Assert 1: 5 days ago appears
    assert ipo_5d.id in feed_ids
    assert any(item["id"] == ipo_5d.id for item in listed_feed_items)

    # Assert 2: 31 days ago does NOT appear
    assert ipo_31d.id not in feed_ids

    # Assert 3: 2025 does NOT appear
    assert ipo_2025.id not in feed_ids

    # Assert 4: 2024 does NOT appear
    assert ipo_2024.id not in feed_ids

    # Assert 6: Historical Listed IPOs remain accessible via explicit status filter and direct ID
    res_direct_2024 = client.get(f"/api/v1/ipos/{ipo_2024.id}")
    assert res_direct_2024.status_code == 200
    assert res_direct_2024.json()["name"] == "Co 2024 Listed"

    res_direct_2025 = client.get(f"/api/v1/ipos/{ipo_2025.id}")
    assert res_direct_2025.status_code == 200
    assert res_direct_2025.json()["name"] == "Co 2025 Listed"

    res_filter = client.get("/api/v1/ipos?status_filter=Listed&page_size=50")
    assert res_filter.status_code == 200
    filter_ids = [item["id"] for item in res_filter.json()["items"]]
    assert ipo_2024.id in filter_ids
    assert ipo_2025.id in filter_ids
    assert ipo_31d.id in filter_ids
    assert ipo_5d.id in filter_ids

    # Assert 5: If zero recent Listed IPOs, default feed returns exactly ZERO Listed records
    # Remove the 5-day IPO to leave zero recent Listed records
    db.delete(ipo_5d)
    db.commit()

    res_zero = client.get("/api/v1/ipos")
    assert res_zero.status_code == 200
    zero_feed_listed = [item for item in res_zero.json()["items"] if item["status"] == "Listed"]
    assert len(zero_feed_listed) == 0, "When zero recent Listed IPOs exist, feed must return zero Listed records without fallback"

    db.close()


def test_recently_closed_boundary_conditions():
    """Prove:
    1. A Closed IPO 5 days ago appears in Recently Closed.
    2. A Closed IPO 31 days ago does not appear.
    3. A Closed IPO from 2025 does not appear.
    4. If zero recent Closed IPOs, API returns zero Closed records.
    5. Historical Closed IPOs remain accessible via explicit status filter and direct ID.
    """
    db = _fresh_db()
    today = date.today()

    # Closed 5 days ago
    c_5d = Company(name="Co 5d Closed", slug="co-5d-closed", sector="IT")
    db.add(c_5d); db.flush()
    ipo_5d = IPO(company_id=c_5d.id, status="Closed", listing_segment="Mainboard", issue_size=100.0, close_date=today - timedelta(days=5), issue_date=today - timedelta(days=5))
    db.add(ipo_5d)

    # Closed 31 days ago
    c_31d = Company(name="Co 31d Closed", slug="co-31d-closed", sector="Auto")
    db.add(c_31d); db.flush()
    ipo_31d = IPO(company_id=c_31d.id, status="Closed", listing_segment="Mainboard", issue_size=120.0, close_date=today - timedelta(days=31), issue_date=today - timedelta(days=31))
    db.add(ipo_31d)

    # Closed in 2025
    c_2025 = Company(name="Co 2025 Closed", slug="co-2025-closed", sector="Energy")
    db.add(c_2025); db.flush()
    ipo_2025 = IPO(company_id=c_2025.id, status="Closed", listing_segment="Mainboard", issue_size=250.0, close_date=date(2025, 5, 20), issue_date=date(2025, 5, 20))
    db.add(ipo_2025)

    db.commit()

    # Query default feed
    res = client.get("/api/v1/ipos")
    assert res.status_code == 200
    feed_items = res.json()["items"]
    feed_ids = [item["id"] for item in feed_items]

    # Assert 1: 5 days ago appears
    assert ipo_5d.id in feed_ids

    # Assert 2: 31 days ago does not appear
    assert ipo_31d.id not in feed_ids

    # Assert 3: 2025 does not appear
    assert ipo_2025.id not in feed_ids

    # Direct ID works
    res_direct = client.get(f"/api/v1/ipos/{ipo_2025.id}")
    assert res_direct.status_code == 200
    assert res_direct.json()["name"] == "Co 2025 Closed"

    # Status filter works
    res_filter = client.get("/api/v1/ipos?status_filter=Closed&page_size=50")
    assert res_filter.status_code == 200
    filter_ids = [item["id"] for item in res_filter.json()["items"]]
    assert ipo_2025.id in filter_ids
    assert ipo_31d.id in filter_ids
    assert ipo_5d.id in filter_ids

    # If zero recent Closed IPOs, return zero Closed records
    db.delete(ipo_5d)
    # Also delete any other Closed records that might be recent from seed
    for c_ipo in db.scalars(select(IPO).where(IPO.status == "Closed", IPO.close_date >= today - timedelta(days=30))).all():
        db.delete(c_ipo)
    db.commit()

    res_zero = client.get("/api/v1/ipos")
    assert res_zero.status_code == 200
    zero_feed_closed = [item for item in res_zero.json()["items"] if item["status"] == "Closed"]
    assert len(zero_feed_closed) == 0, "When zero recent Closed IPOs exist, feed must return zero Closed records without fallback"

    db.close()


def test_api_dynamic_lifecycle_overrides_stale_db_status():
    """Verify API read paths derive status from dates and never expose stale stored DB status."""
    db = _fresh_db()
    today = date.today()

    # Create company & IPO with STALE status in database:
    # Stored status is "Ongoing", but close_date passed yesterday and listing_date is next week.
    stale_company = Company(
        name="Stale Ongoing Corp",
        slug="stale-ongoing-corp",
        sector="Technology",
        exchange="NSE / BSE",
        description="A company whose DB status is stale Ongoing",
    )
    db.add(stale_company)
    db.flush()

    stale_ipo = IPO(
        company_id=stale_company.id,
        status="Ongoing",  # Intentionally stale in DB
        listing_segment="Mainboard",
        issue_size=100.0,
        price_low=50.0,
        price_high=60.0,
        open_date=today - timedelta(days=5),
        close_date=today - timedelta(days=1),  # Bidding closed yesterday
        listing_date=today + timedelta(days=5),  # Listing next week
        data_source="test",
    )
    db.add(stale_ipo)
    db.commit()

    # 1. Direct Detail endpoint: /api/v1/ipos/{id}
    res_detail = client.get(f"/api/v1/ipos/{stale_ipo.id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["status"] == "Closed", "Detail endpoint must return effective status 'Closed', not stale 'Ongoing'"

    # 2. Main list endpoint: /api/v1/ipos
    res_list = client.get(f"/api/v1/ipos?q=Stale+Ongoing")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "Closed", "List endpoint must return effective status 'Closed'"

    # 3. Global search: /api/v1/search
    res_search = client.get(f"/api/v1/search?q=Stale+Ongoing")
    assert res_search.status_code == 200
    search_items = res_search.json()["items"]
    assert len(search_items) == 1
    assert search_items[0]["status"] == "Closed", "Search endpoint must return effective status 'Closed'"

    # 4. Summary endpoint: /api/v1/ipos/summary
    res_summary = client.get("/api/v1/ipos/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["closed"] >= 1

    db.close()


def test_api_listed_when_listing_date_passed():
    """Verify IPO with passed listing date dynamically returns 'Listed' even if DB says 'Closed'."""
    db = _fresh_db()
    today = date.today()

    comp = Company(
        name="Stale Closed Corp",
        slug="stale-closed-corp",
        sector="Technology",
        exchange="NSE / BSE",
    )
    db.add(comp)
    db.flush()

    ipo = IPO(
        company_id=comp.id,
        status="Closed",  # Stale in DB
        listing_segment="Mainboard",
        issue_size=200.0,
        price_low=100.0,
        price_high=110.0,
        open_date=today - timedelta(days=20),
        close_date=today - timedelta(days=15),
        listing_date=today - timedelta(days=1),  # Listed yesterday
        data_source="test",
    )
    db.add(ipo)
    db.commit()

    res = client.get(f"/api/v1/ipos/{ipo.id}")
    assert res.status_code == 200
    assert res.json()["status"] == "Listed", "Must evaluate to Listed"

    db.close()


def test_api_future_open_and_current_window():
    """Verify future open date evaluates to Upcoming and current window evaluates to Ongoing."""
    db = _fresh_db()
    today = date.today()

    c1 = Company(name="Future Open Corp", slug="future-open-corp", sector="Finance")
    c2 = Company(name="Current Window Corp", slug="current-window-corp", sector="Finance")
    db.add_all([c1, c2])
    db.flush()

    # DB has stale "Ongoing" for future open
    ipo_future = IPO(
        company_id=c1.id,
        status="Ongoing",
        open_date=today + timedelta(days=4),
        close_date=today + timedelta(days=7),
        issue_size=100.0, price_low=50.0, price_high=60.0,
        data_source="test",
    )
    # DB has stale "Upcoming" for active bidding
    ipo_current = IPO(
        company_id=c2.id,
        status="Upcoming",
        open_date=today - timedelta(days=1),
        close_date=today + timedelta(days=1),
        issue_size=100.0, price_low=50.0, price_high=60.0,
        data_source="test",
    )
    db.add_all([ipo_future, ipo_current])
    db.commit()

    res_f = client.get(f"/api/v1/ipos/{ipo_future.id}")
    assert res_f.json()["status"] == "Upcoming"

    res_c = client.get(f"/api/v1/ipos/{ipo_current.id}")
    assert res_c.json()["status"] == "Ongoing"

    db.close()


def test_sync_detects_date_change_without_status_change():
    """Verify sync._needs_update detects date changes even when status string remains unchanged."""
    from app.services.sync import _needs_update
    from app.providers import NormalizedIPO

    ipo = IPO(
        status="Ongoing",
        open_date=date(2026, 9, 9),
        close_date=date(2026, 9, 11),
        listing_date=date(2026, 9, 17),
        price_low=100.0,
        price_high=110.0,
        issue_size=500.0,
    )

    # Record with identical status, price, size, but close_date extended to 2026-09-12
    rec = NormalizedIPO(
        name="Test Corp",
        slug="test-corp",
        status="Ongoing",
        open_date="2026-09-09",
        close_date="2026-09-12",  # Date changed!
        listing_date="2026-09-17",
        price_low=100.0,
        price_high=110.0,
        issue_size_crore=500.0,
    )

    assert _needs_update(ipo, rec) is True, "Sync must detect provider date revisions even when status is unchanged"

    # When all dates and values match, _needs_update must return False
    rec_matching = NormalizedIPO(
        name="Test Corp",
        slug="test-corp",
        status="Ongoing",
        open_date="2026-09-09",
        close_date="2026-09-11",
        listing_date="2026-09-17",
        price_low=100.0,
        price_high=110.0,
        issue_size_crore=500.0,
    )
    assert _needs_update(ipo, rec_matching) is False


def test_reconcile_db_lifecycles_startup():
    """Verify reconcile_db_lifecycles reconciles stored database rows in batch."""
    from app.lifecycle import reconcile_db_lifecycles
    db = _fresh_db()
    today = date.today()

    comp = Company(name="Reconcile Test Corp", slug="reconcile-test-corp", sector="Tech")
    db.add(comp)
    db.flush()

    # DB stored as "Ongoing", but close_date is 2 days ago
    ipo = IPO(
        company_id=comp.id,
        status="Ongoing",
        open_date=today - timedelta(days=5),
        close_date=today - timedelta(days=2),
        listing_date=today + timedelta(days=4),
        issue_size=100.0, price_low=50.0, price_high=60.0,
        data_source="test",
    )
    db.add(ipo)
    db.commit()

    updated = reconcile_db_lifecycles(db, reference_date=today)
    assert updated >= 1

    # Reload from DB
    reloaded = db.get(IPO, ipo.id)
    assert reloaded.status == "Closed"

    db.close()

