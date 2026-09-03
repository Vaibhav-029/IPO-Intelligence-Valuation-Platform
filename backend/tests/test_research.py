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
