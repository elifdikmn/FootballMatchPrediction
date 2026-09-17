import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_utils import save_model_prediction
from match_repository import prediction_metadata
from models import Base, Fixture, PredictionSnapshot


class PredictionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.db.add(Fixture(
            FixtureID=7,
            Date="2026-09-20",
            League="E0",
            HomeTeam="Arsenal",
            AwayTeam="Chelsea",
            Status="SCHEDULED",
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def prediction(self, home=50.0, draw=25.0, away=25.0):
        return {
            "FixtureID": 7,
            "Predicted_Label": "Home Win",
            "Home Win %": home,
            "Draw %": draw,
            "Away Win %": away,
        }

    def test_changed_pre_match_prediction_appends_version_and_exposes_delta(self):
        save_model_prediction(self.prediction(), db=self.db)
        save_model_prediction(self.prediction(56.0, 23.0, 21.0), db=self.db, trigger="LINEUP")
        self.db.commit()

        snapshots = self.db.query(PredictionSnapshot).order_by(PredictionSnapshot.version).all()
        self.assertEqual([row.version for row in snapshots], [1, 2])
        metadata = prediction_metadata(self.db, [7])[7]
        self.assertEqual(metadata["prediction_trigger"], "LINEUP")
        self.assertEqual(metadata["home_delta"], 6.0)
        self.assertEqual(metadata["draw_delta"], -2.0)
        self.assertEqual(metadata["away_delta"], -4.0)

    def test_identical_prediction_does_not_create_duplicate_snapshot(self):
        save_model_prediction(self.prediction(), db=self.db)
        save_model_prediction(self.prediction(), db=self.db)
        self.db.commit()
        self.assertEqual(self.db.query(PredictionSnapshot).count(), 1)

    def test_live_prediction_does_not_replace_pre_match_fields(self):
        save_model_prediction(self.prediction(), db=self.db)
        save_model_prediction(
            self.prediction(10.0, 20.0, 70.0),
            db=self.db,
            prediction_type="LIVE",
            trigger="LIVE_STATE",
        )
        self.db.commit()
        fixture = self.db.get(Fixture, 7)
        self.assertEqual(fixture.HomeWinPct, 50.0)
        self.assertEqual(fixture.AwayWinPct, 25.0)
        self.assertEqual(
            self.db.query(PredictionSnapshot).filter_by(prediction_type="LIVE").count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
