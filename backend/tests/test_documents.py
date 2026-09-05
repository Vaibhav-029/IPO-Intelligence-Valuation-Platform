import pytest
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.models import Document, Source, User, IPO, Company
from app.services.documents import process_document, is_likely_heading
from app.services.research import retrieve_evidence
from app.db import Base, engine, SessionLocal
from app.main import app, settings

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()

@pytest.fixture
def client():
    return TestClient(app)

def test_is_likely_heading():
    assert is_likely_heading("SUMMARY OF FINANCIAL INFORMATION") is True
    assert is_likely_heading("RISK FACTORS") is True
    assert is_likely_heading("A very long sentence that is not a heading but is upper case. " * 5) is False
    assert is_likely_heading("Some normal text") is False
    assert is_likely_heading("") is False


@patch("app.services.documents.fitz")
def test_process_document_extraction(mock_fitz, db_session: Session):
    # Mock PDF behavior
    mock_doc = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = [
        (0,0,0,0, "RISK FACTORS", 1, 0),
        (0,0,0,0, "This is a risk factor.", 2, 0),
        (0,0,0,0, "Another risk factor.", 3, 0)
    ]
    mock_page2 = MagicMock()
    # Mock empty page
    mock_page2.get_text.return_value = []
    
    # Mock large page for chunking
    mock_page3 = MagicMock()
    mock_page3.get_text.return_value = [
        (0,0,0,0, "LONG TEXT", 1, 0)
    ] + [(0,0,0,0, "A"*500, i, 0) for i in range(2, 6)] # 2000 chars total
    
    mock_doc.__iter__.return_value = [mock_page1, mock_page2, mock_page3]
    mock_doc.__len__.return_value = 3
    mock_fitz.open.return_value = mock_doc

    doc = Document(type="RHP", storage_url="test.pdf", checksum="test", is_public=True)
    db_session.add(doc)
    db_session.commit()

    process_document(db_session, doc.id)
    
    db_session.refresh(doc)
    assert doc.processing_status == "completed"
    assert doc.page_count == 3
    
    sources = db_session.query(Source).filter_by(document_id=doc.id).order_by(Source.page, Source.id).all()
    
    # Page 1: 1 chunk, section=RISK FACTORS
    p1_sources = [s for s in sources if s.page == 1]
    assert len(p1_sources) == 1
    assert p1_sources[0].section == "RISK FACTORS"
    assert "This is a risk factor." in p1_sources[0].text
    assert p1_sources[0].is_empty is False
    
    # Page 2: empty page
    p2_sources = [s for s in sources if s.page == 2]
    assert len(p2_sources) == 1
    assert p2_sources[0].is_empty is True
    assert p2_sources[0].text == ""
    assert p2_sources[0].section is None
    
    # Page 3: Chunking (2000 chars should split across 2 chunks)
    p3_sources = [s for s in sources if s.page == 3]
    assert len(p3_sources) == 2
    assert p3_sources[0].section == "LONG TEXT"
    assert p3_sources[1].section == "LONG TEXT" # Preserved section across chunks
    assert "A"*500 in p3_sources[0].text
    assert p3_sources[0].is_empty is False


def test_bm25_retrieval(db_session: Session):
    company = Company(name="Test Co", slug="test-co", sector="Tech")
    db_session.add(company)
    db_session.commit()
    doc = Document(company_id=company.id, type="RHP", storage_url="test.pdf", checksum="bm25test", is_public=True)
    db_session.add(doc)
    db_session.commit()
    
    # Add sources
    db_session.add_all([
        Source(document_id=doc.id, page=1, section="Risks", chunk_id="c1", text="Company faces litigation risks.", source_text_hash="h1", confidence=1.0),
        Source(document_id=doc.id, page=2, section="Business", chunk_id="c2", text="We expect high revenue growth.", source_text_hash="h2", confidence=1.0),
        Source(document_id=doc.id, page=3, section="Debt", chunk_id="c3", text="Debt is very high.", source_text_hash="h3", confidence=1.0),
        Source(document_id=doc.id, page=4, section=None, chunk_id="empty", text="", source_text_hash="empty", confidence=0.0, is_empty=True)
    ])
    db_session.commit()
    
    # Test relevance matching
    results = retrieve_evidence(db_session, company.id, "litigation risks", min_score=0.0)
    assert len(results) == 1
    assert results[0]["page"] == 1
    assert "source_id" in results[0]
    
    # Test empty query / zero match
    assert len(retrieve_evidence(db_session, company.id, "   ")) == 0
    assert len(retrieve_evidence(db_session, company.id, "aliens")) == 0
    
    # Test top-K
    results = retrieve_evidence(db_session, company.id, "risks revenue debt", limit=2, min_score=0.0)
    assert len(results) == 2


def test_bm25_tie_breaking(db_session: Session):
    company = Company(name="Tie Co", slug="tie-co", sector="Tech")
    db_session.add(company)
    db_session.commit()
    doc = Document(company_id=company.id, type="RHP", storage_url="test.pdf", checksum="tietest", is_public=True)
    db_session.add(doc)
    db_session.commit()
    
    # Add exact identical texts on different pages to force a tie score
    db_session.add_all([
        Source(document_id=doc.id, page=3, section="S1", chunk_id="t1", text="Exact same sentence match.", source_text_hash="x1", confidence=1.0),
        Source(document_id=doc.id, page=1, section="S2", chunk_id="t2", text="Exact same sentence match.", source_text_hash="x2", confidence=1.0),
        Source(document_id=doc.id, page=2, section="S3", chunk_id="t3", text="Exact same sentence match.", source_text_hash="x3", confidence=1.0),
    ])
    db_session.commit()
    
    results = retrieve_evidence(db_session, company.id, "sentence match", limit=4, min_score=0.0)
    assert len(results) == 3
    # Same score, tie break on page ASC
    assert results[0]["page"] == 1
    assert results[1]["page"] == 2
    assert results[2]["page"] == 3


def test_access_control(client: TestClient, db_session: Session):
    u1 = User(email="u1@test.com", password_hash="hash")
    u2 = User(email="u2@test.com", password_hash="hash")
    db_session.add_all([u1, u2])
    db_session.commit()
    
    public_doc = Document(is_public=True, checksum="pub", storage_url="pub")
    private_doc = Document(is_public=False, user_id=u1.id, checksum="priv", storage_url="priv")
    db_session.add_all([public_doc, private_doc])
    db_session.commit()
    
    # Mock auth for u1
    from app.main import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: u1
    
    # u1 can access public doc
    res = client.get(f"/api/v1/documents/{public_doc.id}/status")
    assert res.status_code == 200
    
    # u1 can access own private doc
    res = client.get(f"/api/v1/documents/{private_doc.id}/status")
    assert res.status_code == 200
    
    # Mock auth for u2
    client.app.dependency_overrides[get_current_user] = lambda: u2
    
    # u2 can access public doc
    res = client.get(f"/api/v1/documents/{public_doc.id}/status")
    assert res.status_code == 200
    
    # u2 CANNOT access u1's private doc
    res = client.get(f"/api/v1/documents/{private_doc.id}/status")
    assert res.status_code == 404
    
    # 404 nonexistent
    res = client.get(f"/api/v1/documents/999/status")
    assert res.status_code == 404
    client.app.dependency_overrides.pop(get_current_user, None)


def test_deduplication(client: TestClient, db_session: Session, tmp_path, monkeypatch):
    u1 = User(email="dup1@test.com", password_hash="hash")
    u2 = User(email="dup2@test.com", password_hash="hash")
    company = Company(name="Dup Co", slug="dup-co", sector="Tech")
    db_session.add_all([u1, u2, company])
    db_session.commit()
    ipo = IPO(company_id=company.id, status="Upcoming")
    db_session.add(ipo)
    db_session.commit()
    
    content = b"pdf content"
    checksum = hashlib.sha256(content).hexdigest()
    
    # 1. u1 uploads private
    from app.main import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: u1
    
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    
    res = client.post("/api/v1/documents", files={"file": ("test.pdf", content, "application/pdf")})
    assert res.status_code == 202
    assert res.json()["deduplicated"] is False
    
    # 2. u1 uploads private again -> Deduplicated
    res = client.post("/api/v1/documents", files={"file": ("test.pdf", content, "application/pdf")})
    assert res.status_code == 202
    assert res.json()["deduplicated"] is True
        
    # 3. u2 uploads same file private -> Not deduplicated (isolated)
    client.app.dependency_overrides[get_current_user] = lambda: u2
    res = client.post("/api/v1/documents", files={"file": ("test.pdf", content, "application/pdf")})
    assert res.status_code == 202
    assert res.json()["deduplicated"] is False
    client.app.dependency_overrides.pop(get_current_user, None)
