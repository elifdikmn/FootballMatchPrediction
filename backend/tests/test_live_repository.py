import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from live_repository import persist_live_matches
from models import Base, Fixture, FixtureSyncState, LiveMatchState, PredictionSnapshot


class LiveRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.db.add(Fixture(
            FixtureID=12,
            Date="2026-09-20",
            League="E0",
            HomeTeam="Man City",
            AwayTeam="Arsenal",
            Status="SCHEDULED",
            Predicted_Label="Home Win",
            HomeWinPct=55,
            DrawPct=25,
            AwayWinPct=20,
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_live_provider_id_is_reconciled_without_overwriting_pre_match(self):
        output = persist_live_matches(self.db, [{
            "fixture_id": 9988,
            "date": "2026-09-20",
            "home_team": "Manchester City",
            "away_team": "Arsenal FC",
            "league": "E0",
            "score": "1 - 0",
            "elapsed": 33,
            "status": "LIVE",
            "predicted_label": "Home Win",
            "home_win_pct": 72,
            "draw_pct": 18,
            "away_win_pct": 10,
        }])

        self.assertEqual(output[0]["fixture_id"], 12)
        self.assertEqual(output[0]["provider_fixture_id"], 9988)
        state = self.db.get(LiveMatchState, 12)
        self.assertEqual((state.elapsed, state.score), (33, "1 - 0"))
        fixture = self.db.get(Fixture, 12)
        self.assertEqual((fixture.HomeWinPct, fixture.DrawPct, fixture.AwayWinPct), (55, 25, 20))
        live = self.db.query(PredictionSnapshot).filter_by(prediction_type="LIVE").one()
        self.assertEqual((live.home_win_pct, live.version), (72, 1))

    def test_accent_and_club_suffix_match_existing_fixture(self):
        self.db.add(Fixture(
            FixtureID=13, Date="2026-09-20", League="SP1",
            HomeTeam="Málaga CF", AwayTeam="Villarreal", Status="SCHEDULED",
        ))
        self.db.commit()

        output = persist_live_matches(self.db, [{
            "fixture_id": 8877, "date": "2026-09-20", "league": "SP1",
            "home_team": "Malaga", "away_team": "Villarreal CF",
            "score": "1 - 2", "elapsed": 70, "status": "LIVE",
        }])

        self.assertEqual(output[0]["fixture_id"], 13)
        self.assertEqual(self.db.query(Fixture).filter_by(League="SP1").count(), 1)

    def test_stale_live_duplicate_does_not_override_finished_result(self):
        canonical = Fixture(
            FixtureID=13, Date="2026-09-20", League="SP1",
            HomeTeam="Málaga CF", AwayTeam="Villarreal", Status="FINISHED",
            HomeGoals=1, AwayGoals=3,
        )
        duplicate = Fixture(
            FixtureID=2_000_000_001, Date="2026-09-20", League="SP1",
            HomeTeam="Malaga", AwayTeam="Villarreal", Status="LIVE",
            HomeGoals=1, AwayGoals=2,
        )
        self.db.add_all([canonical, duplicate])
        self.db.add(FixtureSyncState(
            FixtureID=13, provider="football-data.org", provider_fixture_id="13",
            kickoff_utc="2026-09-20T18:00:00Z", source_hash="x",
            needs_prediction=False, synced_at="2026-09-20T20:00:00Z",
        ))
        self.db.add(LiveMatchState(
            FixtureID=duplicate.FixtureID, provider_fixture_id="8877", league="SP1",
            score="1 - 2", elapsed=70, status="LIVE", updated_at="old",
        ))
        self.db.commit()

        output = persist_live_matches(self.db, [{
            "fixture_id": 8877, "date": "2026-09-20", "league": "SP1",
            "home_team": "Malaga", "away_team": "Villarreal",
            "score": "1 - 2", "elapsed": 71, "status": "LIVE",
        }])

        self.assertEqual(output, [])
        self.assertEqual((canonical.Status, canonical.HomeGoals, canonical.AwayGoals), ("FINISHED", 1, 3))
        self.assertEqual(duplicate.Status, "DUPLICATE")


if __name__ == "__main__":
    unittest.main()
