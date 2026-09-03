from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    refresh_token_version: Mapped[int] = mapped_column(Integer, default=0)


class Company(Timestamped, Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(100), index=True)
    exchange: Mapped[str] = mapped_column(String(30), default="NSE/BSE")
    description: Mapped[str] = mapped_column(Text, default="")
    ipos: Mapped[list["IPO"]] = relationship(back_populates="company")


class IPO(Timestamped, Base):
    __tablename__ = "ipos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Upcoming", index=True)
    issue_size: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    price_low: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_high: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    issue_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    open_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    close_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    listing_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    fresh_issue: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    ofs: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    lot_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_investment: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    face_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    shares_offered: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    pre_issue_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    post_issue_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fresh_issue_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ofs_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    company: Mapped[Company] = relationship(back_populates="ipos")


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"
    __table_args__ = (UniqueConstraint("company_id", "period_end", name="uq_company_period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    period_end: Mapped[datetime] = mapped_column(Date)
    
    # Authoritative period classification: "Annual" or "Interim"
    period_type: Mapped[str] = mapped_column(String(20), default="Annual")
    # Specific interim designation if applicable (e.g., "Q1", "H1", "Q3", "9M")
    interim_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    fiscal_year: Mapped[str] = mapped_column(String(20))
    metrics: Mapped["FinancialMetric"] = relationship(back_populates="period", uselist=False, cascade="all, delete-orphan")


class FinancialMetric(Base):
    """Raw financial facts.
    
    Unit contract:
    - All financial statement amounts (revenue, EBITDA, EBIT, PAT, total_debt, cash, equity, assets) are in INR Crore.
    - EPS is in absolute INR per share.
    - NULL indicates the value is unavailable or not reported.
    - 0.0 indicates an explicitly reported zero.
    """
    __tablename__ = "financial_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), unique=True)
    
    # Financial fields
    revenue: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    ebitda: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    ebit: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    pat: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    eps: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    total_debt: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    cash: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    equity: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    assets: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    
    # Provenance fields
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    derived_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    
    period: Mapped[FinancialPeriod] = relationship(back_populates="metrics")


class Peer(Base):
    __tablename__ = "peers"
    __table_args__ = (UniqueConstraint("company_id", "peer_company_id", name="uq_peer_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    peer_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    rationale: Mapped[str] = mapped_column(Text, default="Comparable sector and business model")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ValuationMetric(Base):
    """Phase 2B Note:
    These fields represent derived valuation multiples (pe, ps, ev_ebitda, ev_sales).
    In Phase 2B, the platform will migrate to calculating these dynamically from raw 
    financial facts and market cap. They remain structurally compatible here for now.
    """
    __tablename__ = "valuation_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    context: Mapped[str] = mapped_column(String(30), default="CURRENT_MARKET", server_default="CURRENT_MARKET")
    date: Mapped[datetime] = mapped_column(Date)
    market_cap: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    ev: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_sales: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class RiskFactor(Timestamped, Base):
    __tablename__ = "risk_factors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"), index=True)
    category: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="Medium")
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class IPOSCore(Timestamped, Base):
    __tablename__ = "ipo_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"), unique=True)
    financial_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    growth_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valuation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    balance_sheet_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    business_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(40), default="v4.0")
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    explanations: Mapped[dict] = mapped_column(JSON, default=dict)


class Document(Timestamped, Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    ipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ipos.id"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    type: Mapped[str] = mapped_column(String(50), default="RHP")
    filename: Mapped[str] = mapped_column(String(255), default="document.pdf")
    storage_url: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="queued")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(100), unique=True)
    text: Mapped[str] = mapped_column(Text)
    source_text_hash: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_empty: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Timestamped, Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Watchlist(Timestamped, Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "ipo_id", name="uq_user_watchlist"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"))


class ResearchSession(Timestamped, Base):
    __tablename__ = "research_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"))
    title: Mapped[str] = mapped_column(String(255), default="IPO research")


class ResearchMessage(Base):
    __tablename__ = "research_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("research_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    tool_trace: Mapped[list] = mapped_column(JSON, default=list)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
