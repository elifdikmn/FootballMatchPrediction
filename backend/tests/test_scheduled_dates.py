import math
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from match_repository import scheduled_rows, score_value
from models import Base, Fixture, FixtureSyncState


class ScheduledDateTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add_all([
            Fixture(FixtureID=1, Date="2026-09-15", League="E0", Status="FINISHED"),
            Fixture(FixtureID=2, Date="2026-09-17", League="E0", Status="SCHEDULED"),
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def ids(self, selected_date=None):
        return [fixture.FixtureID for fixture, _ in scheduled_rows(
            self.session, {"E0"}, selected_date
        )]

    def test_past_day_includes_saved_finished_match(self):
        self.assertEqual(self.ids("2026-09-15"), [1])

    def test_future_empty_and_default_queries(self):
        self.assertEqual(self.ids("2026-09-17"), [2])
        self.assertEqual(self.ids("2026-09-16"), [])
        self.assertEqual(self.ids(), [2])

    def test_score_conversion_preserves_zero_and_rejects_invalid_values(self):
        self.assertEqual(score_value(0.0), 0)
        self.assertEqual(score_value(2.0), 2)
        for value in (None, math.nan, math.inf, -1, 1.5):
            self.assertIsNone(score_value(value))

    def test_duplicate_provider_match_prefers_synced_finished_fixture(self):
        self.session.add_all([
            Fixture(
                FixtureID=3, Date="2026-09-18", League="E0",
                HomeTeam="Málaga CF", AwayTeam="Villarreal", Status="FINISHED",
            ),
            Fixture(
                FixtureID=2_000_000_003, Date="2026-09-18", League="E0",
                HomeTeam="Malaga", AwayTeam="Villarreal CF", Status="LIVE",
            ),
            FixtureSyncState(
                FixtureID=3, provider="football-data.org", provider_fixture_id="3",
                kickoff_utc="2026-09-18T18:00:00Z", source_hash="x",
                needs_prediction=False, synced_at="2026-09-18T20:00:00Z",
            ),
        ])
        self.session.commit()

        self.assertEqual(self.ids("2026-09-18"), [3])


if __name__ == "__main__":
    unittest.main()
