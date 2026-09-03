# IPO Intelligence

An India-focused IPO research terminal built to demonstrate full-stack SDE and AI-engineering capability. It keeps financial computation deterministic and uses document retrieval only as evidence for research answers.

## What works today

- Curated Indian IPO directory with company profiles, financial history, valuation multiples, risks, and versioned scorecards.
- FastAPI JWT registration/login/refresh/logout plus user-scoped research sessions and watchlists.
- Deterministic financial and scoring engines, including India-specific lakh/crore normalization.
- PDF upload with SHA-256 deduplication, durable job records, PyMuPDF page extraction, and citation-ready source chunks.
- Evidence-first research API with structured tool traces and a safe local fallback. The provider configuration is intentionally isolated for a Groq-compatible adapter.
- Next.js dashboard that makes the core five-minute demo available at `/` and `/ipos/:id`.
- Production-hardened with Redis rate limiting, global exception handling, secure cookies, and safe database migration startup flow.

## Run locally

1. Optionally copy `.env.example` to `.env` and replace `JWT_SECRET`; this is required before deployment, while Compose has safe local defaults.
2. Start the full stack: `docker compose up --build`.
3. Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

For backend-only development, create a Python environment, install `backend/requirements.txt`, then run `uvicorn app.main:app --reload` from `backend/`. SQLite is the default; Docker uses PostgreSQL and Redis.

## Demo flow

1. Browse the IPO directory and open AsterNova Technologies.
2. Inspect deterministic historical financials, valuation metrics, risk factors, and transparent scorecard.
3. Register with `POST /api/v1/auth/register` in Swagger, then use the returned access token for research-session calls.
4. Ask the research endpoint why the IPO trades at a premium; inspect its tool trace and linked filing excerpts.
5. Upload a real public SEBI filing to test checksum deduplication and page-level evidence extraction.

## Architecture

```text
Next.js dashboard ──> FastAPI /api/v1 ──> PostgreSQL
                         │        ├── Redis / Celery worker (production jobs)
                         │        ├── deterministic analytics + scoring
                         │        └── document evidence / provider-agnostic research layer
                         └── uploaded filing storage
```

## Engineering boundaries

- All values are INR crore in the normalized financial store; source text and pages remain auditable.
- The LLM layer is not authorized to calculate financial ratios or make unsupported claims.
- `app/agent/providers.py` defines the provider protocol and Groq-compatible adapter; the agent remains in deterministic mode until `GROQ_API_KEY` is configured server-side.
- This is research support only, never personalized investment advice or brokerage execution.
- Seed values are illustrative portfolio data; validate every value against an allowed public source before presenting it as real-market data.

## Verification

Run backend tests from `backend/` with `pytest`. The test suite covers financial formulas, valuation math, Indian-number normalization, and weighted score behavior.
