"""Tests for the autonomous filing enrichment pipeline."""

import hashlib
import json
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Company, Document, FinancialMetric, FinancialPeriod, IPO, Job
from app.services.discovery import FilingCandidate, validate_filing_url
from app.workers import check_filings_task, download_filing_task, enrich_ipo_task

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_company_ipo(db):
    company = Company(name="Test Corp Ltd", slug="test-corp", sector="Tech", exchange="NSE")
    db.add(company)
    db.flush()

    ipo = IPO(company_id=company.id, status="Upcoming", data_source="live")
    db.add(ipo)
    db.flush()
    db.commit()
    return company, ipo


class TestDiscoveryAndValidation:
    
    @patch("app.services.discovery.requests.get")
    def test_invalid_unrelated_pdf_rejection(self, mock_get):
        # Mock a PDF that doesn't mention the company
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.headers = {"Content-Type": "application/pdf"}
        mock_res.content = b"%PDF-1.4 empty"
        mock_get.return_value = mock_res
        
        # We need to mock fitz (PyMuPDF) since we can't generate a valid PDF easily here
        with patch("app.services.discovery.fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 1
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Random unrelated text about another company"
            mock_doc.__getitem__.return_value = mock_page
            mock_fitz.return_value = mock_doc
            
            # Action
            result = validate_filing_url("http://sebi.gov.in/random.pdf", "Test Corp Ltd")
            
            # Assert
            assert result is None  # Should be rejected because issuer doesn't match

    @patch("app.services.discovery.requests.get")
    def test_valid_pdf_acceptance(self, mock_get):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.headers = {"Content-Type": "application/pdf"}
        mock_res.content = b"%PDF-1.4"
        mock_get.return_value = mock_res
        
        with patch("app.services.discovery.fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 150
            mock_page = MagicMock()
            # Contains normalized company name and "draft red herring prospectus"
            mock_page.get_text.return_value = "Test Corp Draft Red Herring Prospectus"
            mock_doc.__getitem__.return_value = mock_page
            mock_fitz.return_value = mock_doc
            
            result = validate_filing_url("http://sebi.gov.in/test.pdf", "Test Corp Ltd")
            
            assert result is not None
            assert result.doc_type == "DRHP"
            assert result.source_domain == "sebi.gov.in"


class TestWorkerTasks:
    
    @patch("app.workers.SessionLocal")
    @patch("app.workers.validate_filing_url")
    @patch("app.workers.find_candidate_pdf_urls")
    @patch("app.workers.download_filing_task.delay")
    def test_check_filings_triggers_download(self, mock_download_delay, mock_find, mock_validate, mock_session, db, sample_company_ipo):
        mock_session.return_value = db
        company, ipo = sample_company_ipo
        
        mock_find.return_value = ["http://sebi.gov.in/drhp.pdf"]
        
        mock_candidate = FilingCandidate("http://sebi.gov.in/drhp.pdf", "sebi.gov.in")
        mock_candidate.doc_type = "DRHP"
        mock_validate.return_value = mock_candidate
        
        check_filings_task(ipo.id)
        
        mock_download_delay.assert_called_once_with(ipo.id, "http://sebi.gov.in/drhp.pdf", "DRHP")


    @patch("app.workers.SessionLocal")
    @patch("app.workers.validate_filing_url")
    @patch("app.workers.process_document_task.delay")
    @patch("builtins.open")
    def test_download_filing_deduplication(self, mock_open, mock_process_delay, mock_validate, mock_session, db, sample_company_ipo):
        mock_session.return_value = db
        company, ipo = sample_company_ipo
        
        pdf_bytes = b"fake pdf content"
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Pre-insert document with same checksum
        existing_doc = Document(company_id=company.id, ipo_id=ipo.id, checksum=checksum, storage_url="/tmp/existing")
        db.add(existing_doc)
        db.commit()
        
        mock_candidate = FilingCandidate("http://url.com/drhp.pdf", "url.com")
        mock_candidate.pdf_bytes = pdf_bytes
        mock_validate.return_value = mock_candidate
        
        # Act
        download_filing_task(ipo.id, "http://url.com/drhp.pdf", "DRHP")
        
        # Assert - process delay shouldn't be called because dedup caught it
        mock_process_delay.assert_not_called()
        
        # Delete doc and run again
        db.delete(existing_doc)
        db.commit()
        
        download_filing_task(ipo.id, "http://url.com/drhp.pdf", "DRHP")
        
        # Assert it was processed now
        assert mock_process_delay.call_count == 1
