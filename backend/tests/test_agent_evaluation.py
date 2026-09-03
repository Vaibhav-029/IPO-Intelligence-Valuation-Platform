import json
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db import Base, engine, get_db
from app.models import Company, Document, IPO, Source
from app.seed import seed_demo_data
from app.services.research import answer_question


def _setup():
    """Fresh DB with seed data, return a db session and a loaded IPO."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db)
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).limit(1))
    return db, ipo


def test_deterministic_claim_accepted():
    """Valid deterministic claim is accepted."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        responses = [
            # Round 1: Call get_financials
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {
                            "name": "get_financials",
                            "arguments": "{}"
                        }
                    }
                ]
            },
            # Round 2: Final answer with correct numeric match
            {
                "content": json.dumps({
                    "answer": "Revenue CAGR is high.",
                    "claims": [
                        {
                            "type": "deterministic_fact",
                            "text": "Revenue CAGR was 46.5%.",
                            "source": {
                                "tool": "get_financials",
                                "field": "revenue_cagr_2y_pct"
                            }
                        }
                    ]
                }),
                "tool_calls": []
            }
        ]
        mock_llm.generate_sync.side_effect = responses
        mock_get_llm.return_value = mock_llm

        # Since it's a mock, we don't know the exact seed CAGR, but if it's 46.46 it will match 46.5.
        # Wait, to be perfectly deterministic, we can just fetch the true value from snapshot:
        from app.services.research import company_snapshot
        snapshot = company_snapshot(db, ipo)
        true_cagr = snapshot["revenue_cagr_2y_pct"]
        
        # Override the mock round 2 with the exact true value
        responses[1]["content"] = json.dumps({
            "answer": "Revenue CAGR is high.",
            "claims": [
                {
                    "type": "deterministic_fact",
                    "text": f"Revenue CAGR was {round(true_cagr, 1)}%.",
                    "source": {
                        "tool": "get_financials",
                        "field": "revenue_cagr_2y_pct"
                    }
                }
            ]
        })

        result = answer_question(db, ipo, "What is the CAGR?")

        assert result["mode"] == "llm"
        assert len(result["claims"]) == 1
        assert result["claims"][0]["type"] == "deterministic_fact"
        assert "get_financials" in result["tool_trace"]

    db.close()


def test_deterministic_claim_rejected_wrong_number():
    """Invalid deterministic claim with wrong number is rejected."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {
                            "name": "get_financials",
                            "arguments": "{}"
                        }
                    }
                ]
            },
            {
                "content": json.dumps({
                    "answer": "Revenue CAGR is hallucinated.",
                    "claims": [
                        {
                            "type": "deterministic_fact",
                            "text": "Revenue CAGR was 999.9%.",
                            "source": {
                                "tool": "get_financials",
                                "field": "revenue_cagr_2y_pct"
                            }
                        }
                    ]
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm

        result = answer_question(db, ipo, "What is the CAGR?")

        assert result["mode"] == "llm"
        assert len(result["claims"]) == 0

    db.close()

def test_deterministic_claim_rejected_invalid_tool():
    """Invalid deterministic claim pointing to wrong tool is rejected."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {
                            "name": "get_ipo_profile",
                            "arguments": "{}"
                        }
                    }
                ]
            },
            {
                "content": json.dumps({
                    "answer": "Revenue CAGR is high.",
                    "claims": [
                        {
                            "type": "deterministic_fact",
                            "text": "Revenue CAGR was 10.0%.",
                            "source": {
                                "tool": "get_financials", # not executed
                                "field": "revenue_cagr_2y_pct"
                            }
                        }
                    ]
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm

        result = answer_question(db, ipo, "What is the CAGR?")

        assert result["mode"] == "llm"
        assert len(result["claims"]) == 0

    db.close()


def test_agent_loop_max_rounds():
    """Agent loop should break after MAX_AGENT_ROUNDS."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        
        # Always return a tool call
        def generate_side_effect(*args, **kwargs):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_loop",
                        "function": {
                            "name": "get_financials",
                            "arguments": "{}"
                        }
                    }
                ]
            }
            
        mock_llm.generate_sync.side_effect = generate_side_effect
        mock_get_llm.return_value = mock_llm

        result = answer_question(db, ipo, "Loop forever.")

        assert result["mode"] == "deterministic" # because it failed to produce valid JSON at max rounds

    db.close()

def test_agent_tool_failure_continues():
    """Agent should continue gracefully if a tool fails (e.g. unknown tool requested)."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_bad",
                        "function": {
                            "name": "make_up_tool",
                            "arguments": "{}"
                        }
                    }
                ]
            },
            {
                "content": json.dumps({
                    "answer": "Tool failed.",
                    "claims": []
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm

        result = answer_question(db, ipo, "Use bad tool.")

        assert result["mode"] == "llm"
        assert "make_up_tool" in result["tool_trace"] # It was attempted and failed gracefully
        assert result["answer"] == "Tool failed."

    db.close()
    
def test_multi_turn_session():
    """Agent should retain context from chat history."""
    db, ipo = _setup()

    with patch('app.services.research.get_llm_provider') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.generate_sync.side_effect = [
            {
                "content": json.dumps({
                    "answer": "Turn 2 answer.",
                    "claims": []
                }),
                "tool_calls": []
            }
        ]
        mock_get_llm.return_value = mock_llm

        history = [
            {"role": "user", "content": "Turn 1 question"},
            {"role": "assistant", "content": "Turn 1 answer"}
        ]
        
        result = answer_question(db, ipo, "Turn 2 question", chat_history=history)

        assert result["mode"] == "llm"
        assert result["answer"] == "Turn 2 answer."
        # Verify that mock_llm.generate_sync was called with history
        call_args = mock_llm.generate_sync.call_args[1]["messages"]
        assert len(call_args) == 5 # system, turn 1 user, turn 1 asst, turn 2 user, turn 2 asst (appended after call)
        assert call_args[1]["role"] == "user"
        assert call_args[1]["content"] == "Turn 1 question"

    db.close()

