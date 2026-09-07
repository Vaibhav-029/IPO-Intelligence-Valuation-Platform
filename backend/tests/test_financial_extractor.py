"""Comprehensive tests for Phase 1 filing enrichment pipeline.

Tests cover:
A. Multi-year financial extraction
B. INR unit normalization
C. Missing fields remain NULL
D. Provenance is retained
E. Duplicate extraction is idempotent
F. Malformed LLM output is rejected
G. Risk extraction preserves source pages
H. Score regeneration occurs after persistence
I. Partial financial coverage works with NULL-aware scoring
J. No fabricated values are created
K. Ambiguous risk severity causes skip (never defaults)
L. Coverage endpoint returns correct states

All tests use mock LLM responses — no live Groq API required.
"""
import hashlib
import json
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import (
    Company,
    Document,
    FinancialMetric,
    FinancialPeriod,
    IPO,
    IPOSCore,
    RiskFactor,
    Source,
)
from app.services.financial_extractor import (
    ExtractionStatus,
    extract_financials,
    _identify_financial_chunks,
    _normalize_metric_value,
    _validate_metric_value,
    _parse_llm_response,
)
from app.services.risk_extractor import (
    RiskExtractionStatus,
    extract_risks,
    _identify_risk_chunks,
)

# Import test fixtures
from tests.fixtures.rentomojo_drhp_fixture import (
    FINANCIAL_STATEMENT_CHUNK,
    BALANCE_SHEET_CHUNK,
    RISK_FACTORS_CHUNK,
    BOILERPLATE_CHUNK,
    MOCK_FINANCIAL_LLM_RESPONSE,
    MOCK_RISK_LLM_RESPONSE,
    MOCK_PARTIAL_FINANCIAL_LLM_RESPONSE,
    MOCK_MALFORMED_LLM_RESPONSE,
    MOCK_RISK_AMBIGUOUS_SEVERITY,
    MOCK_UNIT_VARIATION_RESPONSE,
    MOCK_EMPTY_RESPONSE,
)


# ── Mock LLM provider ───────────────────────────────────────────────

class MockLLMProvider:
    """A mock LLM provider that returns preset responses."""

    def __init__(self, response_content: str = ""):
        self.is_available = True
        self._response_content = response_content
        self.call_count = 0

    def generate_sync(self, *, messages, temperature=0.15, max_tokens=1500,
                      response_format="text", tools=None, tool_choice=None):
        self.call_count += 1
        return {"content": self._response_content}


class DisabledMockLLMProvider:
    """A mock LLM provider that is disabled."""
    is_available = False

    def generate_sync(self, **kwargs):
        return {"content": "", "tool_calls": []}


# ── Test database setup ──────────────────────────────────────────────

@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def sample_company(db):
    """Create a sample company for testing."""
    company = Company(
        name="Rentomojo",
        slug="rentomojo",
        sector="Consumer Technology",
        exchange="NSE / BSE",
        description="Furniture and appliance rental platform.",
    )
    db.add(company)
    db.flush()
    return company


@pytest.fixture
def sample_ipo(db, sample_company):
    """Create a sample IPO for testing."""
    ipo = IPO(
        company_id=sample_company.id,
        status="Upcoming",
        issue_size=1255.6,
        price_low=384,
        price_high=404,
        open_date=date(2026, 9, 9),
        close_date=date(2026, 9, 11),
        data_source="live",
    )
    db.add(ipo)
    db.flush()
    return ipo


@pytest.fixture
def sample_document(db, sample_company, sample_ipo):
    """Create a sample processed document with Source chunks."""
    doc = Document(
        company_id=sample_company.id,
        ipo_id=sample_ipo.id,
        type="DRHP",
        filename="rentomojo-drhp.pdf",
        storage_url="/tmp/test-drhp.pdf",
        checksum=hashlib.sha256(b"test-content").hexdigest(),
        processing_status="completed",
        page_count=200,
    )
    db.add(doc)
    db.flush()

    # Add Source chunks simulating processed DRHP pages
    chunks = [
        Source(
            document_id=doc.id,
            page=140,
            section="RESTATED CONSOLIDATED STATEMENT OF PROFIT AND LOSS",
            chunk_id=f"doc-{doc.id}-p140-c1",
            text=FINANCIAL_STATEMENT_CHUNK,
            source_text_hash=hashlib.sha256(FINANCIAL_STATEMENT_CHUNK.encode()).hexdigest(),
            confidence=1.0,
            is_empty=False,
        ),
        Source(
            document_id=doc.id,
            page=145,
            section="RESTATED CONSOLIDATED BALANCE SHEET",
            chunk_id=f"doc-{doc.id}-p145-c1",
            text=BALANCE_SHEET_CHUNK,
            source_text_hash=hashlib.sha256(BALANCE_SHEET_CHUNK.encode()).hexdigest(),
            confidence=1.0,
            is_empty=False,
        ),
        Source(
            document_id=doc.id,
            page=45,
            section="RISK FACTORS",
            chunk_id=f"doc-{doc.id}-p45-c1",
            text=RISK_FACTORS_CHUNK,
            source_text_hash=hashlib.sha256(RISK_FACTORS_CHUNK.encode()).hexdigest(),
            confidence=1.0,
            is_empty=False,
        ),
        Source(
            document_id=doc.id,
            page=1,
            section="GENERAL INFORMATION",
            chunk_id=f"doc-{doc.id}-p1-c1",
            text=BOILERPLATE_CHUNK,
            source_text_hash=hashlib.sha256(BOILERPLATE_CHUNK.encode()).hexdigest(),
            confidence=1.0,
            is_empty=False,
        ),
    ]
    for c in chunks:
        db.add(c)
    db.flush()
    db.commit()

    return doc


# ══════════════════════════════════════════════════════════════════════
# A. Multi-year financial extraction
# ══════════════════════════════════════════════════════════════════════

class TestMultiYearExtraction:
    def test_extracts_three_annual_periods(self, db, sample_company, sample_ipo, sample_document):
        """Full extraction: 3 annual periods with all 9 metrics each."""
        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)

        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        assert result.status == ExtractionStatus.EXTRACTION_COMPLETED
        assert result.periods_extracted == 3
        assert result.periods_updated == 0

        # Verify all 3 periods in DB
        periods = db.scalars(
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
            .order_by(FinancialPeriod.period_end)
        ).all()
        assert len(periods) == 3

        # Verify FY2022
        fy22 = [p for p in periods if p.fiscal_year == "FY2022"][0]
        assert fy22.period_type == "Annual"
        assert fy22.period_end == date(2022, 3, 31)
        metric22 = db.scalar(select(FinancialMetric).where(FinancialMetric.period_id == fy22.id))
        assert metric22 is not None
        assert float(metric22.revenue) == pytest.approx(187.21, rel=1e-2)

        # Verify FY2024
        fy24 = [p for p in periods if p.fiscal_year == "FY2024"][0]
        metric24 = db.scalar(select(FinancialMetric).where(FinancialMetric.period_id == fy24.id))
        assert float(metric24.revenue) == pytest.approx(412.56, rel=1e-2)
        assert float(metric24.ebitda) == pytest.approx(120.18, rel=1e-2)
        assert float(metric24.pat) == pytest.approx(56.21, rel=1e-2)
        assert float(metric24.eps) == pytest.approx(14.23, rel=1e-2)
        assert float(metric24.total_debt) == pytest.approx(131.10, rel=1e-2)
        assert float(metric24.cash) == pytest.approx(67.89, rel=1e-2)
        assert float(metric24.equity) == pytest.approx(325.17, rel=1e-2)
        assert float(metric24.assets) == pytest.approx(526.62, rel=1e-2)

    def test_period_type_and_fiscal_year(self, db, sample_company, sample_ipo, sample_document):
        """Verify period semantics are preserved."""
        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        periods = db.scalars(
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
        ).all()
        for p in periods:
            assert p.period_type == "Annual"
            assert p.interim_period is None
            assert p.fiscal_year.startswith("FY")


# ══════════════════════════════════════════════════════════════════════
# B. INR unit normalization
# ══════════════════════════════════════════════════════════════════════

class TestUnitNormalization:
    def test_crore_passthrough(self):
        assert _normalize_metric_value("412.56", "crore", 412.56) == pytest.approx(412.56)

    def test_lakhs_conversion(self):
        # 41256 lakhs = 412.56 crore
        assert _normalize_metric_value("41256", "lakhs", 41256) == pytest.approx(412.56)

    def test_million_conversion(self):
        # 120.18 million = 12.018 crore
        assert _normalize_metric_value("120.18", "million", 120.18) == pytest.approx(12.018)

    def test_billion_conversion(self):
        # 1.5 billion = 150 crore
        assert _normalize_metric_value("1.5", "billion", 1.5) == pytest.approx(150.0)

    def test_inr_passthrough(self):
        # EPS in INR stays as-is
        assert _normalize_metric_value("14.23", "inr", 14.23) == pytest.approx(14.23)

    def test_none_value(self):
        assert _normalize_metric_value(None, None, None) is None

    def test_mixed_unit_extraction(self, db, sample_company, sample_ipo, sample_document):
        """Extraction with mixed units normalizes correctly."""
        llm = MockLLMProvider(MOCK_UNIT_VARIATION_RESPONSE)
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        assert result.periods_extracted == 1
        metric = db.scalar(
            select(FinancialMetric)
            .join(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
        )
        assert metric is not None
        # 41256 lakhs = 412.56 crore
        assert float(metric.revenue) == pytest.approx(412.56, rel=1e-2)
        # 120.18 million = 12.018 crore
        assert float(metric.ebitda) == pytest.approx(12.018, rel=1e-2)
        # 562.1 crore stays as-is
        assert float(metric.pat) == pytest.approx(562.1, rel=1e-2)


# ══════════════════════════════════════════════════════════════════════
# C. Missing fields remain NULL
# ══════════════════════════════════════════════════════════════════════

class TestMissingFields:
    def test_partial_extraction_preserves_nulls(self, db, sample_company, sample_ipo, sample_document):
        """When only revenue and PAT are extracted, other fields stay NULL."""
        llm = MockLLMProvider(MOCK_PARTIAL_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        assert result.periods_extracted == 1
        metric = db.scalar(
            select(FinancialMetric)
            .join(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
        )
        assert metric is not None
        assert float(metric.revenue) == pytest.approx(412.56, rel=1e-2)
        assert float(metric.pat) == pytest.approx(56.21, rel=1e-2)
        # These were NOT in the partial response — must be NULL
        assert metric.ebitda is None
        assert metric.ebit is None
        assert metric.eps is None
        assert metric.total_debt is None
        assert metric.cash is None
        assert metric.equity is None
        assert metric.assets is None


# ══════════════════════════════════════════════════════════════════════
# D. Provenance is retained
# ══════════════════════════════════════════════════════════════════════

class TestProvenance:
    def test_source_type_and_reference(self, db, sample_company, sample_ipo, sample_document):
        """Verify source_type, source_reference, derived_fields are set correctly."""
        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        metric = db.scalar(
            select(FinancialMetric)
            .join(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
            .order_by(FinancialPeriod.period_end.desc())
        )
        assert metric is not None
        assert metric.source_type == "filing_extraction"
        assert metric.source_reference is not None
        assert metric.source_reference.startswith("doc-")

        # derived_fields should contain metadata per extracted metric
        assert isinstance(metric.derived_fields, dict)
        assert "revenue" in metric.derived_fields
        assert metric.derived_fields["revenue"]["confidence"] == "high"
        assert "source_chunk" in metric.derived_fields["revenue"]


# ══════════════════════════════════════════════════════════════════════
# E. Duplicate extraction is idempotent
# ══════════════════════════════════════════════════════════════════════

class TestIdempotency:
    def test_running_twice_does_not_duplicate(self, db, sample_company, sample_ipo, sample_document):
        """Running extraction twice for the same document doesn't create duplicates."""
        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)

        # First run
        result1 = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()
        assert result1.periods_extracted == 3

        # Second run
        result2 = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()
        assert result2.periods_updated == 3
        assert result2.periods_extracted == 0

        # Verify only 3 periods exist, not 6
        count = len(db.scalars(
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
        ).all())
        assert count == 3


# ══════════════════════════════════════════════════════════════════════
# F. Malformed LLM output is rejected
# ══════════════════════════════════════════════════════════════════════

class TestMalformedOutput:
    def test_non_json_response_rejected(self, db, sample_company, sample_ipo, sample_document):
        """Non-JSON LLM output produces failure, not DB rows."""
        llm = MockLLMProvider(MOCK_MALFORMED_LLM_RESPONSE)
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)

        assert result.status == ExtractionStatus.EXTRACTION_FAILED
        assert result.periods_extracted == 0

        # Verify no financial data was created
        count = len(db.scalars(
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == sample_company.id)
        ).all())
        assert count == 0

    def test_empty_periods_response(self, db, sample_company, sample_ipo, sample_document):
        """Empty periods list produces no data."""
        llm = MockLLMProvider(MOCK_EMPTY_RESPONSE)
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)

        assert result.status == ExtractionStatus.NO_FINANCIAL_SECTIONS
        assert result.periods_extracted == 0

    def test_empty_content_response(self, db, sample_company, sample_ipo, sample_document):
        """Empty string response produces failure."""
        llm = MockLLMProvider("")
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.EXTRACTION_FAILED


# ══════════════════════════════════════════════════════════════════════
# G. Risk extraction preserves source pages
# ══════════════════════════════════════════════════════════════════════

class TestRiskExtraction:
    def test_extracts_risks_with_pages(self, db, sample_company, sample_ipo, sample_document):
        """Risk extraction creates RiskFactor rows with correct source_page."""
        llm = MockLLMProvider(MOCK_RISK_LLM_RESPONSE)
        result = extract_risks(db, sample_document.id, sample_ipo.id, llm_provider=llm)
        db.commit()

        assert result.status == RiskExtractionStatus.EXTRACTION_COMPLETED
        assert result.risks_extracted == 7

        risks = db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == sample_ipo.id)).all()
        assert len(risks) == 7

        # Verify source_page is preserved
        high_risks = [r for r in risks if r.severity == "High"]
        assert len(high_risks) == 2
        assert all(r.source_page is not None for r in high_risks)

        # Verify categories
        categories = {r.category for r in risks}
        assert "Concentration" in categories
        assert "Competition" in categories
        assert "Regulatory" in categories

    def test_ambiguous_severity_skipped(self, db, sample_company, sample_ipo, sample_document):
        """Risks with ambiguous severity are skipped, never defaulted to Medium."""
        llm = MockLLMProvider(MOCK_RISK_AMBIGUOUS_SEVERITY)
        result = extract_risks(db, sample_document.id, sample_ipo.id, llm_provider=llm)
        db.commit()

        # Only 1 risk has valid severity ("High"), 2 have "ambiguous"/"unclear"
        assert result.risks_extracted == 1
        assert result.risks_skipped_ambiguous == 2

        risks = db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == sample_ipo.id)).all()
        assert len(risks) == 1
        assert risks[0].severity == "High"
        assert risks[0].category == "Financial"

    def test_risk_idempotency_for_live_ipo(self, db, sample_company, sample_ipo, sample_document):
        """Running risk extraction twice on a live IPO replaces previous results."""
        llm = MockLLMProvider(MOCK_RISK_LLM_RESPONSE)

        # First run
        result1 = extract_risks(db, sample_document.id, sample_ipo.id, llm_provider=llm)
        db.commit()
        assert result1.risks_extracted == 7

        # Second run
        result2 = extract_risks(db, sample_document.id, sample_ipo.id, llm_provider=llm)
        db.commit()
        assert result2.risks_extracted == 7

        # Verify only 7 risks exist, not 14
        count = len(db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == sample_ipo.id)).all())
        assert count == 7


# ══════════════════════════════════════════════════════════════════════
# H. Score regeneration occurs after persistence
# ══════════════════════════════════════════════════════════════════════

class TestScoreRegeneration:
    def test_score_generated_after_financial_and_risk_extraction(self, db, sample_company, sample_ipo, sample_document):
        """After extraction, calling generate_ipo_score produces a score with available dimensions."""
        # Extract financials
        fin_llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        extract_financials(db, sample_document.id, sample_company.id, llm_provider=fin_llm)

        # Extract risks
        risk_llm = MockLLMProvider(MOCK_RISK_LLM_RESPONSE)
        extract_risks(db, sample_document.id, sample_ipo.id, llm_provider=risk_llm)
        db.commit()

        # Now generate the score using the existing scoring engine
        from app.analytics.scoring import generate_ipo_score
        score_obj = generate_ipo_score(db, sample_ipo.id)
        db.commit()

        assert score_obj is not None
        # overall_score should be computed from available dimensions
        assert score_obj.overall_score is not None
        assert score_obj.overall_score > 0

        # With 3 annual periods of full financials + risks, we should have these dimensions:
        # - growth (have 3 periods for CAGR and YoY)
        assert score_obj.growth_score is not None
        # - risk (have risk factors)
        assert score_obj.risk_score is not None
        # - balance_sheet (have debt + equity)
        assert score_obj.balance_sheet_score is not None
        # - business_quality: None (no manual assessment)
        assert score_obj.business_quality_score is None


# ══════════════════════════════════════════════════════════════════════
# I. Partial financial coverage works with NULL-aware scoring
# ══════════════════════════════════════════════════════════════════════

class TestPartialCoverage:
    def test_partial_extraction_produces_partial_score(self, db, sample_company, sample_ipo, sample_document):
        """Only revenue+PAT extracted → only some score dimensions available."""
        llm = MockLLMProvider(MOCK_PARTIAL_FINANCIAL_LLM_RESPONSE)
        extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        from app.analytics.scoring import generate_ipo_score
        score_obj = generate_ipo_score(db, sample_ipo.id)
        db.commit()

        assert score_obj is not None
        # balance_sheet needs debt+equity — both NULL → balance_sheet should be None
        assert score_obj.balance_sheet_score is None
        # business_quality always NULL for live IPOs (no manual assessment)
        assert score_obj.business_quality_score is None
        # valuation needs peers — NULL
        assert score_obj.valuation_score is None


# ══════════════════════════════════════════════════════════════════════
# J. No fabricated values are created
# ══════════════════════════════════════════════════════════════════════

class TestNoFabrication:
    def test_no_document_creates_nothing(self, db, sample_company, sample_ipo):
        """Extraction with non-existent document creates no rows."""
        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, 99999, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.DOCUMENT_UNAVAILABLE
        assert result.periods_extracted == 0

    def test_unprocessed_document_creates_nothing(self, db, sample_company, sample_ipo):
        """Extraction with unprocessed document creates no rows."""
        doc = Document(
            company_id=sample_company.id,
            type="DRHP",
            filename="test.pdf",
            storage_url="/tmp/test.pdf",
            checksum="abc123",
            processing_status="queued",
            page_count=0,
        )
        db.add(doc)
        db.flush()

        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, doc.id, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.PROCESSING_INCOMPLETE
        assert result.periods_extracted == 0

    def test_llm_unavailable_creates_nothing(self, db, sample_company, sample_ipo, sample_document):
        """When LLM is unavailable, no financial data is fabricated."""
        llm = DisabledMockLLMProvider()
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.LLM_UNAVAILABLE
        assert result.periods_extracted == 0

    def test_negative_revenue_rejected(self):
        """Negative revenue is rejected (returns None)."""
        assert _validate_metric_value("revenue", -100) is None

    def test_negative_debt_rejected(self):
        """Negative debt is rejected."""
        assert _validate_metric_value("total_debt", -50) is None

    def test_negative_equity_allowed(self):
        """Negative equity is allowed (accumulated losses)."""
        assert _validate_metric_value("equity", -25) == -25


# ══════════════════════════════════════════════════════════════════════
# K. Chunk identification
# ══════════════════════════════════════════════════════════════════════

class TestChunkIdentification:
    def test_financial_chunks_identified(self, db, sample_document):
        """Financial statement chunks are correctly identified."""
        sources = db.scalars(
            select(Source).where(Source.document_id == sample_document.id, Source.is_empty == False)
        ).all()

        financial_chunks = _identify_financial_chunks(list(sources))

        # Should find the financial statement and balance sheet chunks, not boilerplate
        assert len(financial_chunks) >= 2

        sections = [c.section for c in financial_chunks]
        assert any("PROFIT AND LOSS" in (s or "").upper() for s in sections)
        assert any("BALANCE SHEET" in (s or "").upper() for s in sections)

    def test_risk_chunks_identified(self, db, sample_document):
        """Risk factor chunks are correctly identified."""
        sources = db.scalars(
            select(Source).where(Source.document_id == sample_document.id, Source.is_empty == False)
        ).all()

        risk_chunks = _identify_risk_chunks(list(sources))

        assert len(risk_chunks) >= 1
        sections = [c.section for c in risk_chunks]
        assert any("RISK" in (s or "").upper() for s in sections)

    def test_boilerplate_not_identified_as_financial(self, db, sample_document):
        """Boilerplate text is NOT identified as a financial chunk."""
        sources = db.scalars(
            select(Source).where(
                Source.document_id == sample_document.id,
                Source.section == "GENERAL INFORMATION",
            )
        ).all()

        financial_chunks = _identify_financial_chunks(list(sources))
        assert len(financial_chunks) == 0


# ══════════════════════════════════════════════════════════════════════
# L. LLM response parsing
# ══════════════════════════════════════════════════════════════════════

class TestLLMResponseParsing:
    def test_valid_json_parsed(self):
        result = _parse_llm_response(MOCK_FINANCIAL_LLM_RESPONSE)
        assert result is not None
        assert len(result["periods"]) == 3

    def test_malformed_rejected(self):
        result = _parse_llm_response(MOCK_MALFORMED_LLM_RESPONSE)
        assert result is None

    def test_empty_string_rejected(self):
        result = _parse_llm_response("")
        assert result is None

    def test_none_rejected(self):
        result = _parse_llm_response(None)
        assert result is None

    def test_json_with_markdown_fences(self):
        wrapped = f"```json\n{MOCK_FINANCIAL_LLM_RESPONSE}\n```"
        result = _parse_llm_response(wrapped)
        assert result is not None
        assert len(result["periods"]) == 3


# ══════════════════════════════════════════════════════════════════════
# M. Document status guards
# ══════════════════════════════════════════════════════════════════════

class TestDocumentStatusGuards:
    def test_failed_document_rejected(self, db, sample_company):
        """A document with processing_status='failed' is rejected."""
        doc = Document(
            company_id=sample_company.id,
            type="DRHP",
            filename="test.pdf",
            storage_url="/tmp/test.pdf",
            checksum="xyz",
            processing_status="failed",
            page_count=0,
            failure_reason="PDF corrupt",
        )
        db.add(doc)
        db.flush()

        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, doc.id, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.PROCESSING_INCOMPLETE

    def test_document_with_no_chunks(self, db, sample_company):
        """A completed document with zero chunks is handled."""
        doc = Document(
            company_id=sample_company.id,
            type="DRHP",
            filename="empty.pdf",
            storage_url="/tmp/empty.pdf",
            checksum="empty123",
            processing_status="completed",
            page_count=0,
        )
        db.add(doc)
        db.flush()

        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, doc.id, sample_company.id, llm_provider=llm)
        assert result.status == ExtractionStatus.NO_FINANCIAL_SECTIONS


# ══════════════════════════════════════════════════════════════════════
# N. Does not overwrite curated seed data
# ══════════════════════════════════════════════════════════════════════

class TestSeedDataProtection:
    def test_does_not_overwrite_curated_data(self, db, sample_company, sample_ipo, sample_document):
        """Filing extraction does not overwrite existing curated financial data."""
        # Create a curated financial period that matches FY2024
        period = FinancialPeriod(
            company_id=sample_company.id,
            period_end=date(2024, 3, 31),
            period_type="Annual",
            fiscal_year="FY2024",
        )
        db.add(period)
        db.flush()

        metric = FinancialMetric(
            period_id=period.id,
            revenue=999.99,
            source_type="Curated Structured Dataset",
            source_reference="ipo_companies.json",
            derived_fields={},
        )
        db.add(metric)
        db.flush()
        db.commit()

        llm = MockLLMProvider(MOCK_FINANCIAL_LLM_RESPONSE)
        result = extract_financials(db, sample_document.id, sample_company.id, llm_provider=llm)
        db.commit()

        # FY2024 should not be overwritten
        preserved = db.scalar(select(FinancialMetric).where(FinancialMetric.period_id == period.id))
        assert float(preserved.revenue) == pytest.approx(999.99)
        assert preserved.source_type == "Curated Structured Dataset"

        # FY2023 and FY2022 should be created
        assert result.periods_extracted == 2
