"""Live IPO data provider — fetches current IPO data from the web.

Scrapes IPO Central's mainboard IPO list, which contains IPOs
with their price bands, issue sizes, and dates in a clean HTML table.
Then enriches each record by fetching its detail page for additional
metadata (lot size, face value, listing date, fresh issue, OFS, etc.).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.providers import IPOProvider, NormalizedIPO

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────
SOURCE_URL = "https://ipocentral.in/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

TIMEOUT_SECONDS = 15
DETAIL_TIMEOUT_SECONDS = 10


# ── Status inference from row background color ───────────────────────
# IPO Central uses background-color on <tr> to indicate lifecycle status.
ROW_COLOR_TO_STATUS = {
    "#DDFFDD":   "Ongoing",    # light green = currently open for subscription
    "#EEDDFF":   "Closed",     # light purple = subscription closed
    "#FFEEDDFF": "Listed",     # light peach/orange = listed or allotted
}
DEFAULT_STATUS = "Upcoming"    # no background color = not yet open

# ── Month lookup ─────────────────────────────────────────────────────
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


# ── Parsing helpers ───────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a company name to a URL-friendly slug.

    Example: "Deepa Jewellers" -> "deepa-jewellers"
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)   # remove special chars
    slug = re.sub(r"[\s]+", "-", slug)           # spaces -> hyphens
    slug = re.sub(r"-+", "-", slug)              # collapse multiple hyphens
    return slug.strip("-")


def _parse_price_band(price_str: str) -> tuple[float, float]:
    """Parse a price band string like '168 – 177' into (low, high).

    Handles:
      - "168 – 177"  -> (168.0, 177.0)
      - "102"        -> (102.0, 102.0)   (fixed price)
      - ""           -> (0.0, 0.0)
    """
    if not price_str:
        return 0.0, 0.0
    # Split on various dash characters (en-dash, em-dash, hyphen)
    parts = re.split(r"\s*[–—-]\s*", price_str)
    try:
        low = float(parts[0].replace(",", ""))
        high = float(parts[-1].replace(",", "")) if len(parts) > 1 else low
        return low, high
    except ValueError:
        return 0.0, 0.0


def _parse_issue_size(size_str: str) -> float:
    """Parse issue size like '459.7' or '1,200.5' into a float."""
    if not size_str:
        return 0.0
    try:
        return float(size_str.replace(",", "").strip())
    except ValueError:
        return 0.0


def _extract_status(row_tag) -> str:
    """Infer IPO status from the row's background-color style.

    IPO Central color-codes rows:
      - No color    -> Upcoming
      - #DDFFDD     -> Ongoing (green)
      - #EEDDFF     -> Closed (purple)
      - #FFEEDDFF   -> Listed (peach)
    """
    style = row_tag.get("style", "")
    for color, status in ROW_COLOR_TO_STATUS.items():
        if color.lower() in style.lower():
            return status
    return DEFAULT_STATUS


def _parse_date_range(date_str: str) -> tuple[str | None, str | None]:
    """Parse '31 Aug – 2 Sep' or '1 – 3 Sep' into ('YYYY-MM-DD', 'YYYY-MM-DD')."""
    if not date_str:
        return None, None

    parts = re.split(r"\s*[–—-]\s*", date_str)
    if len(parts) != 2:
        return None, None

    start_str, end_str = parts[0].strip(), parts[1].strip()

    start_match = re.search(r"(\d+)\s*([a-zA-Z]+)?", start_str)
    end_match = re.search(r"(\d+)\s*([a-zA-Z]+)", end_str)

    if not start_match or not end_match:
        return None, None

    start_day = int(start_match.group(1))
    start_month_str = start_match.group(2)

    end_day = int(end_match.group(1))
    end_month_str = end_match.group(2)

    if not start_month_str:
        start_month_str = end_month_str

    if not start_month_str or not end_month_str:
        return None, None

    start_month = MONTH_MAP.get(start_month_str.lower()[:3])
    end_month = MONTH_MAP.get(end_month_str.lower()[:3])

    if not start_month or not end_month:
        return None, None

    current_year = datetime.now().year
    start_year = current_year
    end_year = current_year

    # Handle year crossing (e.g., Dec - Jan)
    if start_month == 12 and end_month == 1:
        if datetime.now().month == 12:
            end_year += 1
        else:
            start_year -= 1

    try:
        start_date = f"{start_year:04d}-{start_month:02d}-{start_day:02d}"
        end_date = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"
        # Validate they are real dates
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        return start_date, end_date
    except ValueError:
        return None, None


# ── Detail-page parsing helpers ──────────────────────────────────────

def _parse_full_date(date_str: str) -> str | None:
    """Parse a full date like '8 September 2026' into 'YYYY-MM-DD'.

    Handles:
      - "8 September 2026"  -> "2026-09-08"
      - "Coming soon"       -> None
      - ""                  -> None
    """
    if not date_str:
        return None

    match = re.search(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})", date_str.strip())
    if not match:
        return None

    day = int(match.group(1))
    month_str = match.group(2).lower()
    year = int(match.group(3))

    month = MONTH_MAP.get(month_str[:3])
    if not month:
        return None

    try:
        result = f"{year:04d}-{month:02d}-{day:02d}"
        datetime.strptime(result, "%Y-%m-%d")  # validate
        return result
    except ValueError:
        return None


def _parse_lot_size_and_investment(text: str) -> tuple[int | None, float | None]:
    """Parse '84 shares (INR 14,868)' into (84, 14868.0).

    Returns (lot_size, min_investment). Either may be None if unparseable.
    """
    lot_size = None
    min_investment = None

    lot_match = re.search(r"([\d,]+)\s*shares?", text, re.IGNORECASE)
    if lot_match:
        try:
            lot_size = int(lot_match.group(1).replace(",", ""))
        except ValueError:
            pass

    inv_match = re.search(r"INR\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if inv_match:
        try:
            min_investment = float(inv_match.group(1).replace(",", ""))
        except ValueError:
            pass

    return lot_size, min_investment


def _parse_face_value(text: str) -> float | None:
    """Parse 'INR 2 per share' into 2.0. Returns None if unparseable."""
    match = re.search(r"INR\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_crore_value(text: str) -> float | None:
    """Parse 'INR 250 crore' or 'INR 199.05 – 209.72 crore' into a float.

    For ranges, returns the higher value. Returns 0.0 for 'Nil'.
    Returns None if the text is empty or unparseable.

    Handles OFS strings like '1,18,48,340 shares (INR 199.05 – 209.72 crore)'
    by specifically extracting the INR...crore portion.
    """
    if not text:
        return None

    cleaned = text.strip().lower()
    if cleaned == "nil" or cleaned == "–" or cleaned == "-":
        return 0.0

    # First try: extract "INR X crore" or "INR X – Y crore" specifically
    crore_match = re.search(
        r"INR\s*([\d,]+(?:\.\d+)?(?:\s*[–—-]\s*[\d,]+(?:\.\d+)?)?)\s*crore",
        text,
        re.IGNORECASE,
    )
    if crore_match:
        crore_text = crore_match.group(1)
        numbers = re.findall(r"[\d,]+(?:\.\d+)?", crore_text)
        if numbers:
            try:
                values = [float(n.replace(",", "")) for n in numbers]
                return max(values)
            except ValueError:
                pass

    # Fallback: just "INR X" without "crore" (e.g. simple number)
    inr_match = re.search(r"INR\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if inr_match:
        try:
            return float(inr_match.group(1).replace(",", ""))
        except ValueError:
            pass

    return None


def _parse_shares_offered(text: str) -> int | None:
    """Parse 'shares' count from detail page text.

    Handles:
      - "1,18,48,340 shares (INR 199.05 – 209.72 crore)"  -> 11848340
      - "77,91,789 shares"                                 -> 7791789
    """
    match = re.search(r"([\d,]+)\s*shares?", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _build_detail_lookup(table) -> dict[str, str]:
    """Build a key->value lookup from a two-column detail table.

    Returns a dict with lowercase keys for case-insensitive matching.
    Example: {"fresh issue": "INR 250 crore", "face value": "INR 2 per share"}
    """
    lookup: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) == 2:
            key = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            lookup[key] = value
    return lookup


def _extract_sector_from_text(desc: str) -> str | None:
    """Extract a factual, source-backed sector from company description text.

    Returns None if no definitive sector can be determined from the source text.
    Never fabricates sectors.
    """
    if not desc:
        return None
    d = desc.lower()
    if "real estate" in d:
        return "Real Estate"
    if "speciality chemicals" in d or "specialty chemicals" in d:
        return "Specialty Chemicals"
    if "chemicals" in d or "inorganic" in d:
        return "Chemicals"
    if "solar energy" in d or "renewable energy" in d:
        return "Renewable Energy"
    if "textile" in d or "knitwear" in d or "garment" in d or "fibre" in d:
        return "Textiles"
    if "logistics" in d:
        return "Logistics"
    if "farming" in d or "agrochemicals" in d or "agricultural" in d:
        return "Agriculture"
    if "jewellery" in d or "jewelry" in d or "fashion" in d or "luxury" in d:
        return "Consumer Discretionary"
    if "payment" in d or "fintech" in d:
        return "Financial Technology"
    if "asset reconstruction" in d or "financial services" in d or "banking" in d:
        return "Financial Services"
    if "rental" in d or "subscription" in d:
        return "Consumer Technology"
    if "gas generation" in d or "utilities" in d:
        return "Utilities"
    if "façade" in d or "facade" in d or "fenestration" in d:
        return "Building Materials"
    if "transformer" in d or "transmission" in d or "epc" in d or "infrastructure" in d:
        return "Infrastructure"
    if "travel" in d or "tourism" in d:
        return "Travel & Tourism"
    return None


# ── Provider class ───────────────────────────────────────────────────

class LiveIPOProvider(IPOProvider):
    """Fetches real-time IPO data from IPO Central's mainboard IPO list."""

    def __init__(self, url: str = SOURCE_URL):
        self.url = url
        self._session: requests.Session | None = None

    def _get_session(self) -> requests.Session:
        """Get or create a reusable HTTP session for this batch."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(HEADERS)
        return self._session

    def _fetch_page(self) -> str:
        """Fetch raw HTML from the IPO listing page.

        Returns:
            The HTML content as a string.

        Raises:
            requests.RequestException: If the HTTP request fails.
        """
        session = self._get_session()
        response = session.get(self.url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.text

    def _fetch_detail_page(self, url: str) -> str | None:
        """Fetch HTML from a single IPO detail page.

        Returns None on any HTTP/connection error — the caller will
        proceed with calendar-level data only.
        """
        try:
            session = self._get_session()
            response = session.get(url, timeout=DETAIL_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.warning("LiveIPOProvider: detail page failed for %s: %s", url, exc)
            return None

    def _parse_html(self, html: str) -> list[dict]:
        """Parse the IPO Central HTML into a list of raw dictionaries.

        Each dict contains:
            name, slug, status, detail_url, dates, price_low, price_high, issue_size_crore

        This is raw parsed data — NOT yet NormalizedIPO objects.
        """
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        if not tables:
            logger.warning("LiveIPOProvider: no tables found in HTML")
            return []

        # Find the mainboard and SME IPO tables by their first column headers
        target_tables = []
        for t in tables:
            header_row = t.find("tr")
            if header_row:
                first_col = header_row.get_text(strip=True).lower()
                if "upcoming ipo" in first_col or "upcoming mainboard" in first_col:
                    target_tables.append((t, "Mainboard"))
                elif "upcoming sme ipo" in first_col or "sme ipo" in first_col:
                    target_tables.append((t, "SME"))

        if not target_tables:
            logger.warning("LiveIPOProvider: no valid IPO tables found")
            return []

        results: list[dict] = []

        for table, segment in target_tables:
            rows = table.find_all("tr")[1:]  # skip header row
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                name = cells[0].get_text(strip=True)
                # Strip emoji and trailing whitespace from company names
                name = re.sub(r"[\U0001f300-\U0001faff\U00002702-\U000027b0]+", "", name).strip()

                # Skip navigation rows (e.g. "More Mainboard IPOs")
                if not name or "more" in name.lower() and "ipo" in name.lower():
                    continue

                status = _extract_status(row)

                link_tag = cells[0].find("a")
                detail_url = link_tag["href"] if link_tag else ""
                dates = cells[1].get_text(strip=True)
                price_low, price_high = _parse_price_band(cells[2].get_text(strip=True))
                issue_size = _parse_issue_size(cells[3].get_text(strip=True))

                # Skip rows with no price and no size (not real IPO data)
                if price_low == 0 and price_high == 0 and issue_size == 0:
                    continue

                results.append({
                    "name": name,
                    "slug": _slugify(name),
                    "status": status,
                    "detail_url": detail_url,
                    "dates": dates,
                    "price_low": price_low,
                    "price_high": price_high,
                    "issue_size_crore": issue_size,
                    "listing_segment": segment,
                })

        logger.info("LiveIPOProvider: parsed %d IPO rows from HTML", len(results))
        return results

    def _parse_detail_html(self, html: str) -> dict:
        """Parse an IPO Central detail page into an enrichment dictionary.

        Returns a dict of enrichment fields. Missing fields are omitted
        (not set to None) so that the merge step preserves calendar values.
        """
        enrichment: dict = {}
        soup = BeautifulSoup(html, "html.parser")

        # ── Extract description and sector from article paragraphs ────
        entry = soup.find(class_=re.compile(r"entry-content|post-content|td-post-content")) or soup
        for p_tag in entry.find_all("p"):
            text = p_tag.get_text(strip=True)
            if "IPO Description" in text or "incorporated in" in text.lower() or "engaged in" in text.lower():
                cleaned_desc = re.sub(r"^.*?IPO Description\s*[–—-]?\s*", "", text, flags=re.IGNORECASE).strip()
                if cleaned_desc:
                    enrichment["description"] = cleaned_desc
                    sec = _extract_sector_from_text(cleaned_desc)
                    if sec:
                        enrichment["sector"] = sec
                break

        tables = soup.find_all("table")

        if not tables:
            return enrichment

        # ── IPO Details table (Table 1 typically) ─────────────────────
        # Look for the table containing "Issue Price" or "IPO Dates"
        details_table = None
        dates_table = None

        for t in tables:
            lookup = _build_detail_lookup(t)
            keys_text = " ".join(lookup.keys())

            if "issue price" in keys_text and details_table is None:
                details_table = lookup
            if "listing date" in keys_text and dates_table is None:
                dates_table = lookup

        # ── Extract from IPO Details table ────────────────────────────
        if details_table:
            # Fresh Issue
            for key, value in details_table.items():
                if "fresh issue" in key and "total" not in key:
                    parsed = _parse_crore_value(value)
                    if parsed is not None:
                        enrichment["fresh_issue_crore"] = parsed
                    break

            # OFS
            for key, value in details_table.items():
                if "offer for sale" in key or "ofs" in key:
                    parsed = _parse_crore_value(value)
                    if parsed is not None:
                        enrichment["ofs_crore"] = parsed
                    # Also try to extract shares offered from OFS text
                    if "shares" in value.lower():
                        shares = _parse_shares_offered(value)
                        if shares is not None:
                            enrichment["shares_offered"] = shares
                    break

            # Lot Size & Minimum Investment
            for key, value in details_table.items():
                if "lot size" in key or "minimum bid" in key:
                    lot_size, min_investment = _parse_lot_size_and_investment(value)
                    if lot_size is not None:
                        enrichment["lot_size"] = lot_size
                    if min_investment is not None:
                        enrichment["min_investment"] = min_investment
                    break

            # Face Value
            for key, value in details_table.items():
                if "face value" in key:
                    fv = _parse_face_value(value)
                    if fv is not None:
                        enrichment["face_value"] = fv
                    break

            # Pre-issue shares (for shares_offered if OFS didn't provide it)
            if "shares_offered" not in enrichment:
                for key, value in details_table.items():
                    if "pre-issue" in key or "pre issue" in key:
                        shares = _parse_shares_offered(value)
                        if shares is not None:
                            enrichment["shares_offered"] = shares
                        break

        # ── Extract from Dates & Listing Performance table ────────────
        if dates_table:
            for key, value in dates_table.items():
                if "listing date" in key:
                    listing_date = _parse_full_date(value)
                    if listing_date is not None:
                        enrichment["listing_date"] = listing_date
                    break

        return enrichment

    @staticmethod
    def _merge_records(calendar: dict, detail: dict) -> dict:
        """Merge calendar and detail data, preserving valid calendar values.

        Detail values only override when they are present and valid.
        Calendar values are never replaced with None.
        """
        merged = dict(calendar)
        for key, value in detail.items():
            if value is not None:
                merged[key] = value
        return merged

    def _normalize_record(self, raw: dict) -> NormalizedIPO | None:
        """Convert a raw (possibly enriched) dictionary into a validated NormalizedIPO."""
        try:
            open_date, close_date = _parse_date_range(raw.get("dates", ""))

            return NormalizedIPO(
                name=raw["name"],
                slug=raw["slug"],
                sector=raw.get("sector"),
                description=raw.get("description", ""),
                status=raw["status"],
                listing_segment=raw.get("listing_segment"),
                issue_size_crore=raw["issue_size_crore"],
                price_low=raw["price_low"],
                price_high=raw["price_high"],
                open_date=open_date,
                close_date=close_date,
                issue_date=open_date,  # Backward compatibility
                listing_date=raw.get("listing_date"),
                fresh_issue_crore=raw.get("fresh_issue_crore"),
                ofs_crore=raw.get("ofs_crore"),
                lot_size=raw.get("lot_size"),
                min_investment=raw.get("min_investment"),
                face_value=raw.get("face_value"),
                shares_offered=raw.get("shares_offered"),
                data_source="live",
                source_url=raw.get("detail_url") or None,
            )
        except (ValueError, KeyError) as exc:
            logger.warning("LiveIPOProvider: Failed to normalize %s: %s", raw.get("name"), exc)
            return None

    def fetch_current_ipos(self) -> list[NormalizedIPO]:
        """Fetch, enrich, and normalize live IPO data.

        Pipeline:
          1. Fetch calendar page → parse into raw records
          2. For each record with a detail_url, fetch & parse the detail page
          3. Merge calendar + detail data
          4. Normalize into NormalizedIPO objects
        """
        try:
            html = self._fetch_page()
            logger.info("LiveIPOProvider: fetched %d bytes from %s", len(html), self.url)
        except requests.RequestException as exc:
            logger.error("LiveIPOProvider: failed to fetch calendar page: %s", exc)
            return []

        raw_records = self._parse_html(html)

        # ── Detail-page enrichment ────────────────────────────────────
        fetched_urls: set[str] = set()
        enriched_records: list[dict] = []
        detail_success = 0
        detail_fail = 0

        for raw in raw_records:
            detail_url = raw.get("detail_url", "")

            if detail_url and detail_url not in fetched_urls:
                fetched_urls.add(detail_url)
                detail_html = self._fetch_detail_page(detail_url)

                if detail_html:
                    detail_data = self._parse_detail_html(detail_html)
                    raw = self._merge_records(raw, detail_data)
                    detail_success += 1
                else:
                    detail_fail += 1
            elif detail_url in fetched_urls:
                logger.debug("LiveIPOProvider: skipping duplicate detail_url %s", detail_url)

            enriched_records.append(raw)

        logger.info(
            "LiveIPOProvider: detail enrichment — %d success, %d failed",
            detail_success, detail_fail,
        )

        # ── Normalization ─────────────────────────────────────────────
        normalized_records = []
        for raw in enriched_records:
            normalized = self._normalize_record(raw)
            if normalized:
                normalized_records.append(normalized)

        logger.info("LiveIPOProvider: successfully normalized %d records", len(normalized_records))

        # Clean up session after batch
        if self._session:
            self._session.close()
            self._session = None

        return normalized_records
