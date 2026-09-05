"""Unit tests for the lifecycle status computation module.

Tests the SINGLE SOURCE OF TRUTH lifecycle logic:
  today < open_date                    → Upcoming
  open_date <= today <= close_date     → Ongoing
  close_date < today < listing_date    → Closed
  today >= listing_date                → Listed

Each test uses a fixed reference_date to make tests deterministic.
"""
import pytest
from datetime import date, timedelta
from app.lifecycle import compute_lifecycle_status, parse_date_safe


TODAY = date(2026, 9, 5)  # Fixed reference date for all tests


class TestComputeLifecycleStatus:
    """Core lifecycle computation tests."""

    def test_upcoming_before_open_date(self):
        """IPO with open_date in the future is Upcoming."""
        status = compute_lifecycle_status(
            open_date=TODAY + timedelta(days=5),
            close_date=TODAY + timedelta(days=8),
            listing_date=TODAY + timedelta(days=15),
            reference_date=TODAY,
        )
        assert status == "Upcoming"

    def test_upcoming_before_open_date_no_listing(self):
        """IPO with open_date in the future but no listing_date is Upcoming."""
        status = compute_lifecycle_status(
            open_date=TODAY + timedelta(days=5),
            close_date=TODAY + timedelta(days=8),
            reference_date=TODAY,
        )
        assert status == "Upcoming"

    def test_ongoing_on_open_date(self):
        """IPO on its open_date is Ongoing (boundary: open_date == today)."""
        status = compute_lifecycle_status(
            open_date=TODAY,
            close_date=TODAY + timedelta(days=3),
            reference_date=TODAY,
        )
        assert status == "Ongoing"

    def test_ongoing_between_open_and_close(self):
        """IPO between open and close dates is Ongoing."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=1),
            close_date=TODAY + timedelta(days=2),
            reference_date=TODAY,
        )
        assert status == "Ongoing"

    def test_ongoing_on_close_date(self):
        """IPO on its close_date is Ongoing (boundary: close_date == today)."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=3),
            close_date=TODAY,
            reference_date=TODAY,
        )
        assert status == "Ongoing"

    def test_closed_after_close_date(self):
        """IPO after close_date but before listing_date is Closed."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=10),
            close_date=TODAY - timedelta(days=7),
            listing_date=TODAY + timedelta(days=3),
            reference_date=TODAY,
        )
        assert status == "Closed"

    def test_closed_after_close_no_listing(self):
        """IPO after close_date with no listing_date is Closed."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=10),
            close_date=TODAY - timedelta(days=7),
            reference_date=TODAY,
        )
        assert status == "Closed"

    def test_listed_on_listing_date(self):
        """IPO on listing_date is Listed (boundary: listing_date == today)."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=15),
            close_date=TODAY - timedelta(days=12),
            listing_date=TODAY,
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_listed_after_listing_date(self):
        """IPO well after listing_date is Listed."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=365),
            close_date=TODAY - timedelta(days=362),
            listing_date=TODAY - timedelta(days=355),
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_listed_overrides_static_ongoing(self):
        """Even if static_status says 'Ongoing', listing_date wins → Listed."""
        status = compute_lifecycle_status(
            open_date=date(2025, 1, 20),
            close_date=date(2025, 1, 22),
            listing_date=date(2025, 1, 30),
            static_status="Ongoing",
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_listed_overrides_static_upcoming(self):
        """Even if static_status says 'Upcoming', listing_date wins → Listed."""
        status = compute_lifecycle_status(
            open_date=date(2025, 8, 25),
            close_date=date(2025, 8, 28),
            listing_date=date(2025, 9, 2),
            static_status="Upcoming",
            reference_date=TODAY,
        )
        assert status == "Listed"


class TestSeedCompanyLifecycleExamples:
    """Test cases modeled on specific companies from the user's reports.
    
    These verify that real-world seed data produces correct statuses.
    """

    def test_stallion_india_is_listed(self):
        """Stallion India listed 2025-01-23 → Listed in Sep 2026."""
        status = compute_lifecycle_status(
            issue_date=date(2025, 1, 20),
            listing_date=date(2025, 1, 23),
            static_status="Ongoing",  # the BAD static status
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_ventive_hospitality_is_listed(self):
        """Ventive Hospitality listed 2024-12-30 → Listed in Sep 2026."""
        status = compute_lifecycle_status(
            issue_date=date(2024, 12, 20),
            listing_date=date(2024, 12, 30),
            static_status="Ongoing",  # the BAD static status
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_hexaware_is_listed(self):
        """Hexaware listed 2025-02-28 → Listed in Sep 2026."""
        status = compute_lifecycle_status(
            issue_date=date(2025, 2, 12),
            listing_date=date(2025, 2, 28),
            static_status="Upcoming",  # the BAD static status
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_swiggy_is_listed(self):
        """Swiggy listed 2024-11-13 → Listed in Sep 2026."""
        status = compute_lifecycle_status(
            issue_date=date(2024, 11, 6),
            listing_date=date(2024, 11, 13),
            static_status="Listed",  # correct in seed but we don't trust it
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_tata_technologies_is_listed(self):
        """Tata Technologies listed 2023-11-30 → Listed in Sep 2026."""
        status = compute_lifecycle_status(
            issue_date=date(2023, 11, 22),
            listing_date=date(2023, 11, 30),
            static_status="Listed",
            reference_date=TODAY,
        )
        assert status == "Listed"


class TestIssueDateFallback:
    """Test that issue_date is correctly used as fallback for open_date."""

    def test_issue_date_fallback_for_upcoming(self):
        """When only issue_date (no open_date) and it's in the future → Upcoming."""
        status = compute_lifecycle_status(
            issue_date=TODAY + timedelta(days=10),
            reference_date=TODAY,
        )
        assert status == "Upcoming"

    def test_issue_date_fallback_for_listed(self):
        """When only issue_date and listing_date, both past → Listed."""
        status = compute_lifecycle_status(
            issue_date=date(2023, 11, 22),
            listing_date=date(2023, 11, 30),
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_open_date_takes_priority_over_issue_date(self):
        """open_date is used instead of issue_date when both exist."""
        # open_date is in the future but issue_date is in the past
        status = compute_lifecycle_status(
            open_date=TODAY + timedelta(days=5),
            close_date=TODAY + timedelta(days=8),
            issue_date=TODAY - timedelta(days=10),  # should be ignored
            reference_date=TODAY,
        )
        assert status == "Upcoming"


class TestMissingDates:
    """Test behavior when dates are partially or fully missing."""

    def test_no_dates_uses_static_status(self):
        """When no dates are available, fall back to static_status."""
        status = compute_lifecycle_status(
            static_status="Upcoming",
            reference_date=TODAY,
        )
        assert status == "Upcoming"

    def test_no_dates_no_static_returns_unresolved(self):
        """When absolutely nothing is available, return Unresolved."""
        status = compute_lifecycle_status(reference_date=TODAY)
        assert status == "Unresolved"

    def test_no_dates_invalid_static_returns_unresolved(self):
        """When static_status is invalid, return Unresolved."""
        status = compute_lifecycle_status(
            static_status="SomeInvalidStatus",
            reference_date=TODAY,
        )
        assert status == "Unresolved"

    def test_only_listing_date_in_future(self):
        """Only listing_date set, in the future → Upcoming."""
        status = compute_lifecycle_status(
            listing_date=TODAY + timedelta(days=30),
            reference_date=TODAY,
        )
        assert status == "Upcoming"

    def test_only_listing_date_in_past(self):
        """Only listing_date set, in the past → Listed."""
        status = compute_lifecycle_status(
            listing_date=TODAY - timedelta(days=30),
            reference_date=TODAY,
        )
        assert status == "Listed"

    def test_open_date_past_no_close_date(self):
        """open_date in past, no close_date → Ongoing (subscription has started)."""
        status = compute_lifecycle_status(
            open_date=TODAY - timedelta(days=1),
            reference_date=TODAY,
        )
        assert status == "Ongoing"


class TestParseDateSafe:
    """Test the safe date parser."""

    def test_valid_date(self):
        assert parse_date_safe("2026-09-05") == date(2026, 9, 5)

    def test_none_input(self):
        assert parse_date_safe(None) is None

    def test_empty_string(self):
        assert parse_date_safe("") is None

    def test_invalid_format(self):
        assert parse_date_safe("not-a-date") is None

    def test_invalid_date(self):
        assert parse_date_safe("2026-13-45") is None
