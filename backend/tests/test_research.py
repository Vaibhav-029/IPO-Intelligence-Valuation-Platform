"""Tests for the research layer — context gathering and deterministic fallback."""
from app.db import Base, engine, get_db
from app.seed import seed_demo_data
from app.services.research import _gather_context, _deterministic_fallback, answer_question
from app.models import Company, IPO, Document, Source
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import json
from unittest.mock import patch, MagicMock


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

    # Financials series might not be populated in legacy fallback context
    # but let's check revenue
    assert context["financials"]["revenue_cagr_2y_pct"] is not None

    # Tool trace has all 6 tool names
    assert len(trace) == 6
    assert "get_ipo_profile" in trace
    assert "get_peers" in trace
    assert "get_risks" in trace
    assert "get_financials" in trace
    assert "search_filing" in trace

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
    
    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = False
        mock_get_llm.return_value = mock_llm
        
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


def test_answer_question_valid_llm_json():
    """Test valid JSON output with valid citations from LLM."""
    db, ipo = _setup()
    
    # Inject a fake source into the DB for retrieval
    doc = Document(company_id=ipo.company_id, filename="test.pdf", user_id=1, is_public=True, storage_url="url", checksum="chk")
    db.add(doc)
    db.commit()
    
    src = Source(document_id=doc.id, page=1, chunk_id="testchunk", source_text_hash="testhash", text="The company has a huge market share.", is_empty=False, confidence=1.0)
    db.add(src)
    db.commit()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            # Round 1: Call search_filing
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {
                            "name": "search_filing",
                            "arguments": json.dumps({"query": "huge market share"})
                        }
                    }
                ]
            },
            # Round 2: Final answer
            {
                "content": json.dumps({
                    "answer": "The company dominates.",
                    "claims": [
                        {
                            "text": "Huge market share.",
                            "citations": [{"source_id": src.id, "document_id": doc.id, "page": 1}]
                        }
                    ]
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm
        
        result = answer_question(db, ipo, "huge market share")
        
        assert result["mode"] == "llm"
        assert result["answer"] == "The company dominates."
        assert len(result["claims"]) == 1
        assert result["claims"][0]["citations"][0]["source_id"] == src.id
        assert "search_filing" in result["tool_trace"]
        
    db.close()


def test_answer_question_invalid_citation_stripped():
    db, ipo = _setup()
    
    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            # Round 1: Call search_filing
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {
                            "name": "search_filing",
                            "arguments": json.dumps({"query": "huge market share"})
                        }
                    }
                ]
            },
            # Round 2: Final answer with fake citations
            {
                "content": json.dumps({
                    "answer": "The company dominates.",
                    "claims": [
                        {
                            "text": "Huge market share.",
                            "citations": [{"source_id": 9999, "document_id": 9999, "page": 1}]
                        }
                    ]
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm
        
        result = answer_question(db, ipo, "huge market share")
        
        assert result["mode"] == "llm"
        assert result["answer"] == "The company dominates."
        assert len(result["claims"]) == 0
        
    db.close()


def test_answer_question_malformed_json_fallback():
    """Test that malformed JSON triggers deterministic fallback safely."""
    db, ipo = _setup()
    
    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.return_value = {"content": "This is not JSON", "tool_calls": []}
        mock_get_llm.return_value = mock_llm
        
        result = answer_question(db, ipo, "valuation")
        
        # Should fallback
        assert result["mode"] == "deterministic"
        assert result["confidence"] == "low"
        assert len(result["claims"]) == 0
        
    db.close()


def test_research_sessions_crud_and_isolation():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_token, hash_password
    from app.models import User

    db, ipo = _setup()
    
    # Create User A and User B
    user_a = User(email="analyst_a@example.com", password_hash=hash_password("Pass123!"))
    user_b = User(email="analyst_b@example.com", password_hash=hash_password("Pass123!"))
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    
    from datetime import timedelta
    token_a = create_token(user_a, "access", timedelta(hours=1))
    token_b = create_token(user_b, "access", timedelta(hours=1))
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client = TestClient(app)

    # 1. User A creates session
    res = client.post("/api/v1/research/sessions", json={"ipo_id": ipo.id, "title": "Desk Note 1"}, headers=headers_a)
    assert res.status_code == 201
    sess_id = res.json()["id"]

    # 2. User A posts message (mock answer_question to avoid external LLM call)
    with patch("app.main.answer_question") as mock_answer:
        mock_answer.return_value = {
            "answer": "Mock financial analysis",
            "tool_trace": ["filing_search", "financial_metrics"],
            "claims": [{"text": "Revenue is 500Cr", "citations": [{"document_id": 1, "page": 10, "section": "Fin", "excerpt": "500Cr"}]}],
            "confidence": "high",
            "mode": "deterministic"
        }
        res_msg = client.post(f"/api/v1/research/sessions/{sess_id}/messages", json={"content": "What is revenue?"}, headers=headers_a)
        assert res_msg.status_code == 201
        assert res_msg.json()["answer"] == "Mock financial analysis"

    # 3. User A lists sessions -> should include this session
    res_list_a = client.get("/api/v1/research/sessions", headers=headers_a)
    assert res_list_a.status_code == 200
    sessions_a = res_list_a.json()
    assert any(s["id"] == sess_id for s in sessions_a)

    # 4. User A gets session details -> should have user and assistant messages
    res_detail_a = client.get(f"/api/v1/research/sessions/{sess_id}", headers=headers_a)
    assert res_detail_a.status_code == 200
    detail_data = res_detail_a.json()
    assert detail_data["id"] == sess_id
    assert len(detail_data["messages"]) == 2

    # 5. Isolation: User B lists sessions -> should NOT see User A's session
    res_list_b = client.get("/api/v1/research/sessions", headers=headers_b)
    assert res_list_b.status_code == 200
    assert not any(s["id"] == sess_id for s in res_list_b.json())

    # 6. Isolation: User B tries to view User A's session -> 404
    res_detail_b = client.get(f"/api/v1/research/sessions/{sess_id}", headers=headers_b)
    assert res_detail_b.status_code == 404

    # 7. Isolation: User B tries to delete User A's session -> 404
    res_del_b = client.delete(f"/api/v1/research/sessions/{sess_id}", headers=headers_b)
    assert res_del_b.status_code == 404

    # 8. User A deletes session -> 204
    res_del_a = client.delete(f"/api/v1/research/sessions/{sess_id}", headers=headers_a)
    assert res_del_a.status_code == 204

    # 9. Session is now gone
    res_list_after = client.get("/api/v1/research/sessions", headers=headers_a)
    assert not any(s["id"] == sess_id for s in res_list_after.json())
    res_get_after = client.get(f"/api/v1/research/sessions/{sess_id}", headers=headers_a)
    assert res_get_after.status_code == 404

    db.close()


def test_peer_comparison_all_peers_pe_null():
    """Regression A: Peer list exists but all peer P/E values are NULL (e.g. Swiggy for Rentomojo).
    Must not raise StatisticsError, peer median P/E must be None, and context must generate cleanly.
    """
    from datetime import date
    from app.services.research import peer_comparison
    from app.models import Peer, ValuationMetric
    db, ipo = _setup()

    # Create target company and peer with NULL P/E
    target_comp = Company(name="Target Tech Corp", slug="target-tech-corp-test", sector="Tech")
    peer_comp = Company(name="Loss Making Peer", slug="loss-making-peer-test", sector="Tech")
    db.add_all([target_comp, peer_comp])
    db.flush()

    target_ipo = IPO(
        company_id=target_comp.id,
        status="Closed",
        issue_size=500.0,
        price_low=100.0,
        price_high=110.0,
    )
    db.add(target_ipo)
    db.flush()

    # Peer valuation exists, but pe is None (loss-making)
    val_peer = ValuationMetric(company_id=peer_comp.id, date=date(2026, 9, 1), pe=None, ps=5.0)
    val_target = ValuationMetric(company_id=target_comp.id, date=date(2026, 9, 1), pe=25.0, ps=4.0)
    peer_link = Peer(company_id=target_comp.id, peer_company_id=peer_comp.id, active=True)
    db.add_all([val_peer, val_target, peer_link])
    db.commit()

    # Test peer_comparison directly
    comp_res = peer_comparison(db, target_comp.id)
    assert comp_res["peer_count"] == 1
    assert comp_res["peer_median_pe"] is None
    assert comp_res["pe_premium_discount_pct"] is None
    assert comp_res["company_pe"] == 25.0

    # Test _gather_context does not crash and includes peer_comparison
    context, trace = _gather_context(db, target_ipo, "is the valuation good?")
    assert "peer_comparison" in context
    assert context["peer_comparison"]["peer_median_pe"] is None
    assert "get_peers" in trace

    db.close()


def test_company_snapshot_missing_filing_metrics():
    """Regression B: Financial metric has valid revenue but ebitda=None and pat=None.
    company_snapshot must succeed without TypeError and preserve None for missing fields.
    """
    from datetime import date
    from app.services.research import company_snapshot
    from app.models import FinancialPeriod, FinancialMetric
    db, _ = _setup()

    comp = Company(name="Sparse Metrics Corp", slug="sparse-metrics-corp-test", sector="Industrial")
    db.add(comp)
    db.flush()

    ipo = IPO(
        company_id=comp.id,
        status="Ongoing",
        issue_size=300.0,
        price_low=50.0,
        price_high=55.0,
    )
    db.add(ipo)
    db.flush()

    period = FinancialPeriod(company_id=comp.id, fiscal_year="FY2025", period_end=date(2025, 3, 31))
    db.add(period)
    db.flush()

    metric = FinancialMetric(period_id=period.id, revenue=1200.0, ebitda=None, pat=None)
    db.add(metric)
    db.commit()

    snapshot = company_snapshot(db, ipo)
    assert snapshot["latest_revenue_crore"] == 1200.0
    assert snapshot["latest_ebitda_crore"] is None
    assert snapshot["latest_pat_crore"] is None
    assert snapshot["ebitda_margin_pct"] is None

    # Series also preserves None cleanly
    assert len(snapshot["financials_series"]) == 1
    assert snapshot["financials_series"][0]["revenue_crore"] == 1200.0
    assert snapshot["financials_series"][0]["ebitda_crore"] is None
    assert snapshot["financials_series"][0]["pat_crore"] is None
    assert snapshot["financials_series"][0]["ebitda_margin_pct"] is None

    db.close()


def test_research_question_rentomojo_endpoint():
    """Regression C: Research message for Rentomojo ('is the valuation good?') returns HTTP 201/200,
    never fails with 500 / 'Failed to fetch', and generates answer with tool trace.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_token, hash_password
    from app.models import User, Peer, ValuationMetric
    from datetime import timedelta, date
    db, _ = _setup()

    user = User(email="rentomojo_analyst@example.com", password_hash=hash_password("Pass123!"))
    db.add(user)
    
    # Check if Rentomojo / Swiggy exist or create them
    rento_comp = db.scalar(select(Company).where(Company.slug == "rentomojo"))
    if not rento_comp:
        rento_comp = Company(name="Rentomojo", slug="rentomojo-test", sector="Consumer Technology")
        db.add(rento_comp)
        db.flush()

    swiggy_comp = db.scalar(select(Company).where(Company.slug == "swiggy"))
    if not swiggy_comp:
        swiggy_comp = Company(name="Swiggy", slug="swiggy-test", sector="Consumer Technology")
        db.add(swiggy_comp)
        db.flush()

    rento_ipo = db.scalar(select(IPO).where(IPO.company_id == rento_comp.id))
    if not rento_ipo:
        rento_ipo = IPO(company_id=rento_comp.id, status="Closed", issue_size=1255.6, price_low=100.0, price_high=110.0)
        db.add(rento_ipo)
        db.flush()

    db.add_all([
        ValuationMetric(company_id=rento_comp.id, date=date(2026, 9, 1), pe=None, ps=3.5),
        ValuationMetric(company_id=swiggy_comp.id, date=date(2026, 9, 1), pe=None, ps=4.0),
        Peer(company_id=rento_comp.id, peer_company_id=swiggy_comp.id, active=True),
    ])
    db.commit()

    token = create_token(user, "access", timedelta(hours=1))
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(app)

    # 1. Create session
    res_sess = client.post("/api/v1/research/sessions", json={"ipo_id": rento_ipo.id, "title": "is the valuation good?"}, headers=headers)
    assert res_sess.status_code == 201
    sess_id = res_sess.json()["id"]

    # 2. Send message
    res_msg = client.post(f"/api/v1/research/sessions/{sess_id}/messages", json={"content": "is the valuation good?"}, headers=headers)
    assert res_msg.status_code in (200, 201), f"Endpoint returned {res_msg.status_code}: {res_msg.text}"
    body = res_msg.json()
    assert "answer" in body and len(body["answer"]) > 0
    assert "tool_trace" in body
    assert isinstance(body["tool_trace"], list)

    db.close()


def test_research_question_karamtara_missing_metrics():
    """Regression D: Research question for an IPO with missing EBITDA/PAT (Karamtara scenario)
    succeeds without TypeError or 500 error.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_token, hash_password
    from app.models import User, FinancialPeriod, FinancialMetric
    from datetime import timedelta, date
    db, _ = _setup()

    user = User(email="karamtara_analyst@example.com", password_hash=hash_password("Pass123!"))
    db.add(user)

    karam_comp = Company(name="Karamtara Engineering", slug="karamtara-engineering-test", sector="Engineering")
    db.add(karam_comp)
    db.flush()

    karam_ipo = IPO(company_id=karam_comp.id, status="Closed", issue_size=750.0, price_low=80.0, price_high=85.0)
    db.add(karam_ipo)
    db.flush()

    # Add periods with missing ebitda and pat
    p1 = FinancialPeriod(company_id=karam_comp.id, fiscal_year="FY2025", period_end=date(2025, 3, 31))
    db.add(p1)
    db.flush()
    db.add(FinancialMetric(period_id=p1.id, revenue=3158.0, ebitda=None, pat=139.0))
    db.commit()

    token = create_token(user, "access", timedelta(hours=1))
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(app)

    # 1. Create session
    res_sess = client.post("/api/v1/research/sessions", json={"ipo_id": karam_ipo.id, "title": "Summarize the financial risks."}, headers=headers)
    assert res_sess.status_code == 201
    sess_id = res_sess.json()["id"]

    # 2. Send message
    res_msg = client.post(f"/api/v1/research/sessions/{sess_id}/messages", json={"content": "Summarize the financial risks."}, headers=headers)
    assert res_msg.status_code in (200, 201), f"Endpoint returned {res_msg.status_code}: {res_msg.text}"
    body = res_msg.json()
    assert "answer" in body and len(body["answer"]) > 0
    assert "key_metrics" in body

    db.close()


