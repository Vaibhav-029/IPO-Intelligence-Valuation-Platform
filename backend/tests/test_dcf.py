from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest
from app.models import IPO, FinancialPeriod, FinancialMetric, Company
from app.main import app
from app.db import Base, engine, get_db
from datetime import date

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.rollback()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_run_dcf_math():
    from app.analytics.dcf import run_dcf
    
    # Hand calculated test:
    # base_rev = 1000
    # rev_growth = 0.10 -> year 1 rev = 1100
    # ebitda_margin = 0.20 -> ebitda = 220
    # da_pct = 0.05 -> da = 55
    # ebit = 220 - 55 = 165
    # tax = 0.25 -> tax = 41.25
    # capex_pct = 0.06 -> capex = 66
    # nwc_pct = 0.02 -> nwc = 22
    # FCFF = 165 * (1 - 0.25) + 55 - 66 - 22 = 123.75 + 55 - 66 - 22 = 90.75
    # Discount rate = 0.10 -> PV1 = 90.75 / 1.1 = 82.5
    
    res = run_dcf(
        base_revenue=1000,
        revenue_growth_rate=0.10,
        ebitda_margin=0.20,
        tax_rate=0.25,
        d_and_a_pct=0.05,
        capex_pct=0.06,
        nwc_pct=0.02,
        wacc=0.10,
        terminal_growth_rate=0.02,
        years=1
    )
    
    p = res["projections"][0]
    assert p["revenue"] == 1100
    assert p["ebitda"] == 220
    assert p["d_and_a"] == 55
    assert p["ebit"] == 165
    assert p["taxes"] == 41.25
    assert p["capex"] == 66
    assert p["change_in_nwc"] == 22
    assert p["fcff"] == 90.75
    assert p["present_value"] == 82.5
    
    # Terminal Value check
    # year 1 fcff = 90.75
    # next year fcff (for TV) = 90.75 * 1.02 = 92.565
    # TV = 92.565 / (0.10 - 0.02) = 1157.0625
    # PV(TV) = 1157.0625 / 1.1 = 1051.875
    
    assert abs(res["terminal_value"] - 1157.06) < 0.01
    assert abs(res["terminal_value_pv"] - 1051.88) < 0.01
    assert abs(res["enterprise_value"] - (82.5 + 1051.88)) < 0.01

def test_api_dcf_success(client: TestClient, db_session: Session):
    company = Company(name="DCF Test IPO", slug="dcf-test-ipo", sector="Technology")
    db_session.add(company)
    db_session.commit()
    
    ipo = IPO(
        company_id=company.id, pre_issue_shares=10000000, fresh_issue_shares=5000000, ofs_shares=0,
        price_low=100, price_high=120, status="Upcoming", data_source="mock"
    )
    db_session.add(ipo)
    db_session.commit()
    
    fp = FinancialPeriod(company_id=company.id, period_type="Annual", period_end=date(2023, 3, 31), fiscal_year="FY23")
    db_session.add(fp)
    db_session.commit()
    
    fm = FinancialMetric(period_id=fp.id, revenue=1000, total_debt=200, cash=50)
    db_session.add(fm)
    db_session.commit()
    
    payload = {
        "revenue_growth_rate": 0.15,
        "ebitda_margin": 0.20,
        "tax_rate": 0.25,
        "d_and_a_pct_of_revenue": 0.05,
        "capex_pct_of_revenue": 0.06,
        "change_in_nwc_pct_of_revenue": 0.10,
        "discount_rate": 0.12,
        "terminal_growth_rate": 0.05,
        "years": 5
    }
    
    res = client.post(f"/api/v1/ipos/{ipo.id}/dcf", json=payload)
    assert res.status_code == 200
    data = res.json()
    
    # 1. Input separation check
    assert data["inputs"]["historical"]["base_revenue"] == 1000
    assert data["inputs"]["historical"]["post_issue_shares"] == 15000000
    assert data["inputs"]["assumptions"]["revenue_growth_rate"] == 0.15
    
    # 2. Valuation calculation
    ev = data["valuation"]["enterprise_value"]
    assert ev > 0
    eq = data["valuation"]["equity_value"]
    assert eq == ev + 50 - 200
    
    ips = data["valuation"]["intrinsic_value_per_share"]
    assert ips == round((eq * 10000000) / 15000000, 2)
    
    # 3. Upside check
    assert data["valuation"]["implied_upside_pct_lower_band"] == round((ips / 100 - 1) * 100, 2)
    assert data["valuation"]["implied_upside_pct_upper_band"] == round((ips / 120 - 1) * 100, 2)
    
    # 4. Sensitivity check
    sens = data["sensitivity"]
    assert 12.0 in sens["wacc_values"]
    assert 5.0 in sens["terminal_growth_values"]
    assert len(sens["grid"]) == 5
    assert len(sens["grid"][0]) == 5
    
def test_api_dcf_missing_base_revenue(client: TestClient, db_session: Session):
    company = Company(name="Missing Rev IPO", slug="missing-rev-ipo", sector="Technology")
    db_session.add(company)
    db_session.commit()
    
    ipo = IPO(
        company_id=company.id,
        status="Upcoming", data_source="mock"
    )
    db_session.add(ipo)
    db_session.commit()
    
    # Add a period but NO revenue
    fp = FinancialPeriod(company_id=company.id, period_type="Annual", period_end=date(2023, 3, 31), fiscal_year="FY23")
    db_session.add(fp)
    db_session.commit()
    
    fm = FinancialMetric(period_id=fp.id, revenue=None)
    db_session.add(fm)
    db_session.commit()
    
    payload = {
        "revenue_growth_rate": 0.15,
        "ebitda_margin": 0.20,
        "tax_rate": 0.25,
        "d_and_a_pct_of_revenue": 0.05,
        "capex_pct_of_revenue": 0.06,
        "change_in_nwc_pct_of_revenue": 0.10,
        "discount_rate": 0.12,
        "terminal_growth_rate": 0.05
    }
    
    res = client.post(f"/api/v1/ipos/{ipo.id}/dcf", json=payload)
    assert res.status_code == 422
    assert "Base annual revenue is required" in res.json()["detail"]

def test_api_dcf_invalid_terminal_growth(client: TestClient, db_session: Session):
    company = Company(name="Test", slug="test-ipo", sector="Technology")
    db_session.add(company)
    db_session.commit()
    
    ipo = IPO(company_id=company.id, status="Upcoming", data_source="mock")
    db_session.add(ipo)
    db_session.commit()
    
    payload = {
        "revenue_growth_rate": 0.15,
        "ebitda_margin": 0.20,
        "tax_rate": 0.25,
        "d_and_a_pct_of_revenue": 0.05,
        "capex_pct_of_revenue": 0.06,
        "change_in_nwc_pct_of_revenue": 0.10,
        "discount_rate": 0.05,
        "terminal_growth_rate": 0.06 # > WACC
    }
    
    res = client.post(f"/api/v1/ipos/{ipo.id}/dcf", json=payload)
    assert res.status_code == 422
    assert "terminal_growth_rate must be less than discount_rate" in res.text

def test_calculate_sensitivity_matrix_null_cells():
    from app.analytics.dcf import calculate_sensitivity_matrix
    
    matrix = calculate_sensitivity_matrix(
        base_revenue=1000,
        revenue_growth_rate=0.1,
        ebitda_margin=0.2,
        tax_rate=0.25,
        d_and_a_pct=0.05,
        capex_pct=0.06,
        nwc_pct=0.02,
        base_wacc=0.06,
        base_terminal_growth=0.06,
        years=5,
        debt=0,
        cash=0,
        post_issue_shares=10000000
    )
    
    # base_wacc = 6%, base_tg = 6%
    # tg_steps = 5%, 5.5%, 6%, 6.5%, 7%
    # wacc_steps = 4%, 5%, 6%, 7%, 8%
    
    wacc_values = matrix["wacc_values"]
    assert wacc_values == [4.0, 5.0, 6.0, 7.0, 8.0]
    
    tg_values = matrix["terminal_growth_values"]
    assert tg_values == [5.0, 5.5, 6.0, 6.5, 7.0]
    
    grid = matrix["grid"]
    
    # Row 0: WACC=4%. For all TG (5% to 7%), WACC <= TG. So all should be None
    assert grid[0] == [None, None, None, None, None]
    
    # Row 2: WACC=6%. For TG=5%, 5.5%, WACC > TG (valid). For TG >= 6%, WACC <= TG (None)
    assert grid[2][0] is not None
    assert grid[2][1] is not None
    assert grid[2][2] is None
    assert grid[2][3] is None
    assert grid[2][4] is None
