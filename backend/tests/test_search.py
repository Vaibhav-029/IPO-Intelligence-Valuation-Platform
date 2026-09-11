import pytest
from fastapi.testclient import TestClient
from app.main import app, get_db
from app.db import Base, engine
from app.seed import seed_demo_data


@pytest.fixture(scope="module")
def client():
    # Setup fresh database with seed demo data including live feed
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db, include_live=True)
    
    # Ensure at least one Document with type RHP exists for filing metadata search testing
    from app.models import Company, Document, IPO
    from sqlalchemy import select
    swiggy = db.scalar(select(Company).where(Company.slug == "swiggy"))
    if swiggy and swiggy.ipos:
        ipo = swiggy.ipos[0]
        doc = Document(
            company_id=swiggy.id,
            ipo_id=ipo.id,
            type="RHP",
            filename="swiggy-rhp-prospectus.pdf",
            storage_url="https://example.com/swiggy-rhp.pdf",
            checksum="swiggy-rhp-test-checksum",
            processing_status="completed",
        )
        db.add(doc)
        db.commit()
    db.close()
    return TestClient(app)


def test_search_empty_and_whitespace(client):
    resp = client.get("/api/v1/search?q=")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0

    resp_spaces = client.get("/api/v1/search?q=   ")
    assert resp_spaces.status_code == 200
    assert resp_spaces.json()["items"] == []


def test_search_exact_and_partial_company(client):
    # Partial query
    resp = client.get("/api/v1/search?q=Swig")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert "Swiggy" in item["name"]
    assert item["slug"] == "swiggy"
    assert item["id"] is not None
    assert item["status"] in ["Ongoing", "Upcoming", "Closed", "Listed"]
    assert item["listing_segment"] in ["Mainboard", "SME"]

    # Exact query
    resp_exact = client.get("/api/v1/search?q=Swiggy")
    assert resp_exact.status_code == 200
    exact_data = resp_exact.json()
    assert exact_data["total"] >= 1
    assert exact_data["items"][0]["name"] == "Swiggy"


def test_search_case_insensitivity(client):
    resp_lower = client.get("/api/v1/search?q=swiggy")
    resp_upper = client.get("/api/v1/search?q=SWIGGY")
    resp_mixed = client.get("/api/v1/search?q=SwIgGy")

    assert resp_lower.status_code == 200
    assert resp_upper.status_code == 200
    assert resp_mixed.status_code == 200

    items_lower = resp_lower.json()["items"]
    items_upper = resp_upper.json()["items"]
    items_mixed = resp_mixed.json()["items"]

    assert len(items_lower) == len(items_upper) == len(items_mixed)
    assert items_lower[0]["id"] == items_upper[0]["id"] == items_mixed[0]["id"]


def test_search_sector_matching(client):
    resp = client.get("/api/v1/search?q=Technology")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # Check that matched items either contain Technology in sector or name
    for it in data["items"]:
        match = "technology" in (it["sector"] or "").lower() or "technology" in it["name"].lower()
        assert match


def test_search_filing_metadata(client):
    # Searching RHP matches IPOs with RHP filings
    resp = client.get("/api/v1/search?q=RHP")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # At least one item has filing_type RHP or has_filing True
    assert any(it.get("has_filing") or it.get("filing_type") == "RHP" for it in data["items"])


def test_search_bounded_limit(client):
    resp_limit_2 = client.get("/api/v1/search?q=a&limit=2")
    assert resp_limit_2.status_code == 200
    assert len(resp_limit_2.json()["items"]) <= 2

    # Verify clamp to max 20 even if high limit passed
    resp_limit_high = client.get("/api/v1/search?q=a&limit=100")
    assert resp_limit_high.status_code == 200
    assert len(resp_limit_high.json()["items"]) <= 20


def test_search_no_results(client):
    resp = client.get("/api/v1/search?q=NonExistentCompanyXYZ999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_search_safe_query_handling(client):
    # Injection strings, SQL characters, special regex characters
    test_queries = [
        "' OR '1'='1",
        "'; DROP TABLE companies; --",
        "<script>alert('xss')</script>",
        "%%%",
        "\"\"\"",
        "\\",
        "!@#$%^&*()_+",
    ]
    for q in test_queries:
        resp = client.get(f"/api/v1/search?q={q}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
