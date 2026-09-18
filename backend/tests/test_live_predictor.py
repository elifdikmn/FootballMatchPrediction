import unittest
from unittest.mock import Mock

import numpy as np

import live_predictor


class LivePredictorTests(unittest.TestCase):
    def test_live_odds_reject_suspended_and_invalid_markets(self):
        values = [
            {"value": name, "odd": odd}
            for name, odd in (("Home", "1.5"), ("Draw", "4"), ("Away", "7"))
        ]
        item = {
            "fixture": {"id": 123},
            "status": {},
            "odds": [{"name": "Fulltime Result", "values": values}],
        }
        payload = {"response": [item]}
        self.assertEqual(live_predictor.parse_live_odds(payload, 123)["B365H"], 1.5)
        self.assertIsNone(live_predictor.parse_live_odds(payload, 456))
        item["status"]["blocked"] = True
        self.assertIsNone(live_predictor.parse_live_odds(payload, 123))
        item["status"] = {}
        values[0]["suspended"] = True
        self.assertIsNone(live_predictor.parse_live_odds(payload, 123))
        values[0]["suspended"] = False
        values[0]["odd"] = "nan"
        self.assertIsNone(live_predictor.parse_live_odds(payload, 123))

    def test_live_prediction_selects_league_model_and_returns_swift_shape(self):
        match = {
            "fixture_id": 101,
            "date": "2026-09-17",
            "home_team": "Man City",
            "away_team": "Arsenal",
            "provider_home_team": "Manchester City FC",
            "provider_away_team": "Arsenal FC",
            "elapsed": 62,
            "home_goals": 2,
            "away_goals": 1,
            "ht_home_goals": 1,
            "ht_away_goals": 1,
            "league": "E0",
            "status": "2H",
        }
        model = Mock()
        model.predict.return_value = np.array([1])
        model.predict_proba.return_value = np.array([[0.1, 0.2, 0.7]])
        model.classes_ = np.array([-1, 0, 1])
        events_loader = Mock(return_value=live_predictor._empty_event_summary())

        result = live_predictor.predict_from_live_api(
            {"E0": model},
            ["HomeProb", "DrawProb", "AwayProb", "HY"],
            [match],
            odds_loader=lambda _: {"B365H": 1.5, "B365D": 4.0, "B365A": 7.0},
            events_loader=events_loader,
        )[0]

        self.assertEqual(result["score"], "2 - 1")
        self.assertEqual(result["predicted_label"], "Home Win")
        self.assertEqual(result["home_win_pct"], 70.0)
        events_loader.assert_called_once_with(101, "Manchester City FC", "Arsenal FC")

    def test_live_match_remains_visible_when_odds_are_unavailable(self):
        match = {
            "fixture_id": 202,
            "date": "2026-09-17",
            "home_team": "Bayern Munich",
            "away_team": "Dortmund",
            "elapsed": None,
            "home_goals": 0,
            "away_goals": 0,
            "ht_home_goals": 0,
            "ht_away_goals": 0,
            "league": "D1",
            "status": "1H",
        }
        result = live_predictor.predict_from_live_api(
            {}, ["HomeProb"], [match],
            odds_loader=lambda _: None,
            events_loader=lambda *_: live_predictor._empty_event_summary(),
        )[0]

        self.assertEqual(result["fixture_id"], 202)
        self.assertIsNone(result["predicted_label"])
        self.assertEqual(result["score"], "0 - 0")


if __name__ == "__main__":
    unittest.main()
