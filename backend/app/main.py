from __future__ import annotations
import hashlib
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from collections import defaultdict
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import redis
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
import os

logger = logging.getLogger("api")
from sqlalchemy import select, delete, or_, case, func
from sqlalchemy.orm import Session, joinedload
from app.analytics.financials import enterprise_value, margin, revenue_cagr
from app.lifecycle import compute_lifecycle_status
from app.core.config import get_settings
from app.core.security import create_token, decode_token, get_current_user, hash_password, verify_password
from app.db import Base, engine, get_db
from app.models import Company, Document, FinancialMetric, FinancialPeriod, IPO, IPOSCore, Job, ResearchMessage, ResearchSession, RiskFactor, User, ValuationMetric, Watchlist
from app.schemas import DCFInput, LoginRequest, RegisterRequest, ResearchQuestion, ResearchSessionRequest, TokenResponse, WatchlistRequest
from app.seed import seed_demo_data
from app.services.documents import process_document
from app.services.research import answer_question, peer_comparison
from app.workers import process_document_task

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    request_id = request.headers.get("x-request-id", "unknown")
    logger.error(f"Unexpected error at {request.url.path} [Req: {request_id}]: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An unexpected internal error occurred. Please try again later."})

try:
    redis_client = redis.from_url(settings.redis_url)
    redis_client.ping()
except Exception as e:
    logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
    redis_client = None


@app.on_event("startup")
def startup() -> None:
    settings.ensure_storage()
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
        with next(get_db()) as db:
            seed_demo_data(db, include_live=True)
            # Lightweight local lifecycle reconciliation (fast, no HTTP/Celery/Redis/LLM)
            try:
                from app.lifecycle import reconcile_db_lifecycles
                reconcile_db_lifecycles(db)
            except Exception as e:
                logger.warning(f"Startup lifecycle reconciliation skipped or failed: {e}")
    else:
        alembic_ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        script = ScriptDirectory.from_config(alembic_cfg)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head()
            if current_rev != head_rev:
                raise RuntimeError(f"Database schema is not at alembic head. Current: {current_rev}, Expected: {head_rev}")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


def enforce_rate_limit(request: Request, bucket: str, limit: int = 15) -> None:
    import sys
    if "pytest" in sys.modules or settings.environment == "development":
        return
    client_id = request.client.host if request.client else "unknown"
    key = f"rate_limit:{bucket}:{client_id}"
    
    if redis_client:
        try:
            current = redis_client.incr(key)
            if current == 1:
                redis_client.expire(key, 60)
            if current > limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
        except redis.RedisError as e:
            logger.error(f"Redis rate limiting failed: {e}")
            raise HTTPException(status_code=503, detail="Service Unavailable (Rate Limiter)")
    else:
        raise HTTPException(status_code=503, detail="Service Unavailable (Rate Limiter)")


def as_float(value):
    return float(value) if value is not None else None


def ipo_payload(ipo: IPO, score: IPOSCore | None = None) -> dict:
    sector = ipo.company.sector if ipo.company.sector and ipo.company.sector != "Unknown" else None
    logo_url = getattr(ipo.company, "logo_url", None) or getattr(ipo, "logo_url", None)
    effective_open = ipo.open_date or ipo.issue_date
    from app.lifecycle import compute_lifecycle_status
    effective_status = getattr(ipo, "_effective_status", None) or compute_lifecycle_status(
        open_date=ipo.open_date,
        close_date=ipo.close_date,
        listing_date=ipo.listing_date,
        issue_date=ipo.issue_date,
        static_status=ipo.status,
    )
    return {
        "id": ipo.id,
        "company_id": ipo.company_id,
        "name": ipo.company.name,
        "slug": ipo.company.slug,
        "sector": sector,
        "exchange": ipo.company.exchange,
        "status": effective_status,
        "listing_segment": ipo.listing_segment,
        "issue_size_crore": as_float(ipo.issue_size),
        "price_band": [as_float(ipo.price_low), as_float(ipo.price_high)],
        "lot_size": ipo.lot_size,
        "min_investment": as_float(ipo.min_investment),
        "face_value": as_float(ipo.face_value),
        "shares_offered": ipo.shares_offered,
        "issue_date": str(ipo.issue_date) if ipo.issue_date else None,
        "open_date": str(effective_open) if effective_open else None,
        "close_date": str(ipo.close_date) if ipo.close_date else None,
        "listing_date": str(ipo.listing_date) if ipo.listing_date else None,
        "data_source": ipo.data_source,
        "score": score.overall_score if score else None,
        "logo_url": logo_url,
    }


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
    is_prod = settings.environment == "production"
    response.set_cookie("refresh_token", refresh, httponly=True, secure=is_prod, samesite="lax", path="/", max_age=settings.jwt_refresh_days * 86400)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@app.get("/api/v1/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "authenticated": True}


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
    user.refresh_token_version += 1; db.commit(); response.delete_cookie("refresh_token", path="/")


@app.get("/api/v1/ipos")
def list_ipos(q: str | None = None, sector: str | None = None, status_filter: str | None = None, page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    from datetime import date, timedelta
    from app.lifecycle import compute_lifecycle_status

    statement = select(IPO).join(Company).options(joinedload(IPO.company)).order_by(IPO.issue_date.desc().nullslast(), IPO.id.desc())
    if q: statement = statement.where((Company.name.ilike(f"%{q}%")) | (Company.sector.ilike(f"%{q}%")))
    if sector: statement = statement.where(Company.sector == sector)

    all_records = db.scalars(statement).unique().all()
    today = date.today()
    recent_closed_date = today - timedelta(days=settings.recently_closed_days)
    recent_listed_date = today - timedelta(days=settings.recently_listed_days)

    filtered_records = []
    for ipo in all_records:
        eff_status = compute_lifecycle_status(
            open_date=ipo.open_date,
            close_date=ipo.close_date,
            listing_date=ipo.listing_date,
            issue_date=ipo.issue_date,
            static_status=ipo.status,
        )
        setattr(ipo, "_effective_status", eff_status)

        if status_filter:
            if status_filter.lower() == "all" or eff_status.lower() == status_filter.lower():
                filtered_records.append(ipo)
        else:
            # Default feed: Ongoing, Upcoming, Recent Closed within window, Recent Listed within window
            ref_close = ipo.close_date or ipo.issue_date
            ref_listed = ipo.listing_date or ipo.issue_date
            if eff_status in ("Ongoing", "Upcoming"):
                filtered_records.append(ipo)
            elif eff_status == "Closed" and (ref_close is None or ref_close >= recent_closed_date):
                filtered_records.append(ipo)
            elif eff_status == "Listed" and (ref_listed is None or ref_listed >= recent_listed_date):
                filtered_records.append(ipo)

    start = (max(page, 1) - 1) * min(page_size, 50)
    page_records = filtered_records[start : start + min(page_size, 50)]
    scores = {item.ipo_id: item for item in db.scalars(select(IPOSCore)).all()}
    return {"items": [ipo_payload(ipo, scores.get(ipo.id)) for ipo in page_records], "page": page, "page_size": min(page_size, 50), "total": len(filtered_records)}

@app.get("/api/v1/ipos/summary")
def ipos_summary(db: Session = Depends(get_db)):
    """Return count of IPOs grouped by lifecycle status."""
    from app.lifecycle import compute_lifecycle_status
    ipos = db.scalars(select(IPO)).all()
    counts = {"Upcoming": 0, "Ongoing": 0, "Closed": 0, "Listed": 0}
    for ipo in ipos:
        eff = compute_lifecycle_status(
            open_date=ipo.open_date,
            close_date=ipo.close_date,
            listing_date=ipo.listing_date,
            issue_date=ipo.issue_date,
            static_status=ipo.status,
        )
        if eff in counts:
            counts[eff] += 1
    return {
        "upcoming": counts["Upcoming"],
        "ongoing": counts["Ongoing"],
        "closed": counts["Closed"],
        "listed": counts["Listed"],
        "total": len(ipos),
    }


@app.get("/api/v1/search")
def search_global(q: str = "", limit: int = 8, db: Session = Depends(get_db)):
    """Global search across Company, IPO, and filing metadata."""
    clean_q = q.strip()
    if not clean_q:
        return {"items": [], "total": 0, "query": clean_q}
    
    clean_q = clean_q[:100]
    bounded_limit = max(1, min(limit, 20))
    
    doc_subq = select(Document.ipo_id).where(
        (Document.ipo_id.isnot(None)) & 
        (
            (Document.filename.ilike(f"%{clean_q}%")) | 
            (Document.type.ilike(f"%{clean_q}%"))
        )
    )
    
    condition = or_(
        Company.name.ilike(f"%{clean_q}%"),
        Company.slug.ilike(f"%{clean_q}%"),
        Company.sector.ilike(f"%{clean_q}%"),
        Company.exchange.ilike(f"%{clean_q}%"),
        IPO.status.ilike(f"%{clean_q}%"),
        IPO.listing_segment.ilike(f"%{clean_q}%"),
        IPO.id.in_(doc_subq)
    )
    
    ranking = case(
        (func.lower(Company.name) == clean_q.lower(), 1),
        (func.lower(Company.name).startswith(clean_q.lower()), 2),
        (func.lower(Company.slug).startswith(clean_q.lower()), 3),
        (Company.name.ilike(f"%{clean_q}%"), 4),
        (Company.sector.ilike(f"%{clean_q}%"), 5),
        else_=6
    )
    
    statement = (
        select(IPO)
        .join(Company)
        .options(joinedload(IPO.company))
        .where(condition)
        .order_by(ranking, IPO.issue_date.desc().nullslast(), IPO.id.desc())
        .limit(bounded_limit)
    )
    
    records = db.scalars(statement).unique().all()
    if not records:
        return {"items": [], "total": 0, "query": clean_q}
        
    ipo_ids = [r.id for r in records]
    scores = {s.ipo_id: s for s in db.scalars(select(IPOSCore).where(IPOSCore.ipo_id.in_(ipo_ids))).all()}
    doc_rows = db.scalars(select(Document).where(Document.ipo_id.in_(ipo_ids))).all()
    ipo_docs = {}
    for d in doc_rows:
        if d.ipo_id and d.ipo_id not in ipo_docs:
            ipo_docs[d.ipo_id] = d
            
    items = []
    for ipo in records:
        sc = scores.get(ipo.id)
        doc = ipo_docs.get(ipo.id)
        eff_status = getattr(ipo, "_effective_status", None) or compute_lifecycle_status(
            open_date=ipo.open_date,
            close_date=ipo.close_date,
            listing_date=ipo.listing_date,
            issue_date=ipo.issue_date,
            static_status=ipo.status,
        )
        items.append({
            "id": ipo.id,
            "company_id": ipo.company_id,
            "name": ipo.company.name,
            "slug": ipo.company.slug,
            "sector": ipo.company.sector,
            "status": eff_status,
            "listing_segment": ipo.listing_segment or ("SME" if "sme" in (ipo.company.exchange or "").lower() else "Mainboard"),
            "exchange": ipo.company.exchange or "NSE/BSE",
            "score": sc.overall_score if sc else None,
            "price_band": [as_float(ipo.price_low), as_float(ipo.price_high)],
            "issue_size_crore": as_float(ipo.issue_size),
            "logo_url": getattr(ipo.company, "logo_url", None) or getattr(ipo, "logo_url", None),
            "filing_type": doc.type if doc else None,
            "has_filing": doc is not None,
        })
        
    return {"items": items, "total": len(items), "query": clean_q}


@app.post("/api/v1/ipos/sync")
def sync_ipos_endpoint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Trigger an IPO data sync from the configured provider."""
    from app.providers import SeedFileProvider
    from app.providers.live import LiveIPOProvider
    from app.services.sync import sync_ipos
    
    # 1. Sync seed data for deep analytics
    seed_report = sync_ipos(db, SeedFileProvider())
    
    # 2. Sync live data for current lifecycle and metadata
    live_report = sync_ipos(db, LiveIPOProvider())
    
    return {
        "seed": seed_report.to_dict(),
        "live": live_report.to_dict(),
        "total_processed": seed_report.total_processed + live_report.total_processed
    }


@app.get("/api/v1/ipos/{ipo_id}")
def get_ipo(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).where(IPO.id == ipo_id))
    if not ipo: raise HTTPException(404, "IPO not found")
    score = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    return {**ipo_payload(ipo, score), "description": ipo.company.description, "fresh_issue_crore": as_float(ipo.fresh_issue), "ofs_crore": as_float(ipo.ofs)}


from app.analytics.financials import margin, revenue_cagr, roe, roce, net_debt, net_debt_to_ebitda, valuation_multiples, extract_2y_cagr, yoy_revenue_growth, ipo_implied_market_cap, derive_post_issue_shares

@app.get("/api/v1/ipos/{ipo_id}/financials")
def financials(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    rows = db.execute(select(FinancialPeriod, FinancialMetric).join(FinancialMetric).where(FinancialPeriod.company_id == ipo.company_id).order_by(FinancialPeriod.period_end)).all()
    
    items = []
    prev_revenue = None
    for period, metric in rows:
        rev = as_float(metric.revenue)
        ebitda = as_float(metric.ebitda)
        ebit = as_float(metric.ebit)
        pat = as_float(metric.pat)
        eq = as_float(metric.equity)
        debt = as_float(metric.total_debt)
        cash = as_float(metric.cash)
        
        items.append({
            "period_type": period.period_type,
            "fiscal_year": period.fiscal_year,
            "period_end": str(period.period_end),
            "revenue": rev,
            "ebitda": ebitda,
            "ebit": ebit,
            "pat": pat,
            "equity": eq,
            "debt": debt,
            "cash": cash,
            "ebitda_margin": margin(ebitda, rev),
            "ebit_margin": margin(ebit, rev),
            "pat_margin": margin(pat, rev),
            "roe": roe(pat, eq),
            "roce": roce(ebit, debt, eq, cash),
            "net_debt": net_debt(debt, cash),
            "net_debt_ebitda": net_debt_to_ebitda(debt, cash, ebitda),
            "yoy_revenue_growth": yoy_revenue_growth(prev_revenue, rev) if prev_revenue is not None else None
        })
        prev_revenue = rev

    return {"items": items, "revenue_cagr_2y": extract_2y_cagr(items)}


@app.get("/api/v1/ipos/{ipo_id}/valuation")
def valuation(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    
    item = db.scalar(select(ValuationMetric).where(ValuationMetric.company_id == ipo.company_id, ValuationMetric.context == "CURRENT_MARKET").order_by(ValuationMetric.date.desc()))
    
    row = db.execute(select(FinancialPeriod, FinancialMetric).join(FinancialMetric).where(FinancialPeriod.company_id == ipo.company_id).order_by(FinancialPeriod.period_end.desc()).limit(1)).first()
    fp, fm = row if row else (None, None)
    
    debt = as_float(fm.total_debt) if fm else None
    cash = as_float(fm.cash) if fm else None
    revenue = as_float(fm.revenue) if fm else None
    ebitda = as_float(fm.ebitda) if fm else None
    pat = as_float(fm.pat) if fm else None
    
    current_market = None
    if item:
        mcap = as_float(item.market_cap)
        multiples = valuation_multiples(mcap, debt, cash, revenue, ebitda, pat)
        current_market = {
            "market_cap": multiples["market_cap"],
            "enterprise_value": multiples["enterprise_value"],
            "pe": multiples["pe"],
            "ps": multiples["ps"],
            "ev_ebitda": multiples["ev_ebitda"],
            "ev_sales": multiples["ev_sales"],
            "as_of": str(item.date),
            "financial_period": {
                "fiscal_year": fp.fiscal_year,
                "period_type": fp.period_type,
                "period_end": str(fp.period_end)
            } if fp else None
        }

    annual_row = db.execute(select(FinancialPeriod, FinancialMetric).join(FinancialMetric).where(FinancialPeriod.company_id == ipo.company_id, FinancialPeriod.period_type == "Annual").order_by(FinancialPeriod.period_end.desc()).limit(1)).first()
    ipo_fp, ipo_fm = annual_row if annual_row else (None, None)
    
    ipo_debt = as_float(ipo_fm.total_debt) if ipo_fm else None
    ipo_cash = as_float(ipo_fm.cash) if ipo_fm else None
    ipo_revenue = as_float(ipo_fm.revenue) if ipo_fm else None
    ipo_ebitda = as_float(ipo_fm.ebitda) if ipo_fm else None
    ipo_pat = as_float(ipo_fm.pat) if ipo_fm else None
    
    post_issue = ipo.post_issue_shares
    if post_issue is None and ipo.pre_issue_shares is not None and ipo.fresh_issue_shares is not None:
        post_issue = derive_post_issue_shares(ipo.pre_issue_shares, ipo.fresh_issue_shares)
    
    low_mcap = ipo_implied_market_cap(as_float(ipo.price_low), post_issue)
    low_mults = valuation_multiples(low_mcap, ipo_debt, ipo_cash, ipo_revenue, ipo_ebitda, ipo_pat)
    
    high_mcap = ipo_implied_market_cap(as_float(ipo.price_high), post_issue)
    high_mults = valuation_multiples(high_mcap, ipo_debt, ipo_cash, ipo_revenue, ipo_ebitda, ipo_pat)
    
    return {
        "CURRENT_MARKET": current_market,
        "IPO_AT_ISSUE": {
            "post_issue_shares": post_issue,
            "financial_period": {
                "fiscal_year": ipo_fp.fiscal_year,
                "period_type": ipo_fp.period_type,
                "period_end": str(ipo_fp.period_end)
            } if ipo_fp else None,
            "lower_band": {
                "price": as_float(ipo.price_low),
                "implied_market_cap": low_mults["market_cap"],
                "enterprise_value": low_mults["enterprise_value"],
                "pe": low_mults["pe"],
                "ps": low_mults["ps"],
                "ev_ebitda": low_mults["ev_ebitda"],
                "ev_sales": low_mults["ev_sales"]
            },
            "upper_band": {
                "price": as_float(ipo.price_high),
                "implied_market_cap": high_mults["market_cap"],
                "enterprise_value": high_mults["enterprise_value"],
                "pe": high_mults["pe"],
                "ps": high_mults["ps"],
                "ev_ebitda": high_mults["ev_ebitda"],
                "ev_sales": high_mults["ev_sales"]
            }
        }
    }


@app.get("/api/v1/ipos/{ipo_id}/peers")
def peers(ipo_id: int, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404, "IPO not found")
    
    from app.models import Peer
    peer_ids = db.scalars(select(Peer.peer_company_id).where(Peer.company_id == ipo.company_id, Peer.active == True)).all()
    
    detailed_peers = []
    for pid in peer_ids:
        comp = db.get(Company, pid)
        vm = db.scalar(select(ValuationMetric).where(ValuationMetric.company_id == pid).order_by(ValuationMetric.date.desc()))
        if comp and vm:
            detailed_peers.append({
                "name": comp.name,
                "sector": comp.sector,
                "context": "CURRENT_MARKET",
                "valuation_date": str(vm.date),
                "market_cap": as_float(vm.market_cap),
                "pe": vm.pe,
                "ps": vm.ps,
                "ev_ebitda": vm.ev_ebitda,
                "ev_sales": vm.ev_sales,
            })
            
    # Fetch target IPO_AT_ISSUE bands using the valuation logic
    val_data = valuation(ipo_id, db)
    ipo_at_issue = val_data.get("IPO_AT_ISSUE", {})
    lower_band = ipo_at_issue.get("lower_band", {})
    upper_band = ipo_at_issue.get("upper_band", {})
    current_market = val_data.get("CURRENT_MARKET")
    
    from app.lifecycle import compute_lifecycle_status
    eff_status = getattr(ipo, "_effective_status", None) or compute_lifecycle_status(
        open_date=ipo.open_date,
        close_date=ipo.close_date,
        listing_date=ipo.listing_date,
        issue_date=ipo.issue_date,
        static_status=ipo.status,
    )
    target = {
        "name": ipo.company.name,
        "sector": ipo.company.sector,
        "context": "CURRENT_MARKET" if current_market and eff_status == "Listed" else "IPO_AT_ISSUE",
        "current_market": current_market,
        "lower_band": lower_band,
        "upper_band": upper_band
    }
    
    from app.analytics.financials import calculate_peer_statistics, calculate_band_comparison, premium_discount
    peer_stats = calculate_peer_statistics(detailed_peers)
    comparison = calculate_band_comparison(lower_band, upper_band, peer_stats)
    if current_market:
        comparison["current_market"] = {
            k: premium_discount(current_market.get(k), peer_stats.get(k, {}).get("median"))
            for k in ["pe", "ps", "ev_ebitda", "ev_sales"]
        }
            
    return {
        "target": target,
        "peers": detailed_peers,
        "peer_statistics": peer_stats,
        "comparison": comparison
    }


@app.get("/api/v1/ipos/{ipo_id}/score")
def score(ipo_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    if not item: raise HTTPException(404, "Score not found")
    
    return {
        "overall_score": item.overall_score,
        "dimensions": {
            "financial_quality": item.financial_quality_score,
            "growth": item.growth_score,
            "valuation": item.valuation_score,
            "balance_sheet": item.balance_sheet_score,
            "business_quality": item.business_quality_score,
            "risk": item.risk_score
        },
        "coverage": item.coverage,
        "explanations": item.explanations,
        "methodology_version": item.methodology_version
    }


@app.get("/api/v1/ipos/{ipo_id}/risks")
def risks(ipo_id: int, db: Session = Depends(get_db)):
    return [{"id": item.id, "category": item.category, "severity": item.severity, "summary": item.summary, "source_page": item.source_page} for item in db.scalars(select(RiskFactor).where(RiskFactor.ipo_id == ipo_id)).all()]


@app.post("/api/v1/ipos/{ipo_id}/enrich", status_code=200)
def enrich_ipo(ipo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Enrich an IPO with financial data and risk factors extracted from its filing documents.

    Pipeline: find Document → financial extraction → risk extraction → score regeneration.
    Requires at least one completed Document linked to the IPO's company.
    """
    ipo = db.scalar(select(IPO).options(joinedload(IPO.company)).where(IPO.id == ipo_id))
    if not ipo:
        raise HTTPException(404, "IPO not found")

    # Find a completed document for this company/IPO
    document = db.scalar(
        select(Document).where(
            ((Document.company_id == ipo.company_id) | (Document.ipo_id == ipo_id)),
            Document.processing_status == "completed",
        ).order_by(Document.id.desc())
    )
    if not document:
        return {
            "status": "no_document",
            "message": "No processed filing document found for this IPO. Upload a DRHP/RHP first.",
            "financial_extraction": None,
            "risk_extraction": None,
            "score_regenerated": False,
        }

    from app.services.financial_extractor import extract_financials
    from app.services.risk_extractor import extract_risks

    # 1. Financial extraction
    fin_result = extract_financials(db, document.id, ipo.company_id)

    # 2. Risk extraction
    risk_result = extract_risks(db, document.id, ipo.id)

    # 3. Score regeneration (only if we have some extracted data)
    score_regenerated = False
    score_result = None
    has_financials = fin_result.periods_extracted > 0 or fin_result.periods_updated > 0
    has_risks = risk_result.risks_extracted > 0

    if has_financials or has_risks:
        try:
            from app.analytics.scoring import generate_ipo_score
            score_obj = generate_ipo_score(db, ipo_id)
            db.commit()
            score_regenerated = True
            score_result = {
                "overall_score": score_obj.overall_score,
                "methodology_version": score_obj.methodology_version,
                "dimensions_available": sum(1 for d in [
                    score_obj.financial_quality_score,
                    score_obj.growth_score,
                    score_obj.valuation_score,
                    score_obj.balance_sheet_score,
                    score_obj.business_quality_score,
                    score_obj.risk_score,
                ] if d is not None),
            }
        except Exception as exc:
            logger.warning("Score regeneration failed for IPO %d: %s", ipo_id, exc)
            db.rollback()
    else:
        db.commit()

    return {
        "status": "completed",
        "financial_extraction": fin_result.to_dict(),
        "risk_extraction": risk_result.to_dict(),
        "score_regenerated": score_regenerated,
        "score": score_result,
    }


@app.get("/api/v1/ipos/{ipo_id}/coverage")
def coverage(ipo_id: int, db: Session = Depends(get_db)):
    """Return the data coverage state for an IPO.

    Coverage tiers:
    - computable: at least 1 score dimension is non-NULL
    - reasonable: 3+ dimensions
    - good: 4+ dimensions
    - full: 6 dimensions
    """
    ipo = db.scalar(select(IPO).where(IPO.id == ipo_id))
    if not ipo:
        raise HTTPException(404, "IPO not found")

    # Filing available
    filing_available = db.scalar(
        select(Document.id).where(
            ((Document.company_id == ipo.company_id) | (Document.ipo_id == ipo_id)),
            Document.processing_status == "completed",
        )
    ) is not None

    # Financials extracted
    financials_extracted = db.scalar(
        select(FinancialMetric.id)
        .join(FinancialPeriod)
        .where(FinancialPeriod.company_id == ipo.company_id)
    ) is not None

    # Count financial periods
    from sqlalchemy import func
    financial_period_count = db.scalar(
        select(func.count(FinancialPeriod.id))
        .where(FinancialPeriod.company_id == ipo.company_id)
    ) or 0

    # Risks extracted
    risks_extracted = db.scalar(
        select(RiskFactor.id).where(RiskFactor.ipo_id == ipo_id)
    ) is not None

    risk_count = db.scalar(
        select(func.count(RiskFactor.id)).where(RiskFactor.ipo_id == ipo_id)
    ) or 0

    # Valuation ready (needs post_issue_shares + financials)
    valuation_ready = (
        ipo.post_issue_shares is not None
        and financials_extracted
    )

    # Score state
    score_obj = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo_id))
    score_ready = score_obj is not None and score_obj.overall_score is not None

    # Score readiness tier
    dimensions_available = 0
    readiness_tier = "no_score"
    if score_obj:
        dims = [
            score_obj.financial_quality_score,
            score_obj.growth_score,
            score_obj.valuation_score,
            score_obj.balance_sheet_score,
            score_obj.business_quality_score,
            score_obj.risk_score,
        ]
        dimensions_available = sum(1 for d in dims if d is not None)

        if dimensions_available >= 6:
            readiness_tier = "full"
        elif dimensions_available >= 4:
            readiness_tier = "good"
        elif dimensions_available >= 3:
            readiness_tier = "reasonable"
        elif dimensions_available >= 1:
            readiness_tier = "computable"
        else:
            readiness_tier = "no_score"

    fully_covered = (
        filing_available
        and financials_extracted
        and risks_extracted
        and score_ready
        and dimensions_available >= 4
    )

    return {
        "ipo_id": ipo_id,
        "filing_available": filing_available,
        "financials_extracted": financials_extracted,
        "financial_period_count": financial_period_count,
        "risks_extracted": risks_extracted,
        "risk_count": risk_count,
        "valuation_ready": valuation_ready,
        "score_ready": score_ready,
        "score_readiness_tier": readiness_tier,
        "dimensions_available": dimensions_available,
        "fully_covered": fully_covered,
    }


@app.post("/api/v1/documents", status_code=202)
def upload_document(request: Request, file: UploadFile = File(...), ipo_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(request, "upload", 8)
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(415, "Only PDF filings are accepted")
    content = file.file.read()
    if len(content) > 30 * 1024 * 1024: raise HTTPException(413, "Maximum upload size is 30 MB")
    
    filename = file.filename or "document.pdf"
    checksum = hashlib.sha256(content).hexdigest()
    
    # Deduplication: match checksum AND (must be public OR owned by the uploading user)
    from sqlalchemy import or_
    existing = db.scalar(select(Document).where(Document.checksum == checksum, or_(Document.is_public == True, Document.user_id == user.id)))
    if existing: return {"document_id": existing.id, "status": existing.processing_status, "deduplicated": True}
    
    ipo = db.get(IPO, ipo_id) if ipo_id else None
    is_public = ipo_id is not None  # Public if tied to an IPO, private user upload otherwise
    
    target = settings.ensure_storage() / f"{checksum}.pdf"
    if not target.exists():
        target.write_bytes(content)
        
    document = Document(
        ipo_id=ipo_id, company_id=ipo.company_id if ipo else None,
        user_id=user.id, is_public=is_public, filename=filename,
        type="RHP", storage_url=str(target.resolve()), checksum=checksum
    )
    db.add(document); db.flush(); db.add(Job(job_type="document_processing", entity_id=document.id)); db.commit()
    if settings.task_eager:
        process_document(db, document.id)
    else:
        process_document_task.delay(document.id)
    return {"document_id": document.id, "status": "queued", "deduplicated": False}


@app.get("/api/v1/documents/{document_id}/status")
def document_status(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document: raise HTTPException(404, "Document not found")
    if not document.is_public and document.user_id != user.id:
        raise HTTPException(404, "Document not found")
    return {"id": document.id, "status": document.processing_status, "page_count": document.page_count, "error": document.failure_reason}


@app.get("/api/v1/documents/{document_id}/sources")
def document_sources(document_id: int, page: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document: raise HTTPException(404, "Document not found")
    if not document.is_public and document.user_id != user.id:
        raise HTTPException(404, "Document not found")
        
    from app.models import Source
    statement = select(Source).where(Source.document_id == document_id, Source.is_empty == False)
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


@app.get("/api/v1/research/sessions")
def list_research_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(ResearchSession)
        .where(ResearchSession.user_id == user.id)
        .order_by(ResearchSession.created_at.desc())
    ).all()
    return [{"id": s.id, "ipo_id": s.ipo_id, "title": s.title, "created_at": s.created_at} for s in sessions]


@app.get("/api/v1/research/sessions/{session_id}")
def get_research_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.scalar(select(ResearchSession).where(ResearchSession.id == session_id, ResearchSession.user_id == user.id))
    if not session: raise HTTPException(404, "Research session not found")
    messages = db.scalars(select(ResearchMessage).where(ResearchMessage.session_id == session.id).order_by(ResearchMessage.created_at)).all()
    return {"id": session.id, "title": session.title, "ipo_id": session.ipo_id, "messages": [{"role": m.role, "content": m.content, "tool_trace": m.tool_trace, "citations": m.citations, "created_at": m.created_at} for m in messages]}


@app.delete("/api/v1/research/sessions/{session_id}", status_code=204)
def delete_research_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.scalar(select(ResearchSession).where(ResearchSession.id == session_id, ResearchSession.user_id == user.id))
    if not session: raise HTTPException(404, "Research session not found")
    db.execute(delete(ResearchMessage).where(ResearchMessage.session_id == session.id))
    db.delete(session)
    db.commit()
    return None


@app.get("/api/v1/watchlist")
def watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Watchlist).where(Watchlist.user_id == user.id)).all()
    if not rows:
        return []
    
    ipo_ids = [row.ipo_id for row in rows]
    ipos = {ipo.id: ipo for ipo in db.scalars(
        select(IPO).options(joinedload(IPO.company)).where(IPO.id.in_(ipo_ids))
    ).unique().all()}
    
    scores = {score.ipo_id: score for score in db.scalars(
        select(IPOSCore).where(IPOSCore.ipo_id.in_(ipo_ids))
    ).all()}
    
    items = []
    for row in rows:
        ipo = ipos.get(row.ipo_id)
        if not ipo:
            continue
        score = scores.get(ipo.id)
        from app.lifecycle import compute_lifecycle_status
        eff_status = getattr(ipo, "_effective_status", None) or compute_lifecycle_status(
            open_date=ipo.open_date,
            close_date=ipo.close_date,
            listing_date=ipo.listing_date,
            issue_date=ipo.issue_date,
            static_status=ipo.status,
        )
        items.append({
            "watchlist_id": row.id,
            "ipo_id": row.ipo_id,
            "name": ipo.company.name,
            "slug": ipo.company.slug,
            "sector": ipo.company.sector,
            "status": eff_status,
            "listing_segment": ipo.listing_segment or ("SME" if "sme" in (ipo.company.exchange or "").lower() else "Mainboard"),
            "exchange": ipo.company.exchange or "NSE/BSE",
            "score": score.overall_score if score else None,
            "issue_size_crore": as_float(ipo.issue_size),
            "price_band": [as_float(ipo.price_low), as_float(ipo.price_high)],
            "open_date": str(ipo.open_date) if ipo.open_date else None,
            "close_date": str(ipo.close_date) if ipo.close_date else None,
            "listing_date": str(ipo.listing_date) if ipo.listing_date else None,
            "logo_url": getattr(ipo.company, "logo_url", None) or getattr(ipo, "logo_url", None),
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


@app.delete("/api/v1/watchlist/{item_id}", status_code=204)
def delete_watchlist(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == user.id,
            (Watchlist.id == item_id) | (Watchlist.ipo_id == item_id)
        )
    )
    if not row:
        raise HTTPException(404, "Watchlist item not found")
    db.delete(row)
    db.commit()
    return None


from app.analytics.dcf import run_dcf, calculate_sensitivity_matrix

@app.post("/api/v1/ipos/{ipo_id}/dcf")
def dcf(ipo_id: int, scenario: DCFInput, db: Session = Depends(get_db)):
    ipo = db.get(IPO, ipo_id)
    if not ipo:
        raise HTTPException(404, "IPO not found")
        
    annual_row = db.execute(select(FinancialPeriod, FinancialMetric).join(FinancialMetric).where(FinancialPeriod.company_id == ipo.company_id, FinancialPeriod.period_type == "Annual").order_by(FinancialPeriod.period_end.desc()).limit(1)).first()
    if not annual_row:
        raise HTTPException(422, "A source-backed annual financial period is required for DCF base revenue.")
    
    fp, fm = annual_row
    base_revenue = as_float(fm.revenue)
    if base_revenue is None:
        raise HTTPException(422, "Base annual revenue is required for DCF.")
        
    debt = as_float(fm.total_debt)
    cash = as_float(fm.cash)
    
    post_issue = ipo.post_issue_shares
    if post_issue is None and ipo.pre_issue_shares is not None and ipo.fresh_issue_shares is not None:
        post_issue = derive_post_issue_shares(ipo.pre_issue_shares, ipo.fresh_issue_shares)

    res = run_dcf(
        base_revenue=base_revenue,
        revenue_growth_rate=scenario.revenue_growth_rate,
        ebitda_margin=scenario.ebitda_margin,
        tax_rate=scenario.tax_rate,
        d_and_a_pct=scenario.d_and_a_pct_of_revenue,
        capex_pct=scenario.capex_pct_of_revenue,
        nwc_pct=scenario.change_in_nwc_pct_of_revenue,
        wacc=scenario.discount_rate,
        terminal_growth_rate=scenario.terminal_growth_rate,
        years=scenario.years
    )
    
    ev = res["enterprise_value"]
    equity_value = None
    intrinsic_value_per_share = None
    upside_lower = None
    upside_upper = None
    
    if debt is not None and cash is not None:
        equity_value = round(ev + cash - debt, 2)
        if post_issue:
            intrinsic_value_per_share = round((equity_value * 10000000.0) / post_issue, 2)
            if ipo.price_low and as_float(ipo.price_low) > 0:
                upside_lower = round((intrinsic_value_per_share / as_float(ipo.price_low) - 1) * 100, 2)
            if ipo.price_high and as_float(ipo.price_high) > 0:
                upside_upper = round((intrinsic_value_per_share / as_float(ipo.price_high) - 1) * 100, 2)
                
    sensitivity = calculate_sensitivity_matrix(
        base_revenue=base_revenue,
        revenue_growth_rate=scenario.revenue_growth_rate,
        ebitda_margin=scenario.ebitda_margin,
        tax_rate=scenario.tax_rate,
        d_and_a_pct=scenario.d_and_a_pct_of_revenue,
        capex_pct=scenario.capex_pct_of_revenue,
        nwc_pct=scenario.change_in_nwc_pct_of_revenue,
        base_wacc=scenario.discount_rate,
        base_terminal_growth=scenario.terminal_growth_rate,
        years=scenario.years,
        debt=debt,
        cash=cash,
        post_issue_shares=post_issue
    )
    
    return {
        "inputs": {
            "historical": {
                "base_revenue": base_revenue,
                "debt": debt,
                "cash": cash,
                "post_issue_shares": post_issue,
                "financial_period": {
                    "fiscal_year": fp.fiscal_year,
                    "period_end": str(fp.period_end)
                }
            },
            "assumptions": scenario.model_dump()
        },
        "projections": res["projections"],
        "valuation": {
            "enterprise_value": ev,
            "equity_value": equity_value,
            "intrinsic_value_per_share": intrinsic_value_per_share,
            "terminal_value": res.get("terminal_value"),
            "terminal_value_pv": res.get("terminal_value_pv"),
            "implied_upside_pct_lower_band": upside_lower,
            "implied_upside_pct_upper_band": upside_upper
        },
        "sensitivity": sensitivity
    }
