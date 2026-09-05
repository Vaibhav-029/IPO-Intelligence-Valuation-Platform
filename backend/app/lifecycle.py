"""Single source of truth for IPO lifecycle status computation.

This module contains the AUTHORITATIVE lifecycle logic used by:
  - seed.py (initial data loading)
  - services/sync.py (live data sync)
  - Any future code that needs to determine IPO status

The rule is absolute: when lifecycle dates are available, status is
DERIVED from dates. Static JSON status strings are NEVER trusted
when dates exist.

Lifecycle rules:
  today < open_date                    → Upcoming
  open_date <= today <= close_date     → Ongoing
  close_date < today < listing_date    → Closed
  today >= listing_date                → Listed

When dates are missing:
  - open_date falls back to issue_date (they are often the same)
  - If no dates are available at all, return "Unresolved"
"""
from __future__ import annotations

from datetime import date


def compute_lifecycle_status(
    *,
    open_date: date | None = None,
    close_date: date | None = None,
    listing_date: date | None = None,
    issue_date: date | None = None,
    static_status: str | None = None,
    reference_date: date | None = None,
) -> str:
    """Compute the authoritative lifecycle status from dates.

    Args:
        open_date: Subscription open date.
        close_date: Subscription close date.
        listing_date: Exchange listing date.
        issue_date: Legacy issue date — used as fallback for open_date.
        static_status: The provider's claimed status. Used ONLY when
                       no dates are available at all.
        reference_date: Override for 'today' — used in testing.

    Returns:
        One of: "Upcoming", "Ongoing", "Closed", "Listed", "Unresolved".
    """
    today = reference_date or date.today()

    # Resolve effective open date (open_date takes priority, issue_date as fallback)
    effective_open = open_date or issue_date

    # ── Rule 1: Listed — listing_date is the strongest signal ──────
    if listing_date and today >= listing_date:
        return "Listed"

    # ── Rule 2: Closed — past close_date but not yet listed ────────
    if close_date and today > close_date:
        return "Closed"

    # ── Rule 3: Ongoing — between open and close ──────────────────
    if effective_open and close_date and effective_open <= today <= close_date:
        return "Ongoing"

    # ── Rule 4: Upcoming — before open date ───────────────────────
    if effective_open and today < effective_open:
        return "Upcoming"

    # ── Rule 5: Partial dates — infer what we can ─────────────────
    # Has listing_date in the future but no open/close → Upcoming
    if listing_date and today < listing_date and not effective_open:
        return "Upcoming"

    # Has open_date but no close_date → if today >= open_date, treat as Ongoing
    if effective_open and not close_date and today >= effective_open:
        # Without a close_date we can't be sure, but subscription has started
        return "Ongoing"

    # ── Fallback: no usable dates ─────────────────────────────────
    if static_status and static_status in {"Upcoming", "Ongoing", "Closed", "Listed"}:
        return static_status

    return "Unresolved"


def parse_date_safe(date_str: str | None) -> date | None:
    """Safely parse a YYYY-MM-DD string. Returns None on any failure."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(str(date_str))
    except (ValueError, TypeError):
        return None
