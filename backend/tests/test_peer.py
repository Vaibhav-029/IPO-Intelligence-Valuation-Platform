import pytest
from datetime import date
from starlette.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Company, IPO, Peer, ValuationMetric, FinancialPeriod, FinancialMetric
from app.main import app
from app.db import Base, engine, get_db

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

@pytest.fixture
def client():
    return TestClient(app)

def test_peer_comparison_api(client: TestClient, db_session: Session):
    # Setup target
    target = Company(name="Target IPO", slug="target-ipo", sector="Technology")
    db_session.add(target)
    db_session.commit()
    
    ipo = IPO(company_id=target.id, status="Upcoming", price_low=100, price_high=120, post_issue_shares=1000000)
    db_session.add(ipo)
    db_session.commit()
    
    fp_target = FinancialPeriod(company_id=target.id, period_type="Annual", period_end=date(2023, 3, 31), fiscal_year="FY23")
    db_session.add(fp_target)
    db_session.commit()
    
    fm_target = FinancialMetric(period_id=fp_target.id, revenue=100, pat=20, ebitda=30)
    db_session.add(fm_target)
    db_session.commit()
    
    # Setup peers
    p1 = Company(name="Peer 1", slug="peer-1", sector="Technology")
    p2 = Company(name="Peer 2", slug="peer-2", sector="Technology")
    p3 = Company(name="Peer 3", slug="peer-3", sector="Technology")
    p4 = Company(name="Peer 4", slug="peer-4", sector="Finance") # Different sector
    db_session.add_all([p1, p2, p3, p4])
    db_session.commit()
    
    # Active peers
    db_session.add(Peer(company_id=target.id, peer_company_id=p1.id, active=True))
    db_session.add(Peer(company_id=target.id, peer_company_id=p2.id, active=True))
    db_session.add(Peer(company_id=target.id, peer_company_id=p3.id, active=False)) # Inactive
    db_session.commit()
    
    # Peer valuations
    db_session.add(ValuationMetric(company_id=p1.id, date=date(2023, 10, 1), market_cap=5000, pe=25, ps=5, ev_ebitda=15, ev_sales=6, context="CURRENT_MARKET"))
    db_session.add(ValuationMetric(company_id=p2.id, date=date(2023, 10, 2), market_cap=6000, pe=35, ps=None, ev_ebitda=None, ev_sales=None, context="CURRENT_MARKET")) # Missing some
    db_session.commit()
    
    # Call API
    response = client.get(f"/api/v1/ipos/{ipo.id}/peers")
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "target" in data
    assert "peers" in data
    assert "peer_statistics" in data
    assert "comparison" in data
    
    # Check peers
    assert len(data["peers"]) == 2
    peer_names = [p["name"] for p in data["peers"]]
    assert "Peer 1" in peer_names
    assert "Peer 2" in peer_names
    assert "Peer 3" not in peer_names # Inactive
    assert "Peer 4" not in peer_names # Not paired
    
    assert data["peers"][0]["context"] == "CURRENT_MARKET"
    
    # Check statistics
    stats = data["peer_statistics"]
    assert stats["pe"]["median"] == 30.0 # median(25, 35)
    assert stats["pe"]["observations"] == 2
    assert stats["ps"]["median"] == 5.0 # median(5) - ignores NULL
    assert stats["ps"]["observations"] == 1
    assert stats["ev_ebitda"]["median"] == 15.0
    
    # Check target
    t = data["target"]
    assert t["name"] == "Target IPO"
    assert t["context"] == "IPO_AT_ISSUE"
    assert "lower_band" in t
    assert "upper_band" in t
    
    # Check comparison
    comp = data["comparison"]
    assert "lower_band" in comp
    assert "upper_band" in comp
    
    # Target mcap low = 100 * 1m / 10m = 10cr. PAT = 20cr. PE = 10/20 = 0.5. PE peer median = 30. 
    # Premium = (0.5 / 30 - 1) * 100 = -98.33
    assert comp["lower_band"]["pe"] == -98.33

def test_peer_statistics_zero_handling():
    from app.analytics.financials import calculate_peer_statistics, calculate_band_comparison
    peers = [
        {"pe": 0, "ps": 0, "ev_ebitda": 0, "ev_sales": 0},
        {"pe": 0, "ps": 0, "ev_ebitda": 0, "ev_sales": 0}
    ]
    stats = calculate_peer_statistics(peers)
    assert stats["pe"]["median"] == 0
    
    lower_band = {"pe": 10, "ps": 1}
    upper_band = {"pe": 20, "ps": 2}
    
    comp = calculate_band_comparison(lower_band, upper_band, stats)
    assert comp["lower_band"]["pe"] is None # Avoid division by zero
    assert comp["upper_band"]["ps"] is None

def test_peer_seeding(db_session: Session):
    from app.seed import seed_demo_data
    
    db_session.execute(IPO.__table__.delete())
    db_session.execute(Company.__table__.delete())
    db_session.execute(Peer.__table__.delete())
    db_session.commit()
    
    # Seed data
    seed_demo_data(db_session)
    
    # Check peers
    peers = db_session.execute(select(Peer)).scalars().all()
    assert len(peers) > 0
    
    for peer in peers:
        c1 = db_session.get(Company, peer.company_id)
        c2 = db_session.get(Company, peer.peer_company_id)
        assert c1.id != c2.id # No self peers
        assert c1.sector == c2.sector # Same sector
        assert c1.sector is not None
        assert peer.active == True
