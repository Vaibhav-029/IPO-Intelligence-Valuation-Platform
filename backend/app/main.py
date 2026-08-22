from __future__ import annotations
import hashlib
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from collections import defaultdict
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.analytics.financials import enterprise_value, margin, revenue_cagr
from app.core.config import get_settings
from app.core.security import create_token, decode_token, get_current_user, hash_password, verify_password
from app.db import Base, engine, get_db
from app.models import Company, Document, FinancialMetric, FinancialPeriod, IPO, IPOSCore, Job, ResearchMessage, ResearchSession, RiskFactor, User, ValuationMetric, Watchlist
from app.schemas import DCFScenario, LoginRequest, RegisterRequest, ResearchQuestion, ResearchSessionRequest, TokenResponse, WatchlistRequest
from app.seed import seed_demo_data
from app.services.documents import process_document
from app.services.research import answer_question, peer_comparison
from app.workers import process_document_task

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
_rate_window: dict[str, list[float]] = defaultdict(list)


@app.on_event("startup")
def startup() -> None:
    settings.ensure_storage()
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        seed_demo_data(db)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


def enforce_rate_limit(request: Request, bucket: str, limit: int = 15) -> None:
    key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
    now = time.time(); _rate_window[key] = [t for t in _rate_window[key] if now - t < 60]
    if len(_rate_window[key]) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    _rate_window[key].append(now)


def as_float(value):
    return float(value) if value is not None else None


def ipo_payload(ipo: IPO, score: IPOSCore | None = None) -> dict:
    return {"id": ipo.id, "company_id": ipo.company_id, "name": ipo.company.name, "slug": ipo.company.slug, "sector": ipo.company.sector,
            "exchange": ipo.company.exchange, "status": ipo.status, "issue_size_crore": as_float(ipo.issue_size), "price_band": [as_float(ipo.price_low), as_float(ipo.price_high)],
            "issue_date": str(ipo.issue_date) if ipo.issue_date else None, "score": score.overall_score if score else None}


@app.get("/health")
def health():
    return {"status": "ok", "service": "ipo-intelligence-api"}


@app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password)); db.add(user); db.commit(); db.refresh(user)
    return issue_tokens(user, response)


def issue_tokens(user: User, response: Response) -> dict:
    access = create_token(user, "access", timedelta(minutes=settings.jwt_access_minutes))
    refresh = create_token(user, "refresh", timedelta(days=settings.jwt_refresh_days))
    response.set_cookie("refresh_token", refresh, httponly=True, secure=False, samesite="lax", max_age=settings.jwt_refresh_days * 86400)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return issue_tokens(user, response)


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
def refresh(response: Response, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    payload = decode_token(token); user = db.get(User, int(payload["sub"]))
    if not user or payload.get("type") != "refresh" or payload.get("ver") != user.refresh_token_version:
        raise HTTPException(status_code=401, detail="Refresh token is invalid")
    return issue_tokens(user, response)


@app.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.refresh_token_version += 1; db.commit(); response.delete_cookie("refresh_token")


@app.get("/api/v1/ipos")
def list_ipos(q: str | None = None, sector: str | None = None, status_filter: str | None = None, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    statement = select(IPO).join(Company).options(joinedload(IPO.company)).order_by(IPO.issue_date.desc())
    if q: statement = statement.where((Company.name.ilike(f"%{q}%")) | (Company.sector.ilike(f"%{q}%")))
    if sector: statement = statement.where(Company.sector == sector)
    if status_filter: statement = statement.where(IPO.status == status_filter)
    records = db.scalars(statement.offset((max(page, 1)-1)*min(page_size, 50)).limit(min(page_size, 50))).unique().all()
    scores = {item.ipo_id: item for item in db.scalars(select(IPOSCore)).all()}
    return {"items": [ipo_payload(ipo, scores.get(ipo.id)) for ipo in records], "page": page, "page_size": min(page_size, 50)}


@app.get("/api/v1/ipos/{ipo_id}")
def get_ipo(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).where(IPO.id == ipo_id))
    if not ipo: raise HTTPException(404, "IPO not found")
    score = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    return {**ipo_payload(ipo, score), "description": ipo.company.description, "fresh_issue_crore": as_float(ipo.fresh_issue), "ofs_crore": as_float(ipo.ofs)}


@app.get("/api/v1/ipos/{ipo_id}/financials")
def financials(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    rows = db.execute(select(FinancialPeriod, FinancialMetric).join(FinancialMetric).where(FinancialPeriod.company_id == ipo.company_id).order_by(FinancialPeriod.period_end)).all()
    items = [{"fiscal_year": period.fiscal_year, "period_end": str(period.period_end), "revenue": as_float(metric.revenue), "ebitda": as_float(metric.ebitda), "ebit": as_float(metric.ebit), "pat": as_float(metric.pat), "equity": as_float(metric.equity), "debt": as_float(metric.total_debt), "cash": as_float(metric.cash), "ebitda_margin": margin(float(metric.ebitda), float(metric.revenue)), "pat_margin": margin(float(metric.pat), float(metric.revenue))} for period, metric in rows]
    return {"items": items, "revenue_cagr_2y": revenue_cagr(items[0]["revenue"], items[-1]["revenue"], len(items)-1) if len(items) > 1 else None}


@app.get("/api/v1/ipos/{ipo_id}/valuation")
def valuation(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    item = db.scalar(select(ValuationMetric).where(ValuationMetric.company_id == ipo.company_id).order_by(ValuationMetric.date.desc()))
    return {"market_cap": as_float(item.market_cap), "enterprise_value": as_float(item.ev), "pe": item.pe, "ps": item.ps, "ev_ebitda": item.ev_ebitda, "ev_sales": item.ev_sales, "as_of": str(item.date)} if item else {}


@app.get("/api/v1/ipos/{ipo_id}/peers")
def peers(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    
    summary = peer_comparison(db, ipo.company_id)
    
    from app.models import Peer
    peer_ids = db.scalars(select(Peer.peer_company_id).where(Peer.company_id == ipo.company_id, Peer.active == True)).all()
    detailed_peers = []
    for pid in peer_ids:
        comp = db.get(Company, pid)
        vm = db.scalar(select(ValuationMetric).where(ValuationMetric.company_id == pid).order_by(ValuationMetric.date.desc()))
        if comp:
            detailed_peers.append({
                "name": comp.name,
                "sector": comp.sector,
                "market_cap": as_float(vm.market_cap) if vm else None,
                "pe": vm.pe if vm else None,
                "ps": vm.ps if vm else None,
                "ev_ebitda": vm.ev_ebitda if vm else None,
            })
            
    # Also fetch the target company's latest metrics for easy comparison
    target_vm = db.scalar(select(ValuationMetric).where(ValuationMetric.company_id == ipo.company_id).order_by(ValuationMetric.date.desc()))
    target = {
        "name": ipo.company.name,
        "sector": ipo.company.sector,
        "market_cap": as_float(target_vm.market_cap) if target_vm else None,
        "pe": target_vm.pe if target_vm else None,
        "ps": target_vm.ps if target_vm else None,
        "ev_ebitda": target_vm.ev_ebitda if target_vm else None,
    }
            
    return {"summary": summary, "target": target, "peers": detailed_peers}


@app.get("/api/v1/ipos/{ipo_id}/score")
def score(ipo_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    if not item: raise HTTPException(404, "Score not found")
    return {"financial_quality": item.profitability_score, "growth": item.growth_score, "valuation": item.valuation_score, "balance_sheet": item.notes.get("balance_sheet_score"), "business_quality": item.business_score, "risk": item.risk_score, "overall_score": item.overall_score, "methodology_version": item.methodology_version, "methodology": "Financial 20%, Growth 20%, Valuation 20%, Balance Sheet 15%, Business Quality 15%, Risk 10%."}


@app.get("/api/v1/ipos/{ipo_id}/risks")
def risks(ipo_id: int, db: Session = Depends(get_db)):
    return [{"id": item.id, "category": item.category, "severity": item.severity, "summary": item.summary, "source_page": item.source_page} for item in db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == ipo_id)).all()]


@app.post("/api/v1/documents", status_code=202)
def upload_document(request: Request, file: UploadFile = File(...), ipo_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(request, "upload", 8)
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(415, "Only PDF filings are accepted")
    content = file.file.read()
    if len(content) > 30 * 1024 * 1024: raise HTTPException(413, "Maximum upload size is 30 MB")
    checksum = hashlib.sha256(content).hexdigest(); existing = db.scalar(select(Document).where(Document.checksum == checksum))
    if existing: return {"document_id": existing.id, "status": existing.processing_status, "deduplicated": True}
    ipo = db.get(IPO, ipo_id) if ipo_id else None
    target = settings.ensure_storage() / f"{checksum}.pdf"; target.write_bytes(content)
    document = Document(ipo_id=ipo_id, company_id=ipo.company_id if ipo else None, type="RHP", storage_url=str(target.resolve()), checksum=checksum)
    db.add(document); db.flush(); db.add(Job(job_type="document_processing", entity_id=document.id)); db.commit()
    if settings.task_eager:
        process_document(db, document.id)
    else:
        process_document_task.delay(document.id)
    return {"document_id": document.id, "status": "queued", "deduplicated": False}


@app.get("/api/v1/documents/{document_id}/status")
def document_status(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document: raise HTTPException(404, "Document not found")
    return {"id": document.id, "status": document.processing_status, "page_count": document.page_count, "error": document.failure_reason}


@app.get("/api/v1/documents/{document_id}/sources")
def document_sources(document_id: int, page: int | None = None, db: Session = Depends(get_db)):
    from app.models import Source
    statement = select(Source).where(Source.document_id == document_id)
    if page: statement = statement.where(Source.page == page)
    return [{"id": source.id, "page": source.page, "section": source.section, "excerpt": source.text, "confidence": source.confidence} for source in db.scalars(statement).all()]


@app.post("/api/v1/research/sessions", status_code=201)
def create_research_session(payload: ResearchSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(IPO, payload.ipo_id): raise HTTPException(404, "IPO not found")
    session = ResearchSession(user_id=user.id, ipo_id=payload.ipo_id, title=payload.title); db.add(session); db.commit(); db.refresh(session)
    return {"id": session.id, "ipo_id": session.ipo_id, "title": session.title, "created_at": session.created_at}


@app.post("/api/v1/research/sessions/{session_id}/messages", status_code=201)
def research_message(session_id: int, payload: ResearchQuestion, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(request, "agent", 20)
    session = db.scalar(select(ResearchSession).where(ResearchSession.id == session_id, ResearchSession.user_id == user.id))
    if not session: raise HTTPException(404, "Research session not found")
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).where(IPO.id == session.ipo_id))
    db.add(ResearchMessage(session_id=session.id, role="user", content=payload.content)); result = answer_question(db, ipo, payload.content)
    db.add(ResearchMessage(session_id=session.id, role="assistant", content=result["answer"], tool_trace=result["tool_trace"], citations=result["claims"])); db.commit()
    return result


@app.get("/api/v1/research/sessions/{session_id}")
def get_research_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.scalar(select(ResearchSession).where(ResearchSession.id == session_id, ResearchSession.user_id == user.id))
    if not session: raise HTTPException(404, "Research session not found")
    messages = db.scalars(select(ResearchMessage).where(ResearchMessage.session_id == session.id).order_by(ResearchMessage.created_at)).all()
    return {"id": session.id, "title": session.title, "ipo_id": session.ipo_id, "messages": [{"role": m.role, "content": m.content, "tool_trace": m.tool_trace, "citations": m.citations, "created_at": m.created_at} for m in messages]}


@app.get("/api/v1/watchlist")
def watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Watchlist).where(Watchlist.user_id == user.id)).all()
    items = []
    for row in rows:
        ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).where(IPO.id == row.ipo_id))
        if not ipo:
            continue
        score = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo.id))
        items.append({
            "watchlist_id": row.id,
            "ipo_id": row.ipo_id,
            "name": ipo.company.name,
            "sector": ipo.company.sector,
            "status": ipo.status,
            "score": score.overall_score if score else None,
            "issue_size_crore": as_float(ipo.issue_size),
            "price_band": [as_float(ipo.price_low), as_float(ipo.price_high)],
            "saved_at": str(row.created_at),
        })
    return items


@app.post("/api/v1/watchlist", status_code=201)
def add_watchlist(payload: WatchlistRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(IPO, payload.ipo_id): raise HTTPException(404, "IPO not found")
    existing = db.scalar(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.ipo_id == payload.ipo_id))
    if existing: return {"id": existing.id, "ipo_id": existing.ipo_id, "created": False}
    row = Watchlist(user_id=user.id, ipo_id=payload.ipo_id); db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "ipo_id": row.ipo_id, "created": True}


@app.post("/api/v1/valuation/dcf")
def dcf(scenario: DCFScenario):
    if scenario.terminal_growth >= scenario.discount_rate: raise HTTPException(422, "Terminal growth must be lower than discount rate")
    cashflows, revenue = [], scenario.revenue
    for year in range(1, scenario.years + 1):
        revenue *= 1 + scenario.growth_rate
        fcf = revenue * scenario.ebitda_margin * (1 - scenario.tax_rate)
        cashflows.append({"year": year, "revenue": round(revenue, 2), "free_cash_flow": round(fcf, 2), "present_value": round(fcf / ((1 + scenario.discount_rate) ** year), 2)})
    terminal_value = cashflows[-1]["free_cash_flow"] * (1 + scenario.terminal_growth) / (scenario.discount_rate - scenario.terminal_growth)
    terminal_pv = terminal_value / ((1 + scenario.discount_rate) ** scenario.years)
    return {"enterprise_value_crore": round(sum(item["present_value"] for item in cashflows) + terminal_pv, 2), "terminal_value_pv_crore": round(terminal_pv, 2), "cashflows": cashflows, "methodology": "Illustrative unlevered scenario, not investment advice."}
