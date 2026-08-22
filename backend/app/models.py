from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
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
    listing_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    fresh_issue: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    ofs: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    company: Mapped[Company] = relationship(back_populates="ipos")


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"
    __table_args__ = (UniqueConstraint("company_id", "period_end", name="uq_company_period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    period_end: Mapped[datetime] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(20), default="FY")
    fiscal_year: Mapped[str] = mapped_column(String(20))
    metrics: Mapped["FinancialMetric"] = relationship(back_populates="period", uselist=False, cascade="all, delete-orphan")


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), unique=True)
    revenue: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    ebitda: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    ebit: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    pat: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    eps: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_debt: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    cash: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    equity: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    assets: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
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
    __tablename__ = "valuation_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    date: Mapped[datetime] = mapped_column(Date)
    market_cap: Mapped[float] = mapped_column(Numeric(16, 2))
    ev: Mapped[float] = mapped_column(Numeric(16, 2))
    pe: Mapped[float] = mapped_column(Float, nullable=True)
    ps: Mapped[float] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float] = mapped_column(Float, nullable=True)
    ev_sales: Mapped[float] = mapped_column(Float, nullable=True)


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
    business_score: Mapped[float] = mapped_column(Float)
    growth_score: Mapped[float] = mapped_column(Float)
    profitability_score: Mapped[float] = mapped_column(Float)
    valuation_score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    overall_score: Mapped[float] = mapped_column(Float)
    methodology_version: Mapped[str] = mapped_column(String(40), default="v1.0")
    notes: Mapped[dict] = mapped_column(JSON, default=dict)


class Document(Timestamped, Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    ipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ipos.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), default="RHP")
    storage_url: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="queued")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(255), default="Document page")
    chunk_id: Mapped[str] = mapped_column(String(100), unique=True)
    text: Mapped[str] = mapped_column(Text)
    source_text_hash: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


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
