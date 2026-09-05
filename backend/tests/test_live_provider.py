"""Tests for LiveIPOProvider — calendar parsing, detail parsing, merge, normalization.

All tests use static HTML fixtures and do NOT call the live internet.
"""
import pytest
from datetime import datetime
from app.providers.live import (
    LiveIPOProvider,
    _parse_date_range,
    _parse_full_date,
    _parse_lot_size_and_investment,
    _parse_face_value,
    _parse_crore_value,
    _parse_shares_offered,
    _extract_status,
    _build_detail_lookup,
)
from app.providers import NormalizedIPO


# ── Helper: minimal tag-like object for _extract_status ──────────────
class FakeTag:
    def __init__(self, style=""):
        self._style = style
    def get(self, key, default=""):
        return self._style if key == "style" else default


# ═══════════════════════════════════════════════════════════════════════
# 1. Status extraction
# ═══════════════════════════════════════════════════════════════════════

class TestExtractStatus:
    def test_upcoming(self):
        assert _extract_status(FakeTag("")) == "Upcoming"

    def test_ongoing(self):
        assert _extract_status(FakeTag("background-color: #DDFFDD;")) == "Ongoing"

    def test_closed(self):
        assert _extract_status(FakeTag("background-color: #EEDDFF;")) == "Closed"

    def test_listed(self):
        assert _extract_status(FakeTag("background-color: #FFEEDDFF;")) == "Listed"

    def test_unknown_color_defaults_to_upcoming(self):
        assert _extract_status(FakeTag("background-color: #FF0000;")) == "Upcoming"


# ═══════════════════════════════════════════════════════════════════════
# 2. Calendar date range parsing
# ═══════════════════════════════════════════════════════════════════════

class TestParseDateRange:
    def test_different_months(self):
        year = datetime.now().year
        start, end = _parse_date_range("31 Aug – 2 Sep")
        assert start == f"{year}-08-31"
        assert end == f"{year}-09-02"

    def test_same_month(self):
        year = datetime.now().year
        start, end = _parse_date_range("1 – 3 Sep")
        assert start == f"{year}-09-01"
        assert end == f"{year}-09-03"

    def test_year_crossing(self):
        start, end = _parse_date_range("30 Dec – 2 Jan")
        assert start is not None
        assert end is not None
        assert start.endswith("-12-30")
        assert end.endswith("-01-02")

    def test_malformed_returns_none(self):
        assert _parse_date_range("Invalid") == (None, None)
        assert _parse_date_range("") == (None, None)
        assert _parse_date_range("abc – xyz") == (None, None)


# ═══════════════════════════════════════════════════════════════════════
# 3. Full date parsing (detail page)
# ═══════════════════════════════════════════════════════════════════════

class TestParseFullDate:
    def test_normal_date(self):
        assert _parse_full_date("8 September 2026") == "2026-09-08"

    def test_two_digit_day(self):
        assert _parse_full_date("31 August 2026") == "2026-08-31"

    def test_coming_soon(self):
        assert _parse_full_date("Coming soon") is None

    def test_empty(self):
        assert _parse_full_date("") is None

    def test_invalid_month(self):
        assert _parse_full_date("8 Foobar 2026") is None

    def test_invalid_day(self):
        assert _parse_full_date("32 January 2026") is None


# ═══════════════════════════════════════════════════════════════════════
# 4. Lot size & minimum investment parsing
# ═══════════════════════════════════════════════════════════════════════

class TestParseLotSizeAndInvestment:
    def test_normal(self):
        lot, inv = _parse_lot_size_and_investment("84 shares (INR 14,868)")
        assert lot == 84
        assert inv == 14868.0

    def test_different_format(self):
        lot, inv = _parse_lot_size_and_investment("26 shares (INR 14,950)")
        assert lot == 26
        assert inv == 14950.0

    def test_only_shares(self):
        lot, inv = _parse_lot_size_and_investment("100 shares")
        assert lot == 100
        assert inv is None

    def test_empty(self):
        lot, inv = _parse_lot_size_and_investment("")
        assert lot is None
        assert inv is None

    def test_malformed(self):
        lot, inv = _parse_lot_size_and_investment("nonsense text")
        assert lot is None
        assert inv is None


# ═══════════════════════════════════════════════════════════════════════
# 5. Face value parsing
# ═══════════════════════════════════════════════════════════════════════

class TestParseFaceValue:
    def test_normal(self):
        assert _parse_face_value("INR 2 per share") == 2.0

    def test_ten(self):
        assert _parse_face_value("INR 10 per share") == 10.0

    def test_empty(self):
        assert _parse_face_value("") is None

    def test_malformed(self):
        assert _parse_face_value("no value here") is None


# ═══════════════════════════════════════════════════════════════════════
# 6. Crore value parsing (fresh issue / OFS)
# ═══════════════════════════════════════════════════════════════════════

class TestParseCroreValue:
    def test_normal(self):
        assert _parse_crore_value("INR 250 crore") == 250.0

    def test_range(self):
        result = _parse_crore_value("INR 199.05 – 209.72 crore")
        assert result == 209.72

    def test_nil(self):
        assert _parse_crore_value("Nil") == 0.0

    def test_dash(self):
        assert _parse_crore_value("–") == 0.0

    def test_empty(self):
        assert _parse_crore_value("") is None

    def test_large_number(self):
        assert _parse_crore_value("INR 1,600 crore") == 1600.0


# ═══════════════════════════════════════════════════════════════════════
# 7. Shares offered parsing
# ═══════════════════════════════════════════════════════════════════════

class TestParseSharesOffered:
    def test_normal(self):
        assert _parse_shares_offered("1,18,48,340 shares (INR 199.05 – 209.72 crore)") == 11848340

    def test_short(self):
        assert _parse_shares_offered("77,91,789 shares") == 7791789

    def test_no_shares(self):
        assert _parse_shares_offered("INR 250 crore") is None

    def test_empty(self):
        assert _parse_shares_offered("") is None


# ═══════════════════════════════════════════════════════════════════════
# 8. Detail HTML parsing — full fixture
# ═══════════════════════════════════════════════════════════════════════

DETAIL_HTML_FIXTURE = """
<html><body>
<h2>Test IPO Details</h2>
<table>
  <tr><td>Test IPO Dates</td><td>1 – 3 September 2026</td></tr>
  <tr><td>Test Issue Price</td><td>INR 168 – 177 per share</td></tr>
  <tr><td>Fresh Issue</td><td>INR 250 crore</td></tr>
  <tr><td>Offer For Sale</td><td>1,18,48,340 shares (INR 199.05 – 209.72 crore)</td></tr>
  <tr><td>Total IPO Size</td><td>INR 449.05 – 459.72 crore</td></tr>
  <tr><td>Minimum Bid (Lot Size)</td><td>84 shares (INR 14,868)</td></tr>
  <tr><td>Pre-issue Shares</td><td>8,20,00,000 shares</td></tr>
  <tr><td>Face Value</td><td>INR 2 per share</td></tr>
  <tr><td>Listing On</td><td>NSE, BSE</td></tr>
</table>
<h2>Dates &amp; Listing Performance</h2>
<table>
  <tr><td>IPO Opening Date</td><td>1 September 2026</td></tr>
  <tr><td>IPO Closing Date</td><td>3 September 2026</td></tr>
  <tr><td>Test IPO Listing Date</td><td>8 September 2026</td></tr>
  <tr><td>Opening Price on NSE</td><td>Coming soon</td></tr>
</table>
</body></html>
"""

DETAIL_HTML_MISSING_FIELDS = """
<html><body>
<h2>Minimal IPO Details</h2>
<table>
  <tr><td>Issue Price</td><td>INR 100 per share</td></tr>
  <tr><td>Face Value</td><td>INR 10 per share</td></tr>
</table>
</body></html>
"""

DETAIL_HTML_OFS_NIL = """
<html><body>
<h2>IPO Details</h2>
<table>
  <tr><td>Issue Price</td><td>INR 546 – 575 per share</td></tr>
  <tr><td>Fresh Issue</td><td>INR 680 crore</td></tr>
  <tr><td>Offer For Sale</td><td>Nil</td></tr>
  <tr><td>Minimum Bid (Lot Size)</td><td>26 shares (INR 14,950)</td></tr>
  <tr><td>Face Value</td><td>INR 10 per share</td></tr>
</table>
</body></html>
"""

DETAIL_HTML_MALFORMED = """
<html><body>
<h2>Broken IPO Details</h2>
<table>
  <tr><td>Issue Price</td><td>???</td></tr>
  <tr><td>Fresh Issue</td><td>not a number at all</td></tr>
  <tr><td>Minimum Bid (Lot Size)</td><td>invalid</td></tr>
  <tr><td>Face Value</td><td>broken</td></tr>
</table>
</body></html>
"""


class TestParseDetailHtml:
    def setup_method(self):
        self.provider = LiveIPOProvider()

    def test_normal_detail_page(self):
        result = self.provider._parse_detail_html(DETAIL_HTML_FIXTURE)
        assert result["fresh_issue_crore"] == 250.0
        assert result["ofs_crore"] == 209.72
        assert result["shares_offered"] == 11848340
        assert result["lot_size"] == 84
        assert result["min_investment"] == 14868.0
        assert result["face_value"] == 2.0
        assert result["listing_date"] == "2026-09-08"

    def test_missing_fields(self):
        result = self.provider._parse_detail_html(DETAIL_HTML_MISSING_FIELDS)
        assert result.get("face_value") == 10.0
        assert "fresh_issue_crore" not in result
        assert "ofs_crore" not in result
        assert "lot_size" not in result
        assert "min_investment" not in result
        assert "listing_date" not in result
        assert "shares_offered" not in result

    def test_ofs_nil_is_zero(self):
        """Verify 'Nil' OFS is stored as 0.0, not None."""
        result = self.provider._parse_detail_html(DETAIL_HTML_OFS_NIL)
        assert result["ofs_crore"] == 0.0
        assert result["fresh_issue_crore"] == 680.0
        assert result["lot_size"] == 26
        assert result["min_investment"] == 14950.0
        assert result["face_value"] == 10.0

    def test_malformed_fields(self):
        """Verify malformed values don't crash the parser."""
        result = self.provider._parse_detail_html(DETAIL_HTML_MALFORMED)
        assert "fresh_issue_crore" not in result
        assert "lot_size" not in result
        assert "face_value" not in result

    def test_empty_html(self):
        result = self.provider._parse_detail_html("<html><body></body></html>")
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════
# 9. Calendar + detail merge
# ═══════════════════════════════════════════════════════════════════════

class TestMergeRecords:
    def test_detail_enriches_calendar(self):
        calendar = {
            "name": "Test Co",
            "slug": "test-co",
            "status": "Upcoming",
            "detail_url": "http://example.com",
            "dates": "1 – 3 Sep",
            "price_low": 100.0,
            "price_high": 120.0,
            "issue_size_crore": 500.0,
        }
        detail = {
            "lot_size": 84,
            "face_value": 2.0,
            "fresh_issue_crore": 250.0,
        }
        merged = LiveIPOProvider._merge_records(calendar, detail)
        # Calendar fields preserved
        assert merged["name"] == "Test Co"
        assert merged["price_low"] == 100.0
        # Detail fields added
        assert merged["lot_size"] == 84
        assert merged["face_value"] == 2.0
        assert merged["fresh_issue_crore"] == 250.0

    def test_calendar_value_not_overwritten_by_none(self):
        """Detail should never replace a valid calendar value with None."""
        calendar = {"issue_size_crore": 680.0, "name": "X", "slug": "x"}
        detail = {}  # no issue_size_crore override
        merged = LiveIPOProvider._merge_records(calendar, detail)
        assert merged["issue_size_crore"] == 680.0

    def test_detail_overrides_calendar_value(self):
        """When detail provides a valid value, it should override."""
        calendar = {"fresh_issue_crore": 0.0, "name": "X"}
        detail = {"fresh_issue_crore": 250.0}
        merged = LiveIPOProvider._merge_records(calendar, detail)
        assert merged["fresh_issue_crore"] == 250.0

    def test_zero_ofs_is_preserved(self):
        """A genuine 0 from detail should replace the calendar default."""
        calendar = {"name": "X"}
        detail = {"ofs_crore": 0.0}
        merged = LiveIPOProvider._merge_records(calendar, detail)
        assert merged["ofs_crore"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 10. Normalization
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeRecord:
    def setup_method(self):
        self.provider = LiveIPOProvider()

    def _make_raw(self, **overrides) -> dict:
        base = {
            "name": "Test Company",
            "slug": "test-company",
            "status": "Ongoing",
            "detail_url": "http://example.com/test",
            "dates": "1 – 3 Sep",
            "price_low": 100.0,
            "price_high": 120.0,
            "issue_size_crore": 500.0,
        }
        base.update(overrides)
        return base

    def test_basic_normalization(self):
        record = self.provider._normalize_record(self._make_raw())
        assert isinstance(record, NormalizedIPO)
        assert record.name == "Test Company"
        assert record.slug == "test-company"
        assert record.status == "Ongoing"
        assert record.sector is None
        assert record.data_source == "live"
        assert record.source_url == "http://example.com/test"

    def test_enriched_normalization(self):
        raw = self._make_raw(
            lot_size=84,
            min_investment=14868.0,
            face_value=2.0,
            shares_offered=11848340,
            fresh_issue_crore=250.0,
            ofs_crore=209.72,
            listing_date="2026-09-08",
        )
        record = self.provider._normalize_record(raw)
        assert record.lot_size == 84
        assert record.min_investment == 14868.0
        assert record.face_value == 2.0
        assert record.shares_offered == 11848340
        assert record.fresh_issue_crore == 250.0
        assert record.ofs_crore == 209.72
        assert record.listing_date == "2026-09-08"

    def test_missing_enrichment_fields(self):
        record = self.provider._normalize_record(self._make_raw())
        assert record.lot_size is None
        assert record.min_investment is None
        assert record.face_value is None
        assert record.shares_offered is None
        assert record.listing_date is None

    def test_malformed_dates(self):
        record = self.provider._normalize_record(self._make_raw(dates="Invalid"))
        assert record.open_date is None
        assert record.close_date is None

    def test_all_canonical_statuses(self):
        for status in ["Upcoming", "Ongoing", "Closed", "Listed"]:
            record = self.provider._normalize_record(self._make_raw(status=status))
            assert record.status == status

    def test_invalid_status_rejected(self):
        record = self.provider._normalize_record(self._make_raw(status="Open"))
        assert record is None  # Should fail validation and return None

    def test_fresh_issue_and_ofs_nullability(self):
        """Prove that missing values remain None and genuine zeros remain 0."""
        # 1. Missing values
        raw_missing = self._make_raw()
        raw_missing.pop("fresh_issue_crore", None)
        raw_missing.pop("ofs_crore", None)
        record_missing = self.provider._normalize_record(raw_missing)
        assert record_missing.fresh_issue_crore is None
        assert record_missing.ofs_crore is None

        # 2. Genuine zero values
        raw_zero = self._make_raw(fresh_issue_crore=0.0, ofs_crore=0.0)
        record_zero = self.provider._normalize_record(raw_zero)
        assert record_zero.fresh_issue_crore == 0.0
        assert record_zero.ofs_crore == 0.0

# ═══════════════════════════════════════════════════════════════════════
# 11. Multiple detail pages — one malformed doesn't break others
# ═══════════════════════════════════════════════════════════════════════

class TestBatchResilience:
    def test_one_bad_detail_doesnt_break_batch(self):
        """Verify that a malformed detail page doesn't prevent normalization."""
        provider = LiveIPOProvider()

        raw_records = [
            {
                "name": "Good IPO",
                "slug": "good-ipo",
                "status": "Upcoming",
                "detail_url": "",
                "dates": "1 – 3 Sep",
                "price_low": 100.0,
                "price_high": 120.0,
                "issue_size_crore": 500.0,
            },
            {
                "name": "Bad IPO",
                "slug": "bad-ipo",
                "status": "InvalidStatus",
                "detail_url": "",
                "dates": "1 – 3 Sep",
                "price_low": 100.0,
                "price_high": 120.0,
                "issue_size_crore": 500.0,
            },
        ]

        results = []
        for raw in raw_records:
            normalized = provider._normalize_record(raw)
            if normalized:
                results.append(normalized)

        assert len(results) == 1
        assert results[0].name == "Good IPO"


# ═══════════════════════════════════════════════════════════════════════
# 11. Sector extraction from description
# ═══════════════════════════════════════════════════════════════════════

class TestExtractSector:
    def test_extract_real_estate(self):
        from app.providers.live import _extract_sector_from_text
        assert _extract_sector_from_text("Kerala-focused residential real estate developer engaged in planning...") == "Real Estate"

    def test_extract_specialty_chemicals(self):
        from app.providers.live import _extract_sector_from_text
        assert _extract_sector_from_text("A leading specialty chemicals manufacturer...") == "Specialty Chemicals"

    def test_extract_renewable_energy(self):
        from app.providers.live import _extract_sector_from_text
        assert _extract_sector_from_text("Manufacturer of solar energy and power transmission...") == "Renewable Energy"

    def test_unknown_returns_none(self):
        from app.providers.live import _extract_sector_from_text
        assert _extract_sector_from_text("A social enterprise providing community benefits...") is None
        assert _extract_sector_from_text("") is None
        assert _extract_sector_from_text(None) is None
