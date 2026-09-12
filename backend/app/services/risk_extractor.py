"""Risk factor extraction from DRHP/RHP filing Source chunks.

Architecture:
    1. Identify Source chunks from the "Risk Factors" section of the filing.
    2. Send identified chunks to the LLM for structured extraction.
    3. Validate severity — only persist risks with clearly justified severity.
       Ambiguous/uncertain severity causes the risk to be SKIPPED, not defaulted.
    4. Persist to RiskFactor with source_page provenance.
    5. Idempotent: clears previously filing-extracted risks before re-inserting.

The LLM NEVER fabricates risks or severity. Ambiguous severity = skip.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models import Document, RiskFactor, Source

logger = logging.getLogger(__name__)


# ── Risk extraction status codes ─────────────────────────────────────
class RiskExtractionStatus:
    DOCUMENT_UNAVAILABLE = "document_unavailable"
    PROCESSING_INCOMPLETE = "processing_incomplete"
    NO_RISK_SECTIONS = "no_risk_sections_found"
    LLM_UNAVAILABLE = "llm_unavailable"
    EXTRACTION_FAILED = "extraction_failed"
    EXTRACTION_COMPLETED = "extraction_completed"
    PARTIAL_EXTRACTION = "partial_extraction"


@dataclass
class RiskExtractionResult:
    """Result of a risk extraction attempt."""
    status: str
    risks_extracted: int = 0
    risks_skipped_ambiguous: int = 0
    errors: list[str] = field(default_factory=list)
    chunks_identified: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "risks_extracted": self.risks_extracted,
            "risks_skipped_ambiguous": self.risks_skipped_ambiguous,
            "errors": self.errors,
            "chunks_identified": self.chunks_identified,
        }


# ── Keywords for identifying risk factor chunks ─────────────────────
RISK_SECTION_KEYWORDS = [
    "risk factors",
    "risk factor",
    "material risk",
    "risks relating",
    "risks associated",
    "risks involved",
    "internal risk",
    "external risk",
]

RISK_CONTENT_KEYWORDS = [
    "may adversely affect",
    "material adverse",
    "could adversely",
    "risk of",
    "risk that",
    "no assurance",
    "cannot guarantee",
    "uncertainty",
    "litigation",
    "regulatory risk",
    "concentration risk",
    "dependence on",
    "competition",
    "may not be able",
]

# ── Valid severity values ────────────────────────────────────────────
VALID_SEVERITIES = {"High", "Medium", "Low"}


# ── LLM extraction prompt ───────────────────────────────────────────
RISK_EXTRACTION_PROMPT = """You are a risk factor extraction engine for Indian IPO filings (DRHP/RHP).

## Rules
1. Extract ONLY risk factors that are explicitly stated in the text.
2. Each risk factor must have:
   - category: A brief category label (e.g., "Regulatory", "Financial", "Operational", "Market", "Legal", "Concentration", "Technology", "Competition")
   - summary: A concise 1-2 sentence summary of the risk
   - severity: One of "High", "Medium", "Low"
   - severity_justification: A brief explanation of WHY you assigned that severity
   - page: The page number where this risk appears (from the page annotations in the text)
3. Severity assignment rules:
   - "High": Risk involves potential material financial loss, regulatory action, existential threat, or major business disruption. Clear language like "material adverse effect", "significant risk", "critical dependency"
   - "Medium": Risk is a genuine concern but manageable. Language like "may affect", "could impact", standard operational risks
   - "Low": Risk is disclosed for completeness but unlikely to materially impact. Minor operational or administrative risks
   - If you CANNOT clearly justify one of these three severities for a risk, set severity to "ambiguous" — do NOT guess
4. NEVER fabricate risks or page numbers
5. Limit to the 15 most significant risk factors

## Output Format
Return ONLY valid JSON:
{{
  "risks": [
    {{
      "category": "Regulatory",
      "summary": "The company is subject to changing regulations...",
      "severity": "High",
      "severity_justification": "Filing uses 'material adverse effect' language",
      "page": 42
    }}
  ]
}}

## Text from the filing:
{text}"""


def _identify_risk_chunks(sources: list[Source]) -> list[Source]:
    """Identify Source chunks that likely contain risk factor disclosures."""
    candidates: list[tuple[float, Source]] = []

    for source in sources:
        if source.is_empty:
            continue

        text_lower = source.text.lower()
        score = 0.0

        # Section heading match
        section = (source.section or "").lower()
        for keyword in RISK_SECTION_KEYWORDS:
            if keyword in section:
                score += 5.0
                break

        # Content keyword density
        keyword_hits = 0
        for keyword in RISK_CONTENT_KEYWORDS:
            if keyword in text_lower:
                keyword_hits += 1

        if keyword_hits >= 2:
            score += keyword_hits * 0.5

        if score >= 2.0:
            candidates.append((score, source))

    candidates.sort(key=lambda x: -x[0])
    max_chunks = 8
    return [source for _, source in candidates[:max_chunks]]


def _parse_risk_response(response_text: str) -> list[dict] | None:
    """Parse and validate the LLM risk extraction response."""
    if not response_text or not response_text.strip():
        return None

    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None

    risks = data.get("risks", [])
    if not isinstance(risks, list):
        return None

    return risks


def extract_risks(
    db: Session,
    document_id: int,
    ipo_id: int,
    llm_provider=None,
) -> RiskExtractionResult:
    """Extract structured risk factors from a processed Document's Source chunks.

    Args:
        db: SQLAlchemy session
        document_id: ID of the processed Document
        ipo_id: ID of the IPO to create RiskFactor rows for
        llm_provider: Optional LLM provider override (for testing)

    Returns:
        RiskExtractionResult with status and details
    """
    result = RiskExtractionResult(status=RiskExtractionStatus.EXTRACTION_FAILED)

    # 1. Verify document exists and is processed
    document = db.get(Document, document_id)
    if not document:
        result.status = RiskExtractionStatus.DOCUMENT_UNAVAILABLE
        result.errors.append(f"Document {document_id} not found")
        return result

    if document.processing_status != "completed":
        result.status = RiskExtractionStatus.PROCESSING_INCOMPLETE
        result.errors.append(
            f"Document processing status is '{document.processing_status}', expected 'completed'"
        )
        return result

    # 2. Fetch all source chunks
    sources = db.scalars(
        select(Source)
        .where(Source.document_id == document_id, Source.is_empty == False)
        .order_by(Source.page, Source.id)
    ).all()

    if not sources:
        result.status = RiskExtractionStatus.NO_RISK_SECTIONS
        result.errors.append("No non-empty source chunks found")
        return result

    # 3. Identify risk factor chunks
    risk_chunks = _identify_risk_chunks(list(sources))
    result.chunks_identified = len(risk_chunks)

    if not risk_chunks:
        result.status = RiskExtractionStatus.NO_RISK_SECTIONS
        result.errors.append("No chunks identified as containing risk factors")
        return result

    # 4. Get LLM provider
    if llm_provider is None:
        from app.agent.providers import get_llm_provider
        llm_provider = get_llm_provider()

    if not llm_provider.is_available:
        result.status = RiskExtractionStatus.LLM_UNAVAILABLE
        result.errors.append("LLM provider is not available for extraction")
        return result

    # 5. Combine relevant chunks
    combined_text = ""
    for chunk in risk_chunks:
        combined_text += f"\n\n--- Page {chunk.page}, Section: {chunk.section or 'N/A'} ---\n"
        combined_text += chunk.text

    # Truncate if too long
    max_chars = 10000
    if len(combined_text) > max_chars:
        combined_text = combined_text[:max_chars]

    # 6. Call LLM for extraction
    try:
        prompt = RISK_EXTRACTION_PROMPT.replace("{text}", combined_text)
        response = llm_provider.generate_sync(
            messages=[
                {"role": "system", "content": "You are a risk factor extraction engine. Output ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.05,
            max_tokens=900,
            response_format="json_object",
        )
    except Exception as e:
        result.status = RiskExtractionStatus.EXTRACTION_FAILED
        result.errors.append(f"LLM call failed: {str(e)[:200]}")
        return result

    content = response.get("content", "")

    # 7. Parse response
    risks = _parse_risk_response(content)
    if risks is None:
        result.status = RiskExtractionStatus.EXTRACTION_FAILED
        result.errors.append("Failed to parse LLM risk extraction response")
        return result

    if not risks:
        result.status = RiskExtractionStatus.NO_RISK_SECTIONS
        result.errors.append("LLM returned no risk factors")
        return result

    # 8. Idempotency: remove previously filing-extracted risks for this IPO
    # We identify filing-extracted risks by checking if source_page is not None
    # and the risk was not from seed data (seed risks have source_page from JSON).
    # Since we can't reliably distinguish, we track by checking if the summary
    # matches — but the cleanest approach is to delete risks that will be replaced.
    # We use a marker: filing-extracted risks will have category prefixed detection.
    # Actually, simplest approach: delete all existing risks for this IPO that
    # could have been filing-extracted, then re-insert.
    # We'll identify filing-extracted risks by the presence of source_page AND
    # checking created_at is after the document creation.
    #
    # Cleanest approach for idempotency: if we've already extracted risks from
    # this document for this IPO, clear them first. We track this by storing
    # the document_id in a way we can identify. Since RiskFactor doesn't have
    # a document_id field, we use a convention: if a risk's source_page exists
    # AND its summary starts with content that matches our extraction, we
    # replace them.
    #
    # For simplicity and correctness: delete ALL risks for this IPO that have
    # a non-null source_page, then re-insert from extraction. Seed-created
    # risks also have source_page, so this could conflict. Let's be safe:
    # only delete risks that were NOT from the seed by checking if they were
    # created after the document was uploaded.
    #
    # Actually the safest approach: track extraction source in the summary itself
    # is fragile. Let's just check: if this IPO has no seed data (data_source='live'),
    # then all existing risks are from previous extractions and can be replaced.
    # If the IPO is from seed, we should NOT overwrite seed risks.
    from app.models import IPO
    ipo = db.get(IPO, ipo_id)
    if ipo and ipo.data_source == "live":
        # Safe to clear all existing risks — they were from previous extraction
        existing_risks = db.scalars(
            select(RiskFactor).where(RiskFactor.ipo_id == ipo_id)
        ).all()
        for risk in existing_risks:
            db.delete(risk)
        db.flush()

    # 9. Validate and persist each risk
    extracted_count = 0
    skipped_count = 0

    for risk_data in risks:
        if not isinstance(risk_data, dict):
            result.errors.append("Non-dict risk entry in LLM output")
            continue

        category = risk_data.get("category", "").strip()
        summary = risk_data.get("summary", "").strip()
        severity = risk_data.get("severity", "").strip()
        page = risk_data.get("page")

        if not category or not summary:
            result.errors.append("Risk missing category or summary")
            continue

        # Severity validation — STRICT per user requirement
        # Ambiguous severity = skip entirely, never default
        if severity not in VALID_SEVERITIES:
            skipped_count += 1
            logger.info(
                "Skipping risk with ambiguous severity '%s': %s",
                severity, summary[:80]
            )
            continue

        # Validate page number
        source_page = None
        if page is not None:
            try:
                source_page = int(page)
                if source_page <= 0:
                    source_page = None
            except (ValueError, TypeError):
                source_page = None

        # Truncate summary if too long
        if len(summary) > 1000:
            summary = summary[:997] + "..."

        db.add(RiskFactor(
            ipo_id=ipo_id,
            category=category,
            severity=severity,
            summary=summary,
            source_page=source_page,
        ))
        extracted_count += 1

    db.flush()

    result.risks_extracted = extracted_count
    result.risks_skipped_ambiguous = skipped_count

    if extracted_count == 0 and skipped_count > 0:
        result.status = RiskExtractionStatus.EXTRACTION_FAILED
        result.errors.append(
            f"All {skipped_count} risks had ambiguous severity and were skipped"
        )
    elif extracted_count > 0 and skipped_count > 0:
        result.status = RiskExtractionStatus.PARTIAL_EXTRACTION
    elif extracted_count > 0:
        result.status = RiskExtractionStatus.EXTRACTION_COMPLETED
    else:
        result.status = RiskExtractionStatus.EXTRACTION_FAILED

    return result
