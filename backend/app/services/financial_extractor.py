"""Financial data extraction from DRHP/RHP filing Source chunks.

Architecture:
    1. Identify candidate Source chunks containing financial statements
       using section heading keywords and content pattern matching.
    2. Send identified chunks to the LLM (via existing Groq provider)
       with a strict JSON extraction schema.
    3. Validate and normalize extracted values using existing utilities.
    4. Persist to FinancialPeriod + FinancialMetric with full provenance.
    5. Idempotent: re-running updates existing rows, never duplicates.

The LLM NEVER fabricates data — it extracts only what appears in the text.
If extraction fails or the LLM is unavailable, no rows are created.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.financials import parse_indian_number
from app.models import (
    Document,
    FinancialMetric,
    FinancialPeriod,
    Source,
)

logger = logging.getLogger(__name__)


# ── Extraction status codes ──────────────────────────────────────────
class ExtractionStatus:
    DOCUMENT_UNAVAILABLE = "document_unavailable"
    PROCESSING_INCOMPLETE = "processing_incomplete"
    NO_FINANCIAL_SECTIONS = "no_financial_sections_found"
    LLM_UNAVAILABLE = "llm_unavailable"
    EXTRACTION_FAILED = "extraction_failed"
    PARTIAL_EXTRACTION = "partial_extraction"
    EXTRACTION_COMPLETED = "extraction_completed"


@dataclass
class ExtractionResult:
    """Result of a financial extraction attempt."""
    status: str
    periods_extracted: int = 0
    periods_updated: int = 0
    metrics_detail: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    chunks_identified: int = 0
    chunks_sent: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "periods_extracted": self.periods_extracted,
            "periods_updated": self.periods_updated,
            "metrics_detail": self.metrics_detail,
            "errors": self.errors,
            "chunks_identified": self.chunks_identified,
            "chunks_sent": self.chunks_sent,
        }


# ── Keywords for identifying financial statement chunks ──────────────
FINANCIAL_SECTION_KEYWORDS = [
    "statement of profit and loss",
    "statement of profit & loss",
    "income statement",
    "profit and loss",
    "profit & loss",
    "balance sheet",
    "statement of assets and liabilities",
    "statement of assets & liabilities",
    "cash flow",
    "restated financial",
    "restated consolidated",
    "restated standalone",
    "summary of financial information",
    "financial information",
    "financial statements",
    "basis for issue price",
    "objects of the issue",
]

FINANCIAL_CONTENT_KEYWORDS = [
    "revenue from operations",
    "total income",
    "total revenue",
    "profit before tax",
    "profit after tax",
    "net profit",
    "ebitda",
    "total equity",
    "total assets",
    "total borrowings",
    "total debt",
    "earnings per share",
    "eps",
    "depreciation",
    "cash and cash equivalents",
    "reserves and surplus",
    "share capital",
]


# ── LLM extraction prompt ───────────────────────────────────────────
EXTRACTION_PROMPT = """You are a financial data extraction engine. You extract ONLY structured financial data that is explicitly present in the provided text from an Indian IPO prospectus (DRHP/RHP).

## Rules
1. Extract ONLY values that are explicitly stated in the text. NEVER fabricate, estimate, or infer values.
2. If a metric is not present in the text, omit it entirely from the output.
3. Identify ALL fiscal periods present in the text (e.g., FY2022, FY2023, FY2024, Q1 FY2025).
4. All monetary values should be reported in the unit stated in the text (lakhs, crores, millions, etc.).
5. Include the raw text value exactly as it appears, plus the unit.
6. For period_end dates, use YYYY-MM-DD format. Indian fiscal years end March 31 (e.g., FY2024 → 2024-03-31). If the exact date is not stated, use March 31 for annual periods.
7. period_type must be "Annual" for full-year periods, or "Interim" for partial periods (Q1, H1, 9M, etc.).
8. For interim periods, include interim_period (e.g., "Q1", "H1", "9M").

## Output Format
Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{
  "periods": [
    {
      "fiscal_year": "FY2024",
      "period_end": "2024-03-31",
      "period_type": "Annual",
      "interim_period": null,
      "metrics": {
        "revenue": {"raw": "1,255.6", "unit": "crore", "value": 1255.6, "confidence": "high"},
        "ebitda": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "ebit": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "pat": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "eps": {"raw": "...", "unit": "inr", "value": ..., "confidence": "high"},
        "total_debt": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "cash": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "equity": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"},
        "assets": {"raw": "...", "unit": "...", "value": ..., "confidence": "high"}
      }
    }
  ],
  "extraction_notes": "Any relevant notes about the data quality or ambiguities"
}

confidence must be one of: "high", "medium", "low".
Only include metrics that are explicitly present in the text.

## Text to extract from:
{text}"""


def _identify_financial_chunks(
    sources: list[Source],
) -> list[Source]:
    """Identify Source chunks that likely contain financial statement data.

    Uses a two-pass approach:
    1. Section heading match (high confidence)
    2. Content keyword density (medium confidence)
    """
    candidates: list[tuple[float, Source]] = []

    for source in sources:
        if source.is_empty:
            continue

        text_lower = source.text.lower()
        score = 0.0

        # Pass 1: Section heading match
        section = (source.section or "").lower()
        for keyword in FINANCIAL_SECTION_KEYWORDS:
            if keyword in section:
                score += 5.0
                break

        # Pass 2: Content keyword density
        keyword_hits = 0
        for keyword in FINANCIAL_CONTENT_KEYWORDS:
            if keyword in text_lower:
                keyword_hits += 1

        # At least 3 financial keywords suggest a financial table
        if keyword_hits >= 3:
            score += keyword_hits * 0.5

        # Numeric density check — financial tables have lots of numbers
        numbers = re.findall(r"[\d,]+(?:\.\d+)?", source.text)
        if len(numbers) >= 5:
            score += 1.0

        if score >= 2.0:
            candidates.append((score, source))

    # Sort by score descending, take top chunks
    candidates.sort(key=lambda x: -x[0])
    # Limit to avoid sending too much to the LLM
    max_chunks = 10
    return [source for _, source in candidates[:max_chunks]]


def _normalize_metric_value(
    raw: str | None, unit: str | None, value: float | None
) -> float | None:
    """Normalize a metric value to INR Crore.

    Uses the existing parse_indian_number for raw-string parsing,
    and applies unit-based conversion for pre-parsed values.
    """
    # If we have a pre-parsed value with a unit, normalize it
    if value is not None and unit:
        unit_lower = unit.lower().strip()
        if unit_lower in ("crore", "cr", "crores", "cr."):
            return round(value, 4)
        elif unit_lower in ("lakh", "lakhs", "lac", "lacs"):
            return round(value * 0.01, 4)
        elif unit_lower in ("million", "mn", "millions"):
            return round(value * 0.1, 4)
        elif unit_lower in ("billion", "bn", "billions"):
            return round(value * 100.0, 4)
        elif unit_lower in ("inr", "rs", "rs.", "rupees", "per share"):
            # EPS and per-share values stay as absolute INR
            return round(value, 4)
        elif unit_lower in ("thousand", "thousands"):
            return round(value * 0.00001, 4)
        else:
            # Unknown unit — try parse_indian_number with raw
            pass

    # Fallback: try parsing the raw string
    if raw:
        combined = raw
        if unit:
            combined = f"{raw} {unit}"
        parsed = parse_indian_number(combined)
        if parsed is not None:
            return parsed

    return value if value is not None else None


def _validate_period(period_data: dict) -> list[str]:
    """Validate a single extracted period. Returns list of error messages."""
    errors = []
    fy = period_data.get("fiscal_year", "")
    pe = period_data.get("period_end", "")
    pt = period_data.get("period_type", "")

    if not fy:
        errors.append("Missing fiscal_year")
    if not pe:
        errors.append("Missing period_end")
    else:
        try:
            date.fromisoformat(pe)
        except (ValueError, TypeError):
            errors.append(f"Invalid period_end date: {pe}")

    if pt not in ("Annual", "Interim"):
        errors.append(f"Invalid period_type: {pt}")

    if pt == "Interim" and not period_data.get("interim_period"):
        errors.append("Interim period missing interim_period designation")

    # Validate metrics
    metrics = period_data.get("metrics", {})
    for metric_name, metric_data in metrics.items():
        if not isinstance(metric_data, dict):
            errors.append(f"Metric {metric_name} is not a dict")
            continue

        val = metric_data.get("value")
        if val is not None:
            try:
                float(val)
            except (ValueError, TypeError):
                errors.append(f"Non-numeric value for {metric_name}: {val}")

    return errors


def _validate_metric_value(name: str, value: float | None) -> float | None:
    """Apply domain-specific validation to a metric value.

    Returns None if the value is implausible, preserving NULL semantics.
    Never coerces unknown values to zero.
    """
    if value is None:
        return None

    # Revenue should not be negative (can be zero for pre-revenue companies)
    if name == "revenue" and value < 0:
        logger.warning("Rejecting negative revenue: %s", value)
        return None

    # Assets should not be negative
    if name == "assets" and value < 0:
        logger.warning("Rejecting negative assets: %s", value)
        return None

    # Equity can be negative (accumulated losses)
    # Debt can be zero but not negative
    if name == "total_debt" and value < 0:
        logger.warning("Rejecting negative total_debt: %s", value)
        return None

    # Cash should not be negative
    if name == "cash" and value < 0:
        logger.warning("Rejecting negative cash: %s", value)
        return None

    return value


def _parse_llm_response(response_text: str) -> dict | None:
    """Parse and validate the LLM extraction response."""
    if not response_text or not response_text.strip():
        return None

    # Try to extract JSON from the response
    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
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

    if "periods" not in data or not isinstance(data["periods"], list):
        return None

    return data


def extract_financials(
    db: Session,
    document_id: int,
    company_id: int,
    llm_provider=None,
) -> ExtractionResult:
    """Extract structured financial data from a processed Document's Source chunks.

    Args:
        db: SQLAlchemy session
        document_id: ID of the processed Document
        company_id: ID of the Company to create FinancialPeriod/Metric rows for
        llm_provider: Optional LLM provider override (for testing)

    Returns:
        ExtractionResult with status and details
    """
    result = ExtractionResult(status=ExtractionStatus.EXTRACTION_FAILED)

    # 1. Verify document exists and is processed
    document = db.get(Document, document_id)
    if not document:
        result.status = ExtractionStatus.DOCUMENT_UNAVAILABLE
        result.errors.append(f"Document {document_id} not found")
        return result

    if document.processing_status != "completed":
        result.status = ExtractionStatus.PROCESSING_INCOMPLETE
        result.errors.append(
            f"Document processing status is '{document.processing_status}', expected 'completed'"
        )
        return result

    # 2. Fetch all source chunks for this document
    sources = db.scalars(
        select(Source)
        .where(Source.document_id == document_id, Source.is_empty == False)
        .order_by(Source.page, Source.id)
    ).all()

    if not sources:
        result.status = ExtractionStatus.NO_FINANCIAL_SECTIONS
        result.errors.append("No non-empty source chunks found for document")
        return result

    # 3. Identify financial statement chunks
    financial_chunks = _identify_financial_chunks(list(sources))
    result.chunks_identified = len(financial_chunks)

    if not financial_chunks:
        result.status = ExtractionStatus.NO_FINANCIAL_SECTIONS
        result.errors.append("No chunks identified as containing financial data")
        return result

    # 4. Get LLM provider
    if llm_provider is None:
        from app.agent.providers import get_llm_provider
        llm_provider = get_llm_provider()

    if not llm_provider.is_available:
        result.status = ExtractionStatus.LLM_UNAVAILABLE
        result.errors.append("LLM provider is not available for extraction")
        return result

    # 5. Combine relevant chunks and send to LLM
    combined_text = ""
    chunk_refs: list[dict] = []
    for chunk in financial_chunks:
        combined_text += f"\n\n--- Page {chunk.page}, Section: {chunk.section or 'N/A'} ---\n"
        combined_text += chunk.text
        chunk_refs.append({
            "chunk_id": chunk.chunk_id,
            "page": chunk.page,
            "section": chunk.section,
            "source_id": chunk.id,
        })

    # Truncate if too long (LLM context limits)
    max_chars = 12000
    if len(combined_text) > max_chars:
        combined_text = combined_text[:max_chars]

    result.chunks_sent = len(financial_chunks)

    # 6. Call LLM for extraction
    try:
        # Use string concatenation instead of .format() to avoid KeyError
        # when combined_text contains curly braces (common in financial data)
        prompt = EXTRACTION_PROMPT.replace("{text}", combined_text)
        response = llm_provider.generate_sync(
            messages=[
                {"role": "system", "content": "You are a financial data extraction engine. Output ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.05,
            max_tokens=3000,
            response_format="json_object",
        )
    except Exception as e:
        result.status = ExtractionStatus.EXTRACTION_FAILED
        result.errors.append(f"LLM call failed: {str(e)[:200]}")
        return result

    content = response.get("content", "")

    # 7. Parse LLM response
    extracted = _parse_llm_response(content)
    if not extracted:
        result.status = ExtractionStatus.EXTRACTION_FAILED
        result.errors.append("Failed to parse LLM extraction response as valid JSON")
        return result

    periods = extracted.get("periods", [])
    if not periods:
        result.status = ExtractionStatus.NO_FINANCIAL_SECTIONS
        result.errors.append("LLM returned no periods in extraction")
        return result

    # 8. Validate, normalize, and persist each period
    new_count = 0
    updated_count = 0

    # Build source reference from the chunks used
    primary_ref = chunk_refs[0]["chunk_id"] if chunk_refs else f"doc-{document_id}"

    for period_data in periods:
        validation_errors = _validate_period(period_data)
        if validation_errors:
            result.errors.extend(
                [f"Period {period_data.get('fiscal_year', '?')}: {e}" for e in validation_errors]
            )
            continue

        fiscal_year = period_data["fiscal_year"]
        period_end_str = period_data["period_end"]
        period_type = period_data["period_type"]
        interim_period = period_data.get("interim_period")

        try:
            period_end = date.fromisoformat(period_end_str)
        except (ValueError, TypeError):
            result.errors.append(f"Invalid period_end for {fiscal_year}: {period_end_str}")
            continue

        metrics_data = period_data.get("metrics", {})
        if not metrics_data:
            result.errors.append(f"No metrics found for {fiscal_year}")
            continue

        # Normalize all metric values
        METRIC_NAMES = ["revenue", "ebitda", "ebit", "pat", "eps", "total_debt", "cash", "equity", "assets"]
        normalized_metrics: dict[str, float | None] = {}
        derived_fields: dict[str, Any] = {}
        has_any_value = False

        for metric_name in METRIC_NAMES:
            if metric_name not in metrics_data:
                normalized_metrics[metric_name] = None
                continue

            md = metrics_data[metric_name]
            if not isinstance(md, dict):
                normalized_metrics[metric_name] = None
                continue

            raw = md.get("raw")
            unit = md.get("unit")
            value = md.get("value")
            confidence = md.get("confidence", "medium")

            # EPS stays in absolute INR, not converted to crore
            if metric_name == "eps":
                if value is not None:
                    try:
                        normalized_val = float(value)
                    except (ValueError, TypeError):
                        normalized_val = None
                else:
                    normalized_val = None
            else:
                normalized_val = _normalize_metric_value(raw, unit, value)

            # Validate
            validated_val = _validate_metric_value(metric_name, normalized_val)
            normalized_metrics[metric_name] = validated_val

            if validated_val is not None:
                has_any_value = True
                derived_fields[metric_name] = {
                    "raw": raw,
                    "unit": unit,
                    "confidence": confidence,
                    "source_chunk": primary_ref,
                }

        if not has_any_value:
            result.errors.append(f"No valid metric values extracted for {fiscal_year}")
            continue

        # 9. Idempotent upsert with Field-Level Precedence
        existing_period = db.scalar(
            select(FinancialPeriod).where(
                FinancialPeriod.company_id == company_id,
                FinancialPeriod.period_end == period_end,
            )
        )

        doc_type = document.type.upper() if document.type else "UNKNOWN"
        DOC_WEIGHTS = {"PROSPECTUS": 30, "RHP": 20, "DRHP": 10, "UNKNOWN": 0}
        incoming_weight = DOC_WEIGHTS.get(doc_type, 0)

        # Update derived fields with weight
        for k in derived_fields:
            derived_fields[k]["weight"] = incoming_weight
            derived_fields[k]["doc_type"] = doc_type

        if existing_period:
            existing_metric = db.scalar(
                select(FinancialMetric).where(
                    FinancialMetric.period_id == existing_period.id
                )
            )
            if existing_metric:
                if existing_metric.source_type not in ["filing_extraction", None]:
                    result.errors.append(
                        f"Skipping {fiscal_year}: existing data from '{existing_metric.source_type}' "
                        f"takes precedence over filing extraction"
                    )
                    continue

                existing_derived = dict(existing_metric.derived_fields or {})
                updated_any = False

                for mn in METRIC_NAMES:
                    val = normalized_metrics.get(mn)
                    if val is not None:
                        # Field-level precedence check
                        existing_weight = existing_derived.get(mn, {}).get("weight", 0)
                        if incoming_weight >= existing_weight:
                            setattr(existing_metric, mn, val)
                            existing_derived[mn] = derived_fields[mn]
                            updated_any = True

                if updated_any:
                    existing_metric.source_type = "filing_extraction"
                    existing_metric.source_reference = primary_ref
                    existing_metric.derived_fields = existing_derived
                    updated_count += 1
            else:
                # Period exists but no metric — create one
                metric = FinancialMetric(
                    period_id=existing_period.id,
                    revenue=normalized_metrics.get("revenue"),
                    ebitda=normalized_metrics.get("ebitda"),
                    ebit=normalized_metrics.get("ebit"),
                    pat=normalized_metrics.get("pat"),
                    eps=normalized_metrics.get("eps"),
                    total_debt=normalized_metrics.get("total_debt"),
                    cash=normalized_metrics.get("cash"),
                    equity=normalized_metrics.get("equity"),
                    assets=normalized_metrics.get("assets"),
                    source_type="filing_extraction",
                    source_reference=primary_ref,
                    derived_fields=derived_fields,
                )
                db.add(metric)
                new_count += 1
        else:
            # Create new period + metric
            period = FinancialPeriod(
                company_id=company_id,
                period_end=period_end,
                period_type=period_type,
                interim_period=interim_period,
                fiscal_year=fiscal_year,
            )
            db.add(period)
            db.flush()

            metric = FinancialMetric(
                period_id=period.id,
                revenue=normalized_metrics.get("revenue"),
                ebitda=normalized_metrics.get("ebitda"),
                ebit=normalized_metrics.get("ebit"),
                pat=normalized_metrics.get("pat"),
                eps=normalized_metrics.get("eps"),
                total_debt=normalized_metrics.get("total_debt"),
                cash=normalized_metrics.get("cash"),
                equity=normalized_metrics.get("equity"),
                assets=normalized_metrics.get("assets"),
                source_type="filing_extraction",
                source_reference=primary_ref,
                derived_fields=derived_fields,
            )
            db.add(metric)
            new_count += 1

        result.metrics_detail.append({
            "fiscal_year": fiscal_year,
            "period_end": period_end_str,
            "period_type": period_type,
            "metrics_available": [k for k, v in normalized_metrics.items() if v is not None],
            "action": "updated" if existing_period else "created",
        })

    db.flush()

    result.periods_extracted = new_count
    result.periods_updated = updated_count
    total = new_count + updated_count

    if total == 0 and result.errors:
        result.status = ExtractionStatus.EXTRACTION_FAILED
    elif total > 0 and result.errors:
        result.status = ExtractionStatus.PARTIAL_EXTRACTION
    elif total > 0:
        result.status = ExtractionStatus.EXTRACTION_COMPLETED
    else:
        result.status = ExtractionStatus.NO_FINANCIAL_SECTIONS

    return result
