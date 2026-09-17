from datetime import date
import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Fixture, Standing
from standings_sync import sync_super_lig_standings, sync_european_standings


class StandingsSyncTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_fixture(self, status="FINISHED"):
        self.db.add(Fixture(
            FixtureID=44,
            Date="2026-09-17",
            League="T1",
            HomeTeam="Galatasaray",
            AwayTeam="Fenerbahce",
            Status=status,
        ))
        self.db.commit()

    def test_european_sync_uses_total_table_and_preserves_failed_league(self):
        self.db.add(Standing(league="78", team_name="Previous", points=10))
        self.db.commit()
        entry = {"team": {"name": "Arsenal FC"}, "position": 1, "points": 12,
                 "goalDifference": 8, "playedGames": 4, "won": 4, "draw": 0, "lost": 0}
        good = Mock()
        good.json.return_value = {"standings": [
            {"type": "HOME", "table": []}, {"type": "TOTAL", "table": [entry]}]}
        bad = Mock()
        bad.json.return_value = {"standings": []}
        http = Mock()
        http.get.side_effect = [bad, good, good, good, good]
        with self.assertRaises(RuntimeError):
            sync_european_standings(self.db, "test-key", http=http)
        self.assertEqual(self.db.query(Standing).filter_by(league="78").one().points, 10)
        row = self.db.query(Standing).filter_by(league="39").one()
        self.assertEqual((row.team_name, row.points), ("Arsenal", 12))
        self.assertEqual(http.get.call_count, 5)

    def test_first_run_waits_until_matches_finish(self):
        self.add_fixture("LIVE")
        http = Mock()
        result = sync_super_lig_standings(
            self.db, "key", date(2026, 9, 17), retry=False, http=http
        )
        self.assertEqual(result["reason"], "matches still in progress")
        http.get.assert_not_called()

    def test_retry_upserts_the_complete_table(self):
        self.add_fixture("LIVE")
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": [{"league": {"standings": [[{
            "rank": 1,
            "team": {"name": "Galatasaray"},
            "points": 12,
            "goalsDiff": 8,
            "all": {"played": 4, "win": 4, "draw": 0, "lose": 0},
        }]]}}]}
        http = Mock(get=Mock(return_value=response))

        result = sync_super_lig_standings(
            self.db, "key", date(2026, 9, 17), retry=True, http=http
        )
        self.assertEqual(result, {"status": "updated", "reason": None, "rows": 1})
        row = self.db.query(Standing).one()
        self.assertEqual((row.rank, row.points, row.played), (1, 12, 4))
        http.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
