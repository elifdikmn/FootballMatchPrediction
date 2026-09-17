import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from match_repository import prediction_dates
from models import Base, Fixture


class PredictionDatesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_dates_are_sorted_unique_and_scoped_to_supported_leagues(self):
        self.session.add_all([
            Fixture(FixtureID=1, League="E0", Date="2025-06-01"),
            Fixture(FixtureID=2, League="E0", Date="2025-05-18"),
            Fixture(FixtureID=3, League="E0", Date="2025-05-18"),
            Fixture(FixtureID=4, League="OTHER", Date="2026-09-16"),
        ])
        self.session.commit()
        self.assertEqual(
            prediction_dates(self.session, {"E0"}),
            {"E0": ["2025-05-18", "2025-06-01"]},
        )


if __name__ == "__main__":
    unittest.main()
