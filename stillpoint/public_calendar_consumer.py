"""Read-only ingestion boundary for the *public* Canonical Core calendar-day.v2.

This is a contract shape/consistency check, not a second calendar engine, a
publication signature verifier, or authorization to perform an external action.
It deliberately imports no private integration, Core implementation, or SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class PublicCalendarContractError(ValueError):
    """Unusable or nonselected public Core calendar observation."""


# Public Canonical Core common grid, *not* the separate sacred 30-30-31 pattern.
_COMMON_MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 30)
_WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


@dataclass(frozen=True)
class PublicCalendarObservation:
    """Immutable summary of a validated public payload; confers no authority."""

    year: int
    ordinal: int
    month: int
    day: int
    weekday: str
    calendar_address: str
    publication_digest: str
    selection_source: str
    usage_scope: str = "read-only-public-contract-observation"


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicCalendarContractError(f"{label} must be a mapping")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:  # bool is not a valid year/ordinal/count
        raise PublicCalendarContractError(f"{label} must be an integer")
    return value


def _required(condition: bool, message: str) -> None:
    if not condition:
        raise PublicCalendarContractError(message)


def inspect_public_calendar_day(payload: Mapping[str, Any]) -> PublicCalendarObservation:
    """Validate a serialized Core v2 day for *read-only*, nonauthoritative use.

    The caller must establish provenance separately (e.g., trusted pinned Core
    publication). Even a well-formed document may be forged; checking its
    metadata is *not* authenticating a publication or verifying its signature.
    """
    obj = _object(payload, "payload")
    _required(obj.get("schema") == "stillpoint.calendar-day.v2", "unsupported calendar schema")
    _required(obj.get("authority") == "read-only-calendar-law", "unsupported read-only surface")

    bounds = _object(obj.get("map"), "map")
    expected = {
        "first_year": 2026, "last_year": 2075, "year_count": 50,
        "year_days": 364, "weeks_per_year": 52, "total_days": 18200,
    }
    for key, value in expected.items():
        _required(_integer(bounds.get(key), f"map.{key}") == value, f"inconsistent map.{key}")
    _required(bounds.get("december_31_exists") is False, "Dec 31 is not published")
    _required(bounds.get("day001_weekday") == "Thursday", "unexpected common weekday anchor")

    date = _object(obj.get("common_date"), "common_date")
    year = _integer(date.get("year"), "common_date.year")
    ordinal = _integer(date.get("ordinal"), "common_date.ordinal")
    month = _integer(date.get("month"), "common_date.month")
    day = _integer(date.get("day"), "common_date.day")
    _required(2026 <= year <= 2075, "year outside finite published map")
    _required(1 <= ordinal <= 364, "ordinal outside 364-day year")
    _required(1 <= month <= 12, "invalid common month")
    _required(1 <= day <= _COMMON_MONTH_LENGTHS[month - 1], "invalid common day")
    _required(ordinal == sum(_COMMON_MONTH_LENGTHS[:month - 1]) + day, "inconsistent ordinal")
    _required(_integer(date.get("week"), "common_date.week") == (ordinal - 1) // 7 + 1, "inconsistent week")
    _required(_integer(date.get("day_in_week"), "common_date.day_in_week") == (ordinal - 1) % 7 + 1, "inconsistent day_in_week")
    weekday = _WEEKDAYS[(_WEEKDAYS.index("Thursday") + ordinal - 1) % 7]
    _required(date.get("weekday") == weekday, "inconsistent common weekday")
    address = f"Y_{year}-{ordinal:03d}"
    _required(obj.get("calendar_address") == address, "inconsistent calendar address")

    publication = _object(obj.get("publication"), "publication")
    _required(publication.get("authority_status") == "enacted", "publication metadata is not selected")
    digest = publication.get("digest")
    _required(isinstance(digest, str) and bool(digest.strip()), "publication digest is missing")

    civil = _object(obj.get("civil_window"), "civil_window")
    _required(civil.get("role") == "external-translation-only", "civil window cannot govern common grid")
    _required(civil.get("grid_authority") is False, "civil window attempts grid authority")
    jubilee = _object(obj.get("jubilee"), "jubilee")
    cfg = _object(jubilee.get("configuration"), "jubilee.configuration")
    _required(cfg.get("selection_source") == "declared-project-profile", "nonselected Jubilee calculation")
    _required(cfg.get("selected_policy_applies") is True, "nonselected Jubilee calculation")
    _required(cfg.get("epoch_common_year") == 2027, "unexpected Jubilee epoch")
    _required(cfg.get("rollover_rule") == "overlap-49", "unexpected Jubilee rollover")
    _required(cfg.get("authority_scope") == "calculation-inputs-only", "cycle data cannot grant action authority")

    return PublicCalendarObservation(
        year=year, ordinal=ordinal, month=month, day=day,
        weekday=weekday, calendar_address=address, publication_digest=digest,
        selection_source="declared-project-profile",
    )
