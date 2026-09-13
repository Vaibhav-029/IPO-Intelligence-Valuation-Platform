# IPO Intelligence & Valuation Platform

> Research-driven IPO analysis for the Indian primary market.

<p align="center">
  <strong>Financials · Valuation · Peers · Risks · Filings · AI Research</strong>
</p>

---

## About

IPO Intelligence & Valuation Platform is a full-stack research workspace built to bring the main parts of IPO analysis into one place.

It combines structured IPO data, financial analysis, valuation models, peer comparison, filing intelligence, risk analysis, deterministic scoring, and an AI-powered research workflow.

The focus is simple:

**turn fragmented IPO information into a structured research process.**

---

## What it does

### IPO Intelligence
- Upcoming, Ongoing, Closed and Listed IPOs
- Mainboard and SME segmentation
- Issue dates, listing dates, price bands, issue size and lot size
- Lifecycle-aware status handling

### Financial Analysis
- Revenue, EBITDA, PAT and EPS
- Historical and interim periods
- Growth and margin analysis
- Provenance-aware financial data

### Valuation
- P/E, P/S, EV and EV/EBITDA
- Issue-price valuation
- Peer-relative valuation
- DCF analysis

### Peer Comparison
- Comparable-company mapping
- Valuation benchmarking
- Financial comparison
- Peer-based research context

### Risk Intelligence
- Filing-based risk extraction
- Categorized risk factors
- Severity and source-page information

### Filing Intelligence
- DRHP / RHP / Prospectus processing
- Page-bounded document extraction
- Searchable evidence
- Source-level provenance

### AI Research
A research workspace backed by structured tools:

```text
IPO Profile
Financials
Valuation
Peers
Risks
Filing Search
```

The AI layer is designed to synthesize retrieved evidence rather than replace the underlying analytical system.

---

## Scoring

The platform uses a deterministic v4.0 scoring framework:

| Factor | Weight |
|---|---:|
| Financial Quality | 20% |
| Growth | 20% |
| Valuation | 20% |
| Balance Sheet | 15% |
| Business Quality | 15% |
| Risk | 10% |

Scores are NULL-aware: unavailable inputs remain unavailable instead of being fabricated.

---

## Architecture

```text
Next.js / React
      │
      ▼
    FastAPI
      │
 ┌────┴─────┐
 ▼          ▼
PostgreSQL Redis
      │
      ▼
    Celery
      │
      ├── IPO data
      ├── Filings
      ├── Financial extraction
      └── Background jobs

Research Layer
      │
      ├── Structured financial data
      ├── Filing evidence
      └── Groq + Qwen
```

---

## Tech Stack

**Frontend**
- Next.js
- React
- TypeScript
- Tailwind CSS

**Backend**
- FastAPI
- Python
- SQLAlchemy
- Pydantic
- Alembic

**Data & Infrastructure**
- PostgreSQL
- SQLite
- Redis
- Celery

**Document Intelligence**
- PyMuPDF
- RAG / evidence retrieval

**AI**
- Groq
- Qwen

---

## Engineering Principles

- **Evidence over confidence**
- **Missing data over fabricated data**
- **Deterministic analytics over LLM arithmetic**
- **Structured data before unstructured reasoning**
- **One analytical source of truth across the product**

---

## Current Scale

Current local analytical dataset:

| Domain | Records |
|---|---:|
| Companies | 61 |
| IPOs | 61 |
| Financial Periods | 154 |
| Financial Metrics | 154 |
| Risk Factors | 233 |
| Documents | 27 |
| RAG Source Chunks | 26,968 |
| Peer Records | 34 |
| IPO Scores | 54 |
| Valuation Records | 21 |

---

## Project Structure

```text
backend/
  app/
  alembic/
  tests/

frontend/
  app/
  components/
  lib/

Dockerfile
docker-compose.yml
README.md
```

---

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
uvicorn app.main:app --reload
```

### Frontend

```bash
npm install
npm run dev
```

---

## Testing

The backend test suite currently passes:

```text
218 passed
```

Tests use an isolated test database so destructive test setup cannot target the primary development intelligence database.

---

## Deployment

The project is being prepared for a free-tier production deployment using:

- Vercel — Next.js frontend
- Render — FastAPI / background services
- Supabase — PostgreSQL

Production deployment will also require durable storage for filing documents.

---

## Roadmap

- [x] IPO lifecycle intelligence
- [x] Financial analytics
- [x] Valuation and DCF
- [x] Peer comparison
- [x] Risk intelligence
- [x] Filing intelligence
- [x] RAG research
- [x] AI Research workspace
- [x] IPO scoring
- [x] Global search
- [x] Watchlists
- [x] Test-database isolation
- [ ] Production deployment
- [ ] Production QA
- [ ] Further research and valuation refinements

---

## Disclaimer

This project is intended for educational, analytical, and software-engineering purposes.

It is not investment advice, financial advice, brokerage software, or a recommendation to buy or sell securities.

Always verify important information against official issuer, exchange, and regulatory sources.

---

## Author

**Vaibhav Srivastava**

[GitHub](https://github.com/Vaibhav-029)
[LinkedIn](https://www.linkedin.com/in/vaibhav-srivastava-851927285/)
---

<p align="center">
  <strong>IPO Intelligence & Valuation Platform</strong><br>
  <sub>Research the IPO. Understand the numbers.</sub>
</p>
