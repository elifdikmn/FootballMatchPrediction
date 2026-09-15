import pandas as pd
import requests
import pickle
import joblib
from datetime import timedelta
from sklearn.preprocessing import LabelEncoder

from team_normalizer import team_name_map
from team_normalizer import map_live_team_name
from config import API_FOOTBALL_KEY
HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}


def get_live_events_summary(fixture_id, home_team, away_team):
    url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"❌ Event API hatası ({fixture_id}):", response.status_code)
        return {}

    data = response.json().get("response", [])
    summary = {
        "home_yellow_cards": 0,
        "away_yellow_cards": 0,
        "home_red_cards": 0,
        "away_red_cards": 0,
        "last_event_type": None,
        "last_event_team": None,
        "last_event_minute": None,
    }

    for event in data:
        team = event["team"]["name"]
        event_type = event["type"]
        detail = event["detail"]
        elapsed = event["time"]["elapsed"]

        # Kartlar
        if event_type == "Card":
            if detail == "Yellow Card":
                if team == home_team:
                    summary["home_yellow_cards"] += 1
                elif team == away_team:
                    summary["away_yellow_cards"] += 1
            elif detail == "Red Card":
                if team == home_team:
                    summary["home_red_cards"] += 1
                elif team == away_team:
                    summary["away_red_cards"] += 1

        # Son event
        summary["last_event_type"] = event_type
        summary["last_event_team"] = team
        summary["last_event_minute"] = elapsed

    return summary

def get_live_fixtures():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print("❌ Live fixtures API hatası:", response.status_code)
        return []

    data = response.json().get("response", [])
    live_fixtures = []

    for match in data:
        fixture_id = match["fixture"]["id"]
        home_team = match["teams"]["home"]["name"]
        away_team = match["teams"]["away"]["name"]
        elapsed = match["fixture"]["status"]["elapsed"]
        halftime_score = match.get("score", {}).get("halftime", {"home": 0, "away": 0})
        league_code = match["league"].get("code", "E0")  # ⚠️ varsa "E0", "SP1", vs.


        live_fixtures.append({
            "fixture_id": fixture_id,
            "home_team": home_team,
            "away_team": away_team,
            "elapsed": elapsed,
            "ht_home_goals": halftime_score.get("home", 0),
            "ht_away_goals": halftime_score.get("away", 0),
            "league": league_code

        })

    return live_fixtures

def get_htr(score_str, home_team, away_team):
    try:
        home_goals, away_goals = map(int, score_str.strip().split("-"))
        if home_goals > away_goals:
            return "H"
        elif home_goals < away_goals:
            return "A"
        else:
            return "D"
    except Exception as e:
        print(f"⚠️ HTR hesaplama hatası: {e}")
        return "D"  # varsayılan olarak beraberlik dön

def get_live_odds_from_api_football(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print("❌ API-Football Odds Hatası:", response.status_code)
        return None

    data = response.json().get("response", [])
    for item in data:
        for bookmaker in item.get("bookmakers", []):
            if bookmaker["name"].lower() == "bet365":
                for bet in bookmaker.get("bets", []):
                    if bet["name"].lower() == "match winner":
                        odds = {}
                        for value in bet.get("values", []):
                            outcome = value["value"].lower()
                            try:
                                price = float(value["odd"])
                            except Exception:
                                continue
                            if outcome == "home":
                                odds["B365H"] = price
                            elif outcome == "draw":
                                odds["B365D"] = price
                            elif outcome == "away":
                                odds["B365A"] = price
                        if all(k in odds for k in ["B365H", "B365D", "B365A"]):
                            return odds
    return None

def extract_card_counts(events, home_team, away_team):
    hy = ay = hr = ar = 0
    for event in events:
        if event["type"] != "Card":
            continue
        team = event["team"]
        detail = event.get("detail", "")
        is_home = team == home_team

        if "Yellow" in detail:
            if is_home:
                hy += 1
            else:
                ay += 1
        elif "Red" in detail:
            if is_home:
                hr += 1
            else:
                ar += 1
    return hy, ay, hr, ar

def normalize_odds(odds_dict):
    try:
        inverse_sum = sum(1 / odds_dict[k] for k in ["B365H", "B365D", "B365A"])
        return {
            "HomeProb": (1 / odds_dict["B365H"]) / inverse_sum,
            "DrawProb": (1 / odds_dict["B365D"]) / inverse_sum,
            "AwayProb": (1 / odds_dict["B365A"]) / inverse_sum
        }
    except ZeroDivisionError:
        return {"HomeProb": 0.33, "DrawProb": 0.33, "AwayProb": 0.33}
