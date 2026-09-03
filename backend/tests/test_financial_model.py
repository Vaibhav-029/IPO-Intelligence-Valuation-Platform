from datetime import date
from sqlalchemy import select
from app.db import Base, engine, get_db
from app.models import Company, FinancialPeriod, FinancialMetric
from app.seed import seed_demo_data

def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db)
    return db

def test_period_semantics():
    from app.seed import _normalize_period
    assert _normalize_period("FY22") == ("Annual", None)
    assert _normalize_period("Q1FY23") == ("Interim", "Q1")
    assert _normalize_period("H2FY23") == ("Interim", "H2")
    assert _normalize_period("9MFY24") == ("Interim", "9M")

    db_session = _fresh_db()
    company = Company(name="Test Corp", slug="test-corp", sector="Tech", exchange="NSE")
    db_session.add(company)
    db_session.flush()

    # Annual period
    annual_period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2024, 3, 31),
        period_type="Annual",
        fiscal_year="FY24"
    )
    db_session.add(annual_period)
    
    # Interim period
    interim_period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2023, 12, 31),
        period_type="Interim",
        interim_period="Q3",
        fiscal_year="FY24"
    )
    db_session.add(interim_period)
    db_session.commit()

    periods = db_session.scalars(select(FinancialPeriod).where(FinancialPeriod.company_id == company.id).order_by(FinancialPeriod.period_end)).all()
    assert len(periods) == 2
    assert periods[0].period_type == "Interim"
    assert periods[0].interim_period == "Q3"
    assert periods[1].period_type == "Annual"
    assert periods[1].interim_period is None

def test_financial_metric_nulls_and_provenance():
    db_session = _fresh_db()
    company = Company(name="Test Corp 2", slug="test-corp-2", sector="Tech", exchange="NSE")
    db_session.add(company)
    db_session.flush()

    period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2024, 3, 31),
        period_type="Annual",
        fiscal_year="FY24"
    )
    db_session.add(period)
    db_session.flush()

    # Explicitly test NULL vs 0.0
    metric = FinancialMetric(
        period_id=period.id,
        revenue=100.50,
        ebitda=None,  # Not reported
        pat=0.0,      # Explicit zero
        source_type="RHP",
        source_reference="Page 123",
        derived_fields={"ebitda": True}
    )
    db_session.add(metric)
    db_session.commit()

    fetched = db_session.scalar(select(FinancialMetric).where(FinancialMetric.period_id == period.id))
    assert fetched.revenue == 100.50
    assert fetched.ebitda is None
    assert fetched.pat == 0.0
    assert fetched.source_type == "RHP"
    assert fetched.source_reference == "Page 123"
    assert fetched.derived_fields == {"ebitda": True}
