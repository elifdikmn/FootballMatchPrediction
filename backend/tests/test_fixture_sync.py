from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fixture_sync import (
    ExternalFixture,
    parse_espn_matches,
    parse_football_data_matches,
    parse_openfootball_matches,
    upsert_fixtures,
)
from models import Base, Fixture, FixtureSyncState


class FixtureSyncTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_football_data_names_status_and_score_are_normalized(self):
        payload = {"matches": [{
            "id": 42,
            "utcDate": "2026-09-20T15:00:00Z",
            "status": "FINISHED",
            "lastUpdated": "2026-09-20T17:00:00Z",
            "homeTeam": {"name": "Manchester City FC"},
            "awayTeam": {"name": "Arsenal FC"},
            "score": {"fullTime": {"home": 2, "away": 1}},
        }]}
        fixture = parse_football_data_matches(payload, "E0")[0]
        self.assertEqual((fixture.home_team, fixture.away_team), ("Man City", "Arsenal"))
        self.assertEqual((fixture.status, fixture.home_goals, fixture.away_goals), ("FINISHED", 2, 1))

    def test_espn_super_lig_response_is_normalized(self):
        payload = {"events": [{
            "id": "99",
            "date": "2026-09-20T17:00Z",
            "competitions": [{
                "status": {"type": {
                    "name": "STATUS_SCHEDULED",
                    "state": "pre",
                    "completed": False,
                }},
                "competitors": [
                    {"homeAway": "home", "score": "0", "team": {"displayName": "Fenerbahçe"}},
                    {"homeAway": "away", "score": "0", "team": {"displayName": "Beşiktaş"}},
                ],
            }],
        }]}
        fixture = parse_espn_matches(payload)[0]
        self.assertEqual((fixture.league, fixture.status), ("T1", "SCHEDULED"))
        self.assertEqual((fixture.home_team, fixture.away_team), ("Fenerbahce", "Besiktas"))

    def test_openfootball_ids_are_stable_and_future_scores_are_ignored(self):
        payload = {"matches": [{
            "round": "1. Round",
            "date": "2026-09-20",
            "time": "20:30",
            "team1": "Fenerbahçe",
            "team2": "Galatasaray",
            "score": [0, 0],
        }]}
        first = parse_openfootball_matches(payload, "2026-27", date(2026, 9, 16))[0]
        second = parse_openfootball_matches(payload, "2026-27", date(2026, 9, 16))[0]
        self.assertEqual(first.fixture_id, second.fixture_id)
        self.assertEqual(first.status, "SCHEDULED")
        self.assertIsNone(first.home_goals)

    def test_openfootball_past_match_without_score_is_not_scheduled(self):
        payload = {"matches": [{
            "round": "1. Round",
            "date": "2026-09-10",
            "time": "20:30",
            "team1": "Fenerbahçe",
            "team2": "Galatasaray",
        }]}
        fixture = parse_openfootball_matches(payload, "2026-27", date(2026, 9, 16))[0]
        self.assertEqual(fixture.status, "POSTPONED")
        self.assertIsNone(fixture.home_goals)

    def test_upsert_is_idempotent_and_marks_schedule_changes_for_prediction(self):
        payload = {"matches": [{
            "id": 77,
            "utcDate": "2026-09-20T15:00:00Z",
            "status": "TIMED",
            "homeTeam": {"name": "Chelsea FC"},
            "awayTeam": {"name": "Arsenal FC"},
            "score": {"fullTime": {"home": None, "away": None}},
        }]}
        fixture = parse_football_data_matches(payload, "E0")[0]
        self.assertEqual(upsert_fixtures([fixture], self.session), (1, 0))
        state = self.session.get(FixtureSyncState, 77)
        self.assertTrue(state.needs_prediction)

        state.needs_prediction = False
        self.session.get(Fixture, 77).Predicted_Label = "Home Win"
        self.session.commit()
        self.assertEqual(upsert_fixtures([fixture], self.session), (0, 0))
        self.assertFalse(state.needs_prediction)

        payload["matches"][0]["utcDate"] = "2026-09-20T17:00:00Z"
        changed = parse_football_data_matches(payload, "E0")[0]
        self.assertEqual(upsert_fixtures([changed], self.session), (0, 1))
        self.assertTrue(state.needs_prediction)
        self.assertEqual(self.session.get(Fixture, 77).Date, "2026-09-20")

    def test_provider_switch_reuses_the_existing_fixture(self):
        first = ExternalFixture(
            provider="espn",
            provider_fixture_id="100",
            fixture_id=100,
            league="T1",
            kickoff_utc="2026-09-20T17:00:00Z",
            home_team="Galatasaray",
            away_team="Fenerbahce",
            status="SCHEDULED",
        )
        replacement = ExternalFixture(
            provider="openfootball",
            provider_fixture_id="1500000100",
            fixture_id=1_500_000_100,
            league="T1",
            kickoff_utc="2026-09-20T17:00:00Z",
            home_team="Galatasaray",
            away_team="Fenerbahce",
            status="SCHEDULED",
        )
        upsert_fixtures([first], self.session)
        upsert_fixtures([replacement], self.session)
        self.assertEqual(self.session.query(Fixture).count(), 1)
        state = self.session.get(FixtureSyncState, 100)
        self.assertEqual((state.provider, state.provider_fixture_id), (
            "openfootball", "1500000100"
        ))


if __name__ == "__main__":
    unittest.main()
