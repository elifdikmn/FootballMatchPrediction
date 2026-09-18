"""Pure helpers for cached API-Football live data and live-model inference."""

import math

import pandas as pd

from config import LEAGUE_IDS


API_FOOTBALL_LEAGUES = {provider_id: code for code, provider_id in LEAGUE_IDS.items()}


def _empty_event_summary():
    return {
        "home_yellow_cards": 0,
        "away_yellow_cards": 0,
        "home_red_cards": 0,
        "away_red_cards": 0,
        "last_event_type": None,
        "last_event_team": None,
        "last_event_minute": None,
    }


def parse_live_odds(payload, fixture_id):
    """Accept active full-time 1X2 markets from a cached in-play response."""
    for item in payload.get("response", []):
        if str(item.get("fixture", {}).get("id")) != str(fixture_id):
            continue
        if any(item.get("status", {}).get(key) for key in ("blocked", "stopped", "finished")):
            continue
        for bet in item.get("odds", []):
            if str(bet.get("name", "")).lower() not in {
                "fulltime result", "full time result", "match winner"
            }:
                continue
            odds = {}
            for value in bet.get("values", []):
                if value.get("suspended") or value.get("main") is False:
                    continue
                outcome = str(value.get("value", "")).lower()
                key = {
                    "home": "B365H", "1": "B365H",
                    "draw": "B365D", "x": "B365D",
                    "away": "B365A", "2": "B365A",
                }.get(outcome)
                try:
                    price = float(value["odd"])
                except (KeyError, TypeError, ValueError):
                    continue
                if key and math.isfinite(price) and price > 1:
                    odds[key] = price
            if len(odds) == 3:
                return odds
    return None


def normalize_odds(odds):
    inverse_sum = sum(1 / odds[key] for key in ("B365H", "B365D", "B365A"))
    return {
        "HomeProb": (1 / odds["B365H"]) / inverse_sum,
        "DrawProb": (1 / odds["B365D"]) / inverse_sum,
        "AwayProb": (1 / odds["B365A"]) / inverse_sum,
    }


def predict_from_live_api(models, features, live_matches, odds_loader, events_loader):
    """Run live inference from centrally cached match, odds and event data."""
    results = []
    for match in live_matches:
        fixture_id = match["fixture_id"]
        league = match["league"]
        home_team = match["home_team"]
        away_team = match["away_team"]
        ht_home = match.get("ht_home_goals", 0)
        ht_away = match.get("ht_away_goals", 0)
        htr_code = 1 if ht_home > ht_away else -1 if ht_home < ht_away else 0

        odds = odds_loader(fixture_id)
        events = events_loader(
            fixture_id,
            match.get("provider_home_team", home_team),
            match.get("provider_away_team", away_team),
        )
        label = None
        percentages = {"home": None, "draw": None, "away": None}
        model = models.get(league)

        if odds and events is not None and model is not None:
            feature_row = {
                "HY": events["home_yellow_cards"],
                "AY": events["away_yellow_cards"],
                "HR": events["home_red_cards"],
                "AR": events["away_red_cards"],
                "HTR_code": htr_code,
                "HTAG": ht_away,
                "HTHG": ht_home,
                **normalize_odds(odds),
            }
            model_input = pd.DataFrame([
                {column: feature_row.get(column, 0) for column in features}
            ])
            predicted = model.predict(model_input)[0]
            model_probabilities = dict(zip(model.classes_, model.predict_proba(model_input)[0]))
            label = {1: "Home Win", 0: "Draw", -1: "Away Win"}.get(predicted)
            percentages = {
                "home": round(float(model_probabilities.get(1, 0)) * 100, 2),
                "draw": round(float(model_probabilities.get(0, 0)) * 100, 2),
                "away": round(float(model_probabilities.get(-1, 0)) * 100, 2),
            }

        results.append({
            "fixture_id": fixture_id,
            "date": match.get("date"),
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "score": f"{match.get('home_goals', 0)} - {match.get('away_goals', 0)}",
            "elapsed": int(match.get("elapsed") or 0),
            "status": match.get("status") or "LIVE",
            "predicted_label": label,
            "home_win_pct": percentages["home"],
            "draw_pct": percentages["draw"],
            "away_win_pct": percentages["away"],
        })
    return results
