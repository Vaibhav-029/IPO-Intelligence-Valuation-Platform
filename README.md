# IPO Intelligence & Valuation Platform

> **An institutional-style IPO research and valuation platform for the Indian primary market — combining IPO intelligence, financial analytics, valuation, peer comparison, filing intelligence, risk analysis, deterministic scoring, DCF analysis, and an AI-powered research workspace into one analytical system.**

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-0f172a?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Frontend-Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Language-TypeScript%20%7C%20Python-3178C6?style=for-the-badge" alt="Languages">
  <img src="https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="Database">
  <img src="https://img.shields.io/badge/AI-Groq%20%2B%20Qwen-7c3aed?style=for-the-badge" alt="AI">
</p>

<p align="center">
  <strong>Research the IPO. Understand the numbers. Challenge the valuation.</strong>
</p>

---

## Overview

IPO Intelligence & Valuation Platform is a full-stack financial research system designed to make IPO analysis more structured, evidence-driven, and repeatable.

Traditional IPO research is fragmented across:

- IPO websites
- exchange information
- company filings
- DRHPs / RHPs / Prospectuses
- financial statements
- peer-company data
- valuation spreadsheets
- risk disclosures
- multiple browser tabs
- and increasingly, general-purpose AI assistants

This project brings those workflows together into a single research environment.

Instead of treating an IPO as a page containing a few fields, the platform models it as a structured analytical object:

```text
IPO
├── Company
├── Lifecycle
├── Financials
├── Valuation
├── Peers
├── Risks
├── Filings
├── Evidence
├── DCF
├── Score
└── AI Research Context
```

The goal is not to replace professional terminals or brokerage platforms.

The goal is to build a focused **IPO intelligence and research workstation** where structured financial data, filing evidence, deterministic analytics, and AI-assisted research work together.

---

# Key Features

## 1. IPO Intelligence

The platform maintains a structured IPO universe with lifecycle-aware status handling.

Supported lifecycle states:

```text
Upcoming
Ongoing
Closed
Listed
```

Lifecycle is derived from issue and listing dates rather than blindly trusting a stale status field:

```text
today < open_date
        ↓
Upcoming

open_date ≤ today ≤ close_date
        ↓
Ongoing

close_date < today < listing_date
        ↓
Closed

today ≥ listing_date
        ↓
Listed
```

### IPO information includes

- Company
- IPO name
- Mainboard / SME segment
- Open date
- Close date
- Listing date
- Price band
- Issue size
- Lot size
- Face value
- Fresh issue
- Offer for Sale (OFS)
- Shares offered
- Source metadata

---

# 2. Financial Intelligence

Financial information is stored as structured data rather than relying on generated text.

The platform supports:

- Revenue
- EBITDA
- PAT
- EPS
- Margins
- Growth metrics
- CAGR
- Annual financial periods
- Interim periods
- Q1 / H1 / 9M reporting
- Financial provenance

A central design principle is:

> **Missing data stays missing.**

The platform avoids silently converting unavailable values into zero or inventing estimates.

```text
Available
   ↓
Calculate

Unavailable
   ↓
NULL / N/A

Never
   ↓
Fabricate
```

This matters especially for IPOs where filing coverage is incomplete.

---

# 3. Valuation Intelligence

The valuation layer separates valuation inputs from interpretation.

Supported analytical concepts include:

- IPO issue-price valuation
- P/E
- P/S
- EV
- EV/EBITDA
- Market capitalization
- Peer-relative valuation
- DCF inputs
- Implied valuation metrics

Valuation records preserve context so that different valuation situations are not accidentally treated as the same thing.

For example:

```text
IPO issue valuation
        ≠
Live market valuation
        ≠
Peer-company valuation
```

This contextual approach makes downstream research and scoring more reliable.

---

# 4. Peer Comparison

Comparable companies are represented explicitly in the data model.

Peer relationships can include:

- Target company
- Comparable company
- Peer rationale
- Active / inactive state
- Valuation metrics
- Financial metrics

Peer analysis supports:

- P/E comparison
- Valuation benchmarking
- Financial comparison
- Growth comparison
- Research synthesis

Missing peer metrics are preserved rather than manufactured.

For example:

```text
Peer exists
    ↓
P/E available?
   / \
 YES  NO
  |    |
Compare N/A
```

This prevents misleading peer comparisons when a multiple is not meaningful or unavailable.

---

# 5. Risk Intelligence

The platform extracts structured risk disclosures from company filings.

Risk records contain:

- Category
- Severity
- Summary
- Filing source
- Source page
- IPO / company association

Examples include:

- Market risks
- Regulatory risks
- Business risks
- Financial risks
- Operational risks
- Competitive risks

This converts filing disclosures from passive PDF text into structured analytical information.

---

# 6. Filing Intelligence

A major part of the platform is its filing-processing pipeline.

The system is designed to process:

- DRHP
- RHP
- Prospectus
- Related filing material

The pipeline follows:

```text
Filing Discovery
      ↓
Issuer Validation
      ↓
Download
      ↓
Deduplication
      ↓
PDF Processing
      ↓
Financial Extraction
      ↓
Risk Extraction
      ↓
Valuation / Peer Analysis
      ↓
Scoring
      ↓
Research Availability
```

The platform preserves document provenance and source context throughout the process.

---

# 7. Retrieval-Augmented Research

Filing documents are not simply dumped into an LLM.

Instead, the platform uses a structured evidence workflow:

```text
PDF
 ↓
Page-bounded extraction
 ↓
Chunking
 ↓
Source records
 ↓
Retrieval
 ↓
Research context
 ↓
LLM synthesis
```

Evidence records can preserve:

- Document
- Page
- Section
- Source text
- Chunk identity
- Confidence
- Provenance

This allows AI-generated research to stay grounded in actual company information and filing material.

---

# 8. AI Research Workspace

The Research workspace is designed as an analyst-oriented environment rather than a generic chatbot.

The research layer has specialized tools including:

```text
get_ipo_profile
get_financials
get_valuation
get_peers
get_risks
search_filing
```

A typical research workflow is:

```text
User Question
      ↓
Research Agent
      ↓
Relevant Tool Selection
      ↓
IPO Profile
Financials
Valuation
Peers
Risks
Filing Evidence
      ↓
Evidence Synthesis
      ↓
Research Answer
```

The interface exposes tool traces so users can understand what analytical information contributed to the response.

---

# 9. Evidence-First AI

The system is designed around the principle:

> **Evidence first, synthesis second.**

The intended research flow is:

```text
Claim
 ↓
Structured Data / Filing Evidence
 ↓
Tool Retrieval
 ↓
LLM Synthesis
 ↓
Citation / Trace
```

Not:

```text
Question
 ↓
LLM Guess
 ↓
Confident Financial Narrative
```

The research layer is also designed to handle incomplete datasets gracefully.

Unavailable values remain unavailable rather than being invented to make an answer look complete.

---

# 10. Deterministic IPO Scoring

The platform includes a deterministic multi-factor IPO scoring framework.

### v4.0 methodology

| Factor | Weight |
|---|---:|
| Financial Quality | 20% |
| Growth | 20% |
| Valuation | 20% |
| Balance Sheet | 15% |
| Business Quality | 15% |
| Risk | 10% |
| **Total** | **100%** |

The backend maintains a 0–100 score while the interface presents the result on a 0–10 scale.

## NULL-aware scoring

A missing analytical factor does not automatically become a fabricated or arbitrary value.

If a factor cannot be evaluated reliably:

```text
Factor = NULL
```

The scoring engine can redistribute the available weight across valid factors.

This makes the system more robust when companies have uneven disclosure coverage.

---

# 11. Valuation Score Philosophy

The v4.0 valuation score is intentionally conservative.

It primarily relies on peer-relative P/E analysis.

The methodology requires:

1. IPO lower-band P/E
2. Active peer
3. Valid peer P/E
4. Peer median P/E
5. Relative premium / discount

When those requirements cannot be satisfied reliably:

```text
Valuation Score = NULL
```

rather than manufacturing a peer comparison.

Therefore an IPO can still have:

- Issue valuation metrics
- P/S
- EV/EBITDA
- Market-cap estimates

while its valuation score remains unavailable when a reliable peer P/E comparison cannot be established.

This behavior is intentional.

---

# 12. DCF Analysis

The platform includes a deterministic DCF-oriented analytical layer.

The broader workflow is:

```text
Historical Financials
       ↓
Growth Assumptions
       ↓
Cash Flow Inputs
       ↓
Discount Rate
       ↓
Terminal Assumptions
       ↓
DCF
       ↓
Implied Valuation
```

The philosophy is to keep core financial calculations deterministic and inspectable.

LLMs are used for interpretation and synthesis, not as the primary calculator for financial models.

---

# 13. Global IPO Search

The platform provides PostgreSQL-backed global search.

Search can identify:

- Company name
- IPO name
- Symbol
- Slug
- Sector
- Exchange
- Listing segment
- Lifecycle
- Document metadata

Search ranking favors stronger matches before broader text matches.

### Keyboard support

- `Ctrl/Cmd + K`
- Arrow-key navigation
- Enter to select
- Escape to close

---

# 14. Watchlist

Users can maintain persistent IPO watchlists.

Features include:

- User-scoped watchlists
- Persistent add/remove behavior
- Real company logos when available
- Initials fallback
- CSV export

Watchlists operate on the same underlying IPO intelligence used across the platform.

---

# Product Architecture

```text
                         ┌─────────────────────────┐
                         │      NEXT.JS / REACT    │
                         │                         │
                         │ Market                  │
                         │ Search                  │
                         │ Watchlist               │
                         │ IPO Detail              │
                         │ Research                │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │        FASTAPI          │
                         │                         │
                         │ IPO APIs                │
                         │ Financials              │
                         │ Valuation               │
                         │ Peers                   │
                         │ Risks                   │
                         │ Research                │
                         └────────────┬────────────┘
                                      │
                  ┌───────────────────┴───────────────────┐
                  │                                       │
                  ▼                                       ▼
        ┌─────────────────────┐                 ┌─────────────────────┐
        │     PostgreSQL      │                 │        Redis        │
        │                     │                 │                     │
        │ IPOs                │                 │ Task broker         │
        │ Companies           │                 │ Rate limiting       │
        │ Financials          │                 │ Background jobs     │
        │ Valuation           │                 │                     │
        │ Peers               │                 └──────────┬──────────┘
        │ Risks               │                            │
        │ Filings             │                            ▼
        │ Sources             │                 ┌─────────────────────┐
        │ Research            │                 │   Celery Workers    │
        │ Watchlists          │                 │                     │
        └─────────────────────┘                 │ Sync / Jobs         │
                                                └─────────────────────┘

                    External Intelligence Layer
                               │
               ┌───────────────┼────────────────┐
               ▼               ▼                ▼
          IPO Data         Regulatory        Groq / Qwen
           Sources          Filings           Research
```

---

# Technology Stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Responsive institutional-style UI

## Backend

- FastAPI
- Python
- SQLAlchemy 2.x
- Pydantic
- Alembic

## Data & Infrastructure

- PostgreSQL
- SQLite for local development
- Redis
- Celery

## Document Intelligence

- PyMuPDF
- Page-bounded extraction
- Structured source records
- Retrieval-based evidence search

## AI

- Groq
- Qwen
- Tool-based research
- RAG
- Evidence tracing

---

# Data Model

The core data model contains relational entities for:

```text
Users
Companies
IPOs
Financial Periods
Financial Metrics
Peers
Valuation Metrics
Risk Factors
IPO Scores
Documents
Sources
Jobs
Watchlists
Research Sessions
Research Messages
```

High-level relationship structure:

```text
Company
 ├── IPO
 │    ├── Risk Factors
 │    ├── IPO Score
 │    └── Documents
 │
 ├── Financial Periods
 │      └── Financial Metrics
 │
 ├── Peers
 │      └── Peer Company
 │
 ├── Valuation Metrics
 │
 └── Documents
        └── Sources
```

Research is layered on top:

```text
Company / IPO
      ↓
Structured Analytics
      +
Filing Evidence
      ↓
Research Session
      ↓
Research Messages
      ↓
Tool Trace + Citations
```

---

# Data Integrity Principles

## 1. Do not fabricate missing data

Missing information remains:

```text
NULL
```

or is displayed as:

```text
N/A
```

## 2. Preserve provenance

Financial and filing-derived information retains source context wherever possible.

## 3. Keep calculations deterministic

Scoring and financial calculations are implemented in the analytical layer instead of delegating arithmetic to the LLM.

## 4. Separate evidence from interpretation

Structured data and source evidence are stored separately from natural-language synthesis.

## 5. Prefer authoritative filing versions

Where multiple filing versions are available, the system follows a defined precedence model:

```text
Prospectus
    >
RHP
    >
DRHP
```

Valid fields are not intentionally replaced by NULL values from later incomplete sources.

---

# Database & Migration Architecture

Development uses SQLite for local iteration.

Production is designed around PostgreSQL.

The migration strategy is:

```text
Fresh PostgreSQL Database
          ↓
Alembic Schema
          ↓
Read-only extraction from local SQLite
          ↓
Dependency-aware data transfer
          ↓
PostgreSQL sequence synchronization
          ↓
Row-count validation
          ↓
Production application
```

The application has an Alembic migration chain with the current schema head:

```text
cb6bee80aa04
      ↓
62985079b762
      ↓
d0ad286081f6
      ↓
88bdd6b2b31e
      ↓
f16da429c593
      ↓
238a758092fe
      ↓
3760eae90459
```

`3760eae90459` is the current schema head.

> **Important:** the development SQLite database should not be used as an Alembic migration target. Production schema creation happens on a fresh PostgreSQL database.

---

# Test Safety

The project includes an explicit test-database isolation mechanism.

Tests use:

```text
backend/test_suite.db
```

instead of the primary development intelligence database.

This prevents destructive test setup from affecting the development dataset.

The backend test suite has been verified at:

```text
218 passed
```

TypeScript validation was also completed successfully during the Research hardening cycle.

---

# Research Reliability

The Research layer includes explicit handling for incomplete data.

### Missing peer P/E

Instead of attempting:

```python
median([])
```

the system safely produces:

```text
peer_median_pe = NULL
```

### Missing financial metrics

Missing EBITDA / PAT / revenue values remain unavailable instead of being converted into invalid numerical placeholders.

### Partial research context

Optional research tools can fail independently without necessarily crashing the complete research request.

### Rate-limit resilience

The LLM provider layer avoids blocking a worker for extremely long upstream retry intervals and allows the existing fallback behavior to handle the situation.

---

# Project Structure

```text
IPO-Intelligence-Valuation-Platform/
│
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   ├── services/
│   │   ├── models.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── lifecycle.py
│   │   ├── workers.py
│   │   └── ...
│   │
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
│
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

# Local Development

## Prerequisites

Recommended:

- Python 3.11+
- Node.js
- npm
- Git
- Redis
- SQLite or PostgreSQL for development

---

## Clone the repository

```bash
git clone https://github.com/Vaibhav-029/IPO-Intelligence-Valuation-Platform.git

cd IPO-Intelligence-Valuation-Platform
```

---

# Backend Setup

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables locally.

Start FastAPI:

```bash
uvicorn app.main:app --reload
```

Default backend URL:

```text
http://localhost:8000
```

---

# Frontend Setup

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Default frontend URL:

```text
http://localhost:3000
```

---

# Environment Variables

## Backend

Example:

```env
ENVIRONMENT=development

DATABASE_URL=sqlite:///./ipo_intelligence.db

REDIS_URL=redis://localhost:6379/0

JWT_SECRET=your-secure-secret

JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=14

GROQ_API_KEY=your-groq-api-key

LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b

CORS_ORIGINS=http://localhost:3000

TASK_EAGER=true

UPLOAD_DIR=./data/uploads
```

## Production PostgreSQL

The SQLAlchemy connection should use the Psycopg v3 dialect:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

## Frontend

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NODE_ENV=development
```

> Never commit real `.env` files, API keys, JWT secrets, database passwords, or private credentials.

---

# Production Deployment

The intended production architecture is:

```text
                         GitHub
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
          Vercel                         Render
       Next.js Frontend              FastAPI Backend
                                            │
                                   ┌────────┴────────┐
                                   ▼                 ▼
                             PostgreSQL          Redis / KV
                              Supabase
                                                    │
                                                    ▼
                                             Celery Worker
```

The production deployment process will include:

1. Provision PostgreSQL
2. Create the production schema with Alembic
3. Migrate verified application intelligence
4. Synchronize PostgreSQL sequences
5. Validate row counts
6. Deploy FastAPI
7. Configure Redis / background workers
8. Deploy Next.js
9. Configure CORS and environment variables
10. Configure persistent filing storage
11. Perform end-to-end production validation

The repository is currently prepared for deployment, but production infrastructure should be configured separately from the local development database.

---

# Persistent Filing Storage

The filing pipeline references processed documents and extracted source material.

A production deployment must therefore use durable storage for uploaded/processed filing files.

Stateless containers should not be relied upon as permanent storage.

Possible production approaches include:

- Persistent volumes
- Object storage
- Managed file storage

The application configuration supports a dedicated upload directory through:

```env
UPLOAD_DIR=/app/data/uploads
```

---

# Current Data Footprint

The current local intelligence dataset includes approximately:

| Domain | Records |
|---|---:|
| Companies | 61 |
| IPOs | 61 |
| Financial Periods | 154 |
| Financial Metrics | 154 |
| Risk Factors | 233 |
| Documents | 27 |
| Source / RAG Chunks | 26,968 |
| Peer Records | 34 |
| IPO Scores | 54 |
| Valuation Records | 21 |

These values represent the current local analytical dataset and will evolve as the platform continues to synchronize and ingest information.

---

# What Makes This Project Different

## It is not just an IPO tracker

A typical IPO tracker answers:

> When does the IPO open?

This platform attempts to answer:

> What is this company worth, how is it performing, how does it compare with peers, what risks does the filing disclose, and what does the available evidence actually support?

---

## It is not just an AI chatbot

A generic financial chatbot might produce a plausible response from model knowledge.

This system instead attempts:

```text
Structured Data
      +
Financial Models
      +
Peer Analysis
      +
Filing Evidence
      +
Retrieval
      ↓
AI Research
```

---

## It is not just a financial dashboard

The goal is not only to display numbers.

The system connects:

```text
Data
 ↓
Analysis
 ↓
Evidence
 ↓
Reasoning
 ↓
Research
```

into one workflow.

---

# Design Philosophy

### Evidence over confidence

A confident answer without evidence is not good financial research.

### Missing data over fabricated data

A visible `N/A` is better than an invented number.

### Deterministic analytics over LLM arithmetic

The LLM interprets analytical results; it should not silently become the financial calculation engine.

### Structured data before unstructured reasoning

Whenever possible:

```text
PDF
 ↓
Extraction
 ↓
Normalization
 ↓
Database
 ↓
Analytics
 ↓
Research
```

rather than sending an entire document to an LLM and hoping for reliable output.

### One source of truth

Market, Search, Watchlist, IPO Detail, Valuation, Risk, and Research should operate on the same underlying analytical model.

---

# Roadmap

## Completed

- [x] IPO lifecycle intelligence
- [x] Mainboard / SME classification
- [x] IPO metadata
- [x] Financial modeling layer
- [x] Financial metrics and period modeling
- [x] Valuation analytics
- [x] Peer comparison
- [x] Risk extraction
- [x] Filing intelligence
- [x] RAG source processing
- [x] AI research workspace
- [x] Tool-based research architecture
- [x] Evidence / citation tracing
- [x] Deterministic IPO scoring
- [x] DCF analytics
- [x] Global IPO search
- [x] Persistent watchlists
- [x] Research failure hardening
- [x] Automated test isolation
- [x] Backend test suite
- [x] PostgreSQL migration readiness

## Next

- [ ] Production PostgreSQL deployment
- [ ] FastAPI deployment
- [ ] Redis / worker deployment
- [ ] Next.js deployment
- [ ] Persistent filing storage
- [ ] Production environment configuration
- [ ] Live application validation
- [ ] Research quality benchmarking
- [ ] Broader valuation coverage
- [ ] Advanced financial visualizations
- [ ] Performance optimization
- [ ] Additional data-quality validation

---

# Known Limitations

This project is actively evolving.

Current limitations include:

- IPO information depends on upstream data sources and synchronization.
- Not every issuer has complete financial coverage.
- Some companies do not have enough comparable-company data for a reliable peer-relative valuation score.
- Filing coverage varies between issuers.
- AI research depends partly on external LLM/provider availability.
- Free hosting infrastructure may introduce cold starts or inactivity pauses.
- Production filing persistence requires durable storage.
- Valuation scoring intentionally remains unavailable when its required peer evidence is insufficient.

These limitations are deliberately surfaced rather than hidden.

---

# Disclaimer

This project is intended for:

- Educational purposes
- Financial technology experimentation
- Research
- Analytical workflows
- Software engineering demonstration

It is **not**:

- Investment advice
- Financial advice
- A brokerage platform
- A trading system
- A recommendation to buy or sell securities
- A substitute for professional financial analysis

IPO investments involve risk.

Important financial information should always be independently verified against official exchange, regulatory, issuer, and filing sources.

---

# Author

## Vaibhav

Built as an end-to-end exploration of:

- Financial technology
- IPO analytics
- Financial modeling
- Full-stack engineering
- Data engineering
- Document intelligence
- Retrieval-Augmented Generation
- AI research agents
- Financial research workflows
- Production backend architecture

---

# Repository

**GitHub:**  
https://github.com/Vaibhav-029/IPO-Intelligence-Valuation-Platform

---

<p align="center">
  <strong>IPO Intelligence & Valuation Platform</strong>
  <br>
  <sub>Research the IPO. Understand the numbers. Challenge the valuation.</sub>
</p>
