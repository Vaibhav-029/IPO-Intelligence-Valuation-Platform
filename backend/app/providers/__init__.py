"""IPO data provider abstraction.

This module defines a clean interface for fetching IPO data from external sources.
The provider pattern allows swapping data sources (e.g., seed file, web scraper,
API) without changing the sync logic.

Currently implemented:
    - SeedFileProvider: reads from backend/data/ipo_companies.json
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ── Where the seed data lives ─────────────────────────────────────────
DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "ipo_companies.json"


# ── Normalized IPO record ─────────────────────────────────────────────
class NormalizedIPO(BaseModel):
    """A validated, normalized IPO record.

    This is the contract between any provider and the sync service.
    Invalid or incomplete records will fail Pydantic validation and be
    rejected safely — they never reach the database.
    """
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    sector: Optional[str] = Field(default=None, max_length=100)
    exchange: str = Field(default="NSE / BSE", max_length=30)
    description: str = Field(default="")
    status: str = Field(default="Upcoming")
    issue_size_crore: float = Field(ge=0)
    price_low: float = Field(ge=0)
    price_high: float = Field(ge=0)
    issue_date: Optional[str] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    listing_date: Optional[str] = None
    fresh_issue_crore: Optional[float] = None
    ofs_crore: Optional[float] = None
    lot_size: Optional[int] = None
    min_investment: Optional[float] = None
    face_value: Optional[float] = None
    shares_offered: Optional[int] = None
    data_source: str = Field(default="seed")
    source_url: Optional[str] = None

    # Optional nested data — may be absent for Upcoming IPOs
    financials: list[dict] = Field(default_factory=list)
    valuation: Optional[dict] = None
    risk_factors: list[dict] = Field(default_factory=list)
    score_inputs: Optional[dict] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"Upcoming", "Ongoing", "Closed", "Listed"}
        if v not in allowed:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {allowed}")
        return v

    @field_validator("issue_date", "listing_date", "open_date", "close_date", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return v
        try:
            date.fromisoformat(str(v))
        except ValueError:
            raise ValueError(f"Invalid date format: '{v}'. Expected YYYY-MM-DD.")
        return str(v)


# ── Provider interface ────────────────────────────────────────────────
class IPOProvider(ABC):
    """Base class for IPO data providers."""

    @abstractmethod
    def fetch_current_ipos(self) -> list[NormalizedIPO]:
        """Fetch and return a list of normalized IPO records.

        Implementations should:
        - Fetch data from the source (file, API, scraper, etc.)
        - Validate and normalize each record
        - Log and skip invalid records (never raise for bad data)
        - Return only valid NormalizedIPO objects
        """
        ...


class SeedFileProvider(IPOProvider):
    """Reads IPO data from the local JSON seed file.

    This is the default provider for development and testing.
    It reads from backend/data/ipo_companies.json.
    """

    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = data_file

    def fetch_current_ipos(self) -> list[NormalizedIPO]:
        if not self.data_file.exists():
            logger.error("IPO data file not found at %s", self.data_file)
            return []

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        companies = data.get("companies", [])
        results: list[NormalizedIPO] = []

        for entry in companies:
            try:
                ipo_data = entry.get("ipo", {})
                normalized = NormalizedIPO(
                    name=entry["name"],
                    slug=entry["slug"],
                    sector=entry["sector"],
                    exchange=entry.get("exchange", "NSE / BSE"),
                    description=entry.get("description", ""),
                    status=ipo_data.get("status", "Upcoming"),
                    issue_size_crore=ipo_data.get("issue_size_crore", 0),
                    price_low=ipo_data.get("price_low", 0),
                    price_high=ipo_data.get("price_high", 0),
                    issue_date=ipo_data.get("issue_date"),
                    listing_date=ipo_data.get("listing_date"),
                    fresh_issue_crore=ipo_data.get("fresh_issue_crore", 0),
                    ofs_crore=ipo_data.get("ofs_crore", 0),
                    data_source="seed",
                    financials=entry.get("financials", []),
                    valuation=entry.get("valuation"),
                    risk_factors=entry.get("risk_factors", []),
                    score_inputs=entry.get("score_inputs"),
                )
                results.append(normalized)
            except Exception as exc:
                name = entry.get("name", "<unknown>")
                logger.warning("Skipping invalid IPO record '%s': %s", name, exc)

        logger.info(
            "SeedFileProvider: loaded %d valid IPO records (%d skipped)",
            len(results),
            len(companies) - len(results),
        )
        return results
