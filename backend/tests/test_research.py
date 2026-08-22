"""Tests for the research layer — context gathering and deterministic fallback."""
from app.db import Base, engine, get_db
from app.seed import seed_demo_data
from app.services.research import _gather_context, _deterministic_fallback, answer_question
from app.models import Company, IPO
from sqlalchemy import select
from sqlalchemy.orm import joinedload


def _setup():
    """Fresh DB with seed data, return a db session and a loaded IPO."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db)
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).limit(1))
    return db, ipo


def test_gather_context_returns_all_tools():
    """_gather_context should return a dict with all 7 tool sections and a non-empty trace."""
    db, ipo = _setup()
    context, trace = _gather_context(db, ipo, "Why is this IPO expensive?")

    # All sections present
    assert "company_profile" in context
    assert "financials" in context
    assert "valuation" in context
    assert "peer_comparison" in context
    assert "risk_factors" in context
    assert "ipo_score" in context
    assert "filing_evidence" in context

    # Company profile has expected fields
    assert context["company_profile"]["name"] == ipo.company.name
    assert context["company_profile"]["sector"] == ipo.company.sector
    assert isinstance(context["company_profile"]["issue_size_crore"], float)

    # Financials series has entries
    assert len(context["financials"]["series"]) > 0
    assert context["financials"]["latest_revenue_crore"] is not None

    # Tool trace has all 6 tool names
    assert len(trace) == 6
    assert "get_company_profile" in trace
    assert "compare_peers" in trace
    assert "get_risk_factors" in trace
    assert "get_ipo_score" in trace
    assert "retrieve_filing_evidence" in trace

    db.close()


def test_deterministic_fallback_valuation():
    """Fallback mode should produce a valuation-relevant answer for valuation questions."""
    db, ipo = _setup()
    context, _ = _gather_context(db, ipo, "Is this IPO expensive?")
    answer = _deterministic_fallback(context, "Is this IPO expensive?")

    assert ipo.company.name in answer
    assert "P/E" in answer or "premium" in answer.lower() or "discount" in answer.lower()
    db.close()


def test_deterministic_fallback_growth():
    """Fallback mode should mention revenue/margin for growth questions."""
    db, ipo = _setup()
    context, _ = _gather_context(db, ipo, "How is revenue growth?")
    answer = _deterministic_fallback(context, "How is revenue growth?")

    assert "CAGR" in answer or "margin" in answer.lower()
    db.close()


def test_deterministic_fallback_risk():
    """Fallback mode should list risk factors for risk questions."""
    db, ipo = _setup()
    context, _ = _gather_context(db, ipo, "What are the major risks?")
    answer = _deterministic_fallback(context, "What are the major risks?")

    assert "risk" in answer.lower()
    db.close()


def test_answer_question_fallback_mode():
    """answer_question should work in deterministic fallback mode (no API key)."""
    db, ipo = _setup()
    result = answer_question(db, ipo, "Why is this IPO valued at a premium?")

    # Response has the expected shape
    assert "answer" in result
    assert "key_metrics" in result
    assert "claims" in result
    assert "confidence" in result
    assert "tool_trace" in result
    assert "mode" in result

    # Should be in deterministic mode (no API key configured)
    assert result["mode"] == "deterministic"
    assert result["confidence"] == "low"
    assert len(result["answer"]) > 20  # not empty
    assert len(result["tool_trace"]) >= 5  # used most tools

    db.close()
