import requests

from team_normalizer import team_name_map
from team_normalizer import map_live_team_name
from config import API_FOOTBALL_KEY
HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

API_FOOTBALL_LEAGUES = {
    78: "D1",
    39: "E0",
    140: "SP1",
    135: "I1",
    61: "F1",
    203: "T1",
}


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


def get_live_events_summary(fixture_id, home_team, away_team):
    summary = _empty_event_summary()
    if not API_FOOTBALL_KEY:
        return summary
    url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as error:
        print(f"❌ Event API connection error ({fixture_id}): {error}")
        return summary

    if response.status_code != 200:
        print(f"❌ Event API hatası ({fixture_id}):", response.status_code)
        return summary

    data = response.json().get("response", [])

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
    if not API_FOOTBALL_KEY:
        return []
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as error:
        print(f"❌ Live fixtures API connection error: {error}")
        return []

    if response.status_code != 200:
        print("❌ Live fixtures API hatası:", response.status_code)
        return []

    data = response.json().get("response", [])
    live_fixtures = []

    for match in data:
        league_code = API_FOOTBALL_LEAGUES.get(match.get("league", {}).get("id"))
        if league_code is None:
            continue
        fixture_id = match["fixture"]["id"]
        raw_home_team = match["teams"]["home"]["name"]
        raw_away_team = match["teams"]["away"]["name"]
        home_team = map_live_team_name(raw_home_team, team_name_map)
        away_team = map_live_team_name(raw_away_team, team_name_map)
        elapsed = match["fixture"]["status"]["elapsed"]
        halftime_score = match.get("score", {}).get("halftime", {"home": 0, "away": 0})
        goals = match.get("goals") or {}

        live_fixtures.append({
            "fixture_id": fixture_id,
            "date": str(match["fixture"].get("date") or "")[:10],
            "home_team": home_team,
            "away_team": away_team,
            "provider_home_team": raw_home_team,
            "provider_away_team": raw_away_team,
            "elapsed": elapsed,
            "home_goals": goals.get("home") or 0,
            "away_goals": goals.get("away") or 0,
            "ht_home_goals": halftime_score.get("home") or 0,
            "ht_away_goals": halftime_score.get("away") or 0,
            "league": league_code,
            "status": match["fixture"]["status"].get("short") or "LIVE",
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
    if not API_FOOTBALL_KEY:
        return None
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as error:
        print(f"❌ API-Football odds connection error ({fixture_id}): {error}")
        return None

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
