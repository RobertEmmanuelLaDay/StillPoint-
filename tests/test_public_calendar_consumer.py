"""Public-source consumer regressions; fixtures are shapes, not private system code."""

from __future__ import annotations

from copy import deepcopy
import unittest

from stillpoint.public_calendar_consumer import (
    PublicCalendarContractError,
    PublicCalendarObservation,
    inspect_public_calendar_day,
)


MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 30)
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def public_fixture(year=2026, ordinal=1):
    remaining = ordinal
    month, day = None, None
    for i, length in enumerate(MONTH_LENGTHS, 1):
        if remaining <= length:
            month, day = i, remaining
            break
        remaining -= length
    weekday = WEEKDAYS[(WEEKDAYS.index("Thursday") + ordinal - 1) % 7]
    return {
        "schema": "stillpoint.calendar-day.v2",
        "authority": "read-only-calendar-law",
        "calendar_address": f"Y_{year}-{ordinal:03d}",
        "map": {
            "first_year": 2026, "last_year": 2075, "year_count": 50,
            "year_days": 364, "weeks_per_year": 52, "total_days": 18200,
            "day001_weekday": "Thursday", "december_31_exists": False,
        },
        "common_date": {
            "year": year, "ordinal": ordinal, "month": month, "day": day,
            "week": (ordinal - 1) // 7 + 1,
            "day_in_week": (ordinal - 1) % 7 + 1,
            "weekday": weekday,
        },
        "civil_window": {"role": "external-translation-only", "grid_authority": False},
        "publication": {"authority_status": "enacted", "digest": "fixture-digest-not-a-signature"},
        "jubilee": {"configuration": {
            "selection_source": "declared-project-profile",
            "selected_policy_applies": True,
            "epoch_common_year": 2027, "rollover_rule": "overlap-49",
            "authority_scope": "calculation-inputs-only",
        }},
    }


class PublicCalendarConsumerTests(unittest.TestCase):
    def test_first_and_last_published_days_accept_read_only(self):
        for year, ordinal in ((2026, 1), (2075, 364)):
            with self.subTest(year=year, ordinal=ordinal):
                data = public_fixture(year, ordinal)
                before = deepcopy(data)
                result = inspect_public_calendar_day(data)
                self.assertIsInstance(result, PublicCalendarObservation)
                self.assertEqual((result.year, result.ordinal), (year, ordinal))
                self.assertEqual(result.usage_scope, "read-only-public-contract-observation")
                self.assertEqual(data, before)
        self.assertEqual(inspect_public_calendar_day(public_fixture(2075, 364)).day, 30)

    def test_reject_older_schema(self):
        data = public_fixture(); data["schema"] = "stillpoint.calendar-day.v1"
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_reject_unpublished_years(self):
        for year in (2025, 2076):
            with self.subTest(year=year):
                with self.assertRaises(PublicCalendarContractError):
                    inspect_public_calendar_day(public_fixture(year, 1))

    def test_reject_invalid_ordinal_and_december_31(self):
        data = public_fixture()
        data["common_date"].update(ordinal=365, month=12, day=31, week=53)
        data["calendar_address"] = "Y_2026-365"
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_reject_inconsistent_calendar_address(self):
        data = public_fixture(); data["calendar_address"] = "Y_2027-001"
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_reject_inconsistent_common_weekday(self):
        data = public_fixture(); data["common_date"]["weekday"] = "Friday"
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_reject_alternative_jubilee_as_selected(self):
        data = public_fixture()
        data["jubilee"]["configuration"].update(
            selection_source="explicit-call-configuration",
            selected_policy_applies=False,
            rollover_rule="standalone-50",
        )
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_reject_publication_metadata_without_digest(self):
        data = public_fixture(); data["publication"]["digest"] = ""
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_civil_translation_cannot_be_grid_authority(self):
        data = public_fixture(); data["civil_window"]["grid_authority"] = True
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_bool_is_not_valid_integer(self):
        data = public_fixture(); data["common_date"]["ordinal"] = True
        with self.assertRaises(PublicCalendarContractError): inspect_public_calendar_day(data)

    def test_malformed_payload_fails_closed(self):
        for malformed in (None, {}, {"schema": "stillpoint.calendar-day.v2"}):
            with self.subTest(payload=malformed):
                with self.assertRaises(PublicCalendarContractError):
                    inspect_public_calendar_day(malformed)


if __name__ == "__main__":
    unittest.main()
