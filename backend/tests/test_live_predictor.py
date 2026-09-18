import unittest
from unittest.mock import Mock, patch

import numpy as np

import fixture
import live_predictor


class LivePredictorTests(unittest.TestCase):
    def test_live_odds_reject_suspended_and_invalid_markets(self):
        values = [{"value": name, "odd": odd} for name, odd in
                  [("Home", "1.5"), ("Draw", "4"), ("Away", "7")]]
        item = {"fixture": {"id": 123}, "status": {},
                "odds": [{"name": "Fulltime Result", "values": values}]}
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

    @patch.object(live_predictor, "API_FOOTBALL_KEY", "test-key")
    @patch("live_predictor.requests.get")
    def test_live_fixture_uses_internal_league_and_current_score(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"response": [
            {
                "fixture": {
                    "id": 101,
                    "date": "2026-09-17T20:00:00+00:00",
                    "status": {"elapsed": 62, "short": "2H"},
                },
                "league": {"id": 39},
                "teams": {
                    "home": {"name": "Manchester City FC"},
                    "away": {"name": "Arsenal FC"},
                },
                "goals": {"home": 2, "away": 1},
                "score": {"halftime": {"home": 1, "away": 1}},
            },
            {
                "fixture": {
                    "id": 999,
                    "date": "2026-09-17T20:00:00+00:00",
                    "status": {"elapsed": 10, "short": "1H"},
                },
                "league": {"id": 9999},
                "teams": {"home": {"name": "Other"}, "away": {"name": "Other 2"}},
                "goals": {"home": 0, "away": 0},
                "score": {"halftime": {"home": None, "away": None}},
            },
        ]}
        get.return_value = response

        matches = live_predictor.get_live_fixtures()

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["league"], "E0")
        self.assertEqual(matches[0]["home_team"], "Man City")
        self.assertEqual(matches[0]["home_goals"], 2)
        self.assertEqual(matches[0]["elapsed"], 62)

    @patch("fixture.get_live_events_summary")
    @patch("fixture.get_live_odds_from_api_football")
    @patch("fixture.get_live_fixtures")
    def test_live_prediction_selects_league_model_and_returns_swift_shape(
        self, get_fixtures, get_odds, get_events
    ):
        get_fixtures.return_value = [{
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
        }]
        get_odds.return_value = {"B365H": 1.5, "B365D": 4.0, "B365A": 7.0}
        get_events.return_value = live_predictor._empty_event_summary()
        premier_league_model = Mock()
        premier_league_model.predict.return_value = np.array([1])
        premier_league_model.predict_proba.return_value = np.array([[0.1, 0.2, 0.7]])
        premier_league_model.classes_ = np.array([-1, 0, 1])

        result = fixture.predict_from_live_api(
            {"E0": premier_league_model, "D1": Mock()},
            ["HomeProb", "DrawProb", "AwayProb", "HY"],
        )[0]

        self.assertEqual(result["league"], "E0")
        self.assertEqual(result["score"], "2 - 1")
        self.assertEqual(result["elapsed"], 62)
        self.assertEqual(result["predicted_label"], "Home Win")
        self.assertEqual(result["home_win_pct"], 70.0)
        get_events.assert_called_once_with(101, "Manchester City FC", "Arsenal FC")

    @patch("fixture.get_live_events_summary")
    @patch("fixture.get_live_odds_from_api_football", return_value=None)
    @patch("fixture.get_live_fixtures")
    def test_live_match_remains_visible_when_odds_are_unavailable(
        self, get_fixtures, _get_odds, get_events
    ):
        get_fixtures.return_value = [{
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
        }]
        get_events.return_value = live_predictor._empty_event_summary()

        result = fixture.predict_from_live_api({}, ["HomeProb"])[0]

        self.assertEqual(result["fixture_id"], 202)
        self.assertIsNone(result["predicted_label"])
        self.assertEqual(result["score"], "0 - 0")


if __name__ == "__main__":
    unittest.main()
