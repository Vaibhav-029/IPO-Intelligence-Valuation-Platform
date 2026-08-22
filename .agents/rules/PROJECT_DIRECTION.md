# PROJECT DIRECTION — DO NOT CHANGE THE CORE SCOPE

You are continuing development of an existing project called **IPO Intelligence & Valuation Platform**.

The existing repository is the foundation and should remain fundamentally intact.

## Core product

The goal is to build a polished, production-minded **AI-powered IPO research and valuation platform for Indian IPOs**.

The platform should help a user:

1. Discover upcoming and ongoing IPOs.
2. View structured IPO information.
3. Analyze historical financial performance.
4. Calculate deterministic financial and valuation metrics.
5. Compare the company with relevant peers.
6. Understand major risks.
7. Read and research IPO filings/documents.
8. Ask natural-language questions about an IPO.
9. Receive evidence-grounded AI answers.
10. Understand how the platform arrived at its financial and qualitative conclusions.

The platform should remain an **IPO intelligence and valuation product**, not become a separate general-purpose OSINT platform or a massive autonomous market-monitoring system.

---

## EXISTING ARCHITECTURE

Preserve the existing architecture unless a change is genuinely required:

* Next.js / React / TypeScript frontend
* FastAPI backend
* PostgreSQL
* Redis
* Celery
* deterministic financial/valuation services
* IPO scoring
* JWT authentication
* user-scoped research sessions
* watchlists
* PDF ingestion
* SHA-256 document deduplication
* PyMuPDF extraction
* citation-ready evidence chunks
* research/tool layer
* LLM provider abstraction
* Docker
* automated backend tests

Do not rewrite working functionality unnecessarily.

---

## LIVE / CURRENT IPO DATA

We do want the platform to contain **current information about upcoming and ongoing IPOs**.

However, implement this as an enhancement to the existing IPO directory/data layer rather than turning the project into a completely new real-time event-processing platform.

The platform should support categories such as:

* Upcoming IPOs
* Currently Open IPOs
* Recently Closed IPOs
* Recently Listed IPOs

Where reliable public data is available, keep information such as:

* IPO dates
* price band
* issue size
* fresh issue
* OFS
* lot size
* subscription information
* listing information
* relevant filings
* important status updates

Use a clean provider/ingestion abstraction so the source can be changed later.

Do not fabricate live data.

Clearly distinguish:

* real source data
* derived/calculated data
* illustrative/demo data
* unavailable information

---

## FINANCIAL ENGINE

Keep financial calculations deterministic.

The LLM must NOT be responsible for calculating:

* revenue growth
* CAGR
* margins
* ROE
* ROCE
* debt/equity
* enterprise value
* P/E
* P/S
* EV/EBITDA
* valuation premiums/discounts
* IPO scoring

Python/backend services should calculate these values.

The LLM may explain them and reason about their implications.

---

## IPO VALUATION

Valuation is a major component of the project.

Maintain the ability to analyze:

* issue valuation
* market capitalization
* enterprise value
* valuation multiples
* historical growth
* profitability
* peer multiples
* valuation premium/discount
* qualitative risk factors

The user should be able to understand not just the numerical valuation, but also why the platform considers the valuation attractive, neutral, or expensive.

---

## DOCUMENT INTELLIGENCE

Keep the existing filing/document workflow.

Target flow:

PDF → validation → deduplication → persistent document/job record → PyMuPDF extraction → chunks → metadata/evidence → research retrieval → LLM answer

The source page and document information should remain available for auditing.

Do not allow the LLM to invent citations.

---

## AI RESEARCH LAYER

The AI component should function as a research assistant for IPO analysis.

It should be able to use structured tools such as:

* company profile
* financials
* valuation metrics
* peer comparison
* risk factors
* IPO score
* filing/document evidence

The LLM should combine these sources to answer questions such as:

* Why does this IPO trade at a premium to peers?
* What are the major risks?
* How has profitability changed?
* How does valuation compare with competitors?
* What does the latest filing say about the company?
* What are the key things an investor should investigate further?

Keep the system evidence-first.

---

## RAG / RETRIEVAL

Improve the existing retrieval system only where useful.

Do not replace the entire research architecture simply for the sake of introducing a new technology.

If semantic/vector retrieval is added, it should complement the existing evidence system rather than unnecessarily rewriting it.

The important objective is:

> retrieve the correct evidence and make the AI answer traceable to it.

---

## USER EXPERIENCE

The dashboard should make the five-minute IPO research workflow very strong.

The user should be able to:

1. Find an IPO.
2. Understand the business.
3. Inspect financials.
4. Inspect valuation.
5. See risks.
6. Compare peers.
7. Review filings.
8. Ask the AI research assistant questions.
9. See the evidence supporting the answer.
10. Decide what deserves deeper investigation.

The interface should feel like a serious financial research tool rather than a generic chatbot.

---

## SCALABILITY

Think about scale, but do not over-engineer.

Preserve the existing Redis/Celery architecture for background document processing.

Use asynchronous processing where it provides a clear benefit.

Think about:

* API responsiveness
* document-processing workloads
* database indexing
* caching
* duplicate prevention
* LLM cost
* request concurrency

However, do NOT introduce unnecessary microservices, complex event buses, distributed state machines, WebSockets, or elaborate streaming infrastructure unless a concrete product requirement requires them.

---

## DATA QUALITY

Data correctness is more important than adding features.

Financial values should remain auditable.

Normalize Indian financial units correctly.

Do not silently invent missing values.

Where source data conflicts, retain provenance and make the conflict explicit.

The system should prefer:

> "data unavailable / source not verified"

over fabricated certainty.

---

## ENGINEERING QUALITY

Continue improving:

* tests
* error handling
* authentication
* validation
* logging
* database integrity
* background-job reliability
* documentation
* Docker setup

But keep improvements proportional to the actual product.

---

## IMPORTANT SCOPE RULE

Do NOT turn this project into:

* a generic AI agent framework
* a full OSINT investigation platform
* a Bloomberg replacement
* a high-frequency market-monitoring system
* a giant distributed microservice architecture
* an autonomous financial advisor
* a brokerage/trading platform

The project remains:

> **An AI-powered IPO Intelligence & Valuation Platform with current IPO information, deterministic financial analysis, evidence-grounded document research, and an LLM-powered research assistant.**

Every future feature should strengthen that product.

---

## WORKING METHOD

Before making substantial changes:

1. Inspect the existing implementation.
2. Identify what already works.
3. Avoid rewriting working modules.
4. Make the smallest change necessary.
5. Reuse existing architecture.
6. Run tests after changes.
7. Verify the actual application behavior.
8. Update documentation.

When there are multiple possible implementations, prefer the simplest one that preserves the architecture and improves the product.

The objective is not to maximize the number of technologies.

The objective is to make the existing **IPO Intelligence & Valuation Platform** exceptionally polished, technically defensible, useful, and impressive.
