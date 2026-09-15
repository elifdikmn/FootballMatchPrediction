# main.py gibi
from flask import Flask, jsonify
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
app = Flask(__name__)


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

import requests
live_matches = get_live_fixtures()

for match in live_matches:
    fixture_id = match["fixture_id"]
    home_team = match["home_team"]
    away_team = match["away_team"]
    elapsed = match["elapsed"]
    ht_home = match["ht_home_goals"]
    ht_away = match["ht_away_goals"]

    ht_goal_diff = ht_home - ht_away
    score_str = f"{ht_home} - {ht_away}"
    htr = get_htr(score_str, home_team, away_team)

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

results = []  # ⬅️ Tüm tahminleri saklamak için

def get_htr(score, home_team, away_team):
    home_goals, away_goals = map(int, score.strip().split(" - "))
    if home_goals > away_goals:
        return "H"
    elif home_goals < away_goals:
        return "A"
    else:
        return "D"


def get_htr(score, home_team, away_team):
    home_goals, away_goals = map(int, score.strip().split(" - "))
    if home_goals > away_goals:
        return "H"
    elif home_goals < away_goals:
        return "A"
    else:
        return "D"

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

filtered_matches = live_matches


# 🔄 Artık sadece filtrelenmiş maçlara bak
for match in filtered_matches:
    fixture_id = match["fixture_id"]
    home_team_api = match["home_team"]
    away_team_api = match["away_team"]
    elapsed = match["elapsed"]
    ht_home = match.get("ht_home_goals", 0)
    ht_away = match.get("ht_away_goals", 0)
    score_str = f"{ht_home} - {ht_away}"

    # 🔹 Adları normalize edip map'le
    home_team_mapped = map_live_team_name(home_team_api, team_name_map)
    away_team_mapped = map_live_team_name(away_team_api, team_name_map)

    # 🔹 Encode et


    # 🔹 İlk yarı sonucu
    htr = get_htr(score_str, home_team_api, away_team_api)
    htr_map = {"A": -1, "D": 0, "H": 1}
    htr_code = htr_map.get(htr, 0)

    # 🔹 Events ve odds verisini çek
    event_summary = get_live_events_summary(fixture_id, home_team_api, away_team_api)
    odds = get_live_odds_from_api_football(fixture_id)
    if odds is None:
        continue
    prob = normalize_odds(odds)

    # 🔹 Feature row
    feature_row = {
        "HY": event_summary["home_yellow_cards"],
        "AY": event_summary["away_yellow_cards"],
        "HR": event_summary["home_red_cards"],
        "AR": event_summary["away_red_cards"],
        "HTR_code": htr_code,
        "HTAG": ht_away,
        "HTHG": ht_home,
        "HomeProb": prob["HomeProb"],
        "DrawProb": prob["DrawProb"],
        "AwayProb": prob["AwayProb"]
    }

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

results = []
    #print(f"{home_team} vs {away_team} — Feature row:")
    
    #print(feature_row)

# 🔧 Yardımcı fonksiyonlar (normalize, get_htr, API istekleri vs.)
# ✅ Buraya normalize_team_name, get_live_fixtures, get_live_events_summary, get_live_odds_from_api_football, map_live_team_name, etc.

# 📌 Global değişkenler
live_features ="HomeProb","AwayProb","DrawProb","HY","AY","HR","AR","HTR_code","HTAG","HTHG"
 # modelin beklediği feature'lar
htr_map = {"A": -1, "D": 0, "H": 1}

# 🚀 Ana akış
def main():
    # 1️⃣ Model ve encoder'ı yükle
    with open("team_encoder.pkl", "rb") as f:
        team_encoder = pickle.load(f)

    with open("live_best_models.pkl", "rb") as f:
        live_best_models = pickle.load(f)


    # 2️⃣ Canlı maçları al
    live_matches = get_live_fixtures()
    if not live_matches:
        print("🔕 Canlı maç bulunamadı.")
        return


    # 4️⃣ Her maç için tahmin yap
    results = []
    for match in live_matches:
        fixture_id = match["fixture_id"]
        home_team_api = match["home_team"]
        away_team_api = match["away_team"]
        elapsed = match["elapsed"]
        ht_home = match.get("ht_home_goals", 0)
        ht_away = match.get("ht_away_goals", 0)
        score_str = f"{ht_home} - {ht_away}"
        home_goals = match["HomeGoals"]  # veya API'den gelen tam skor
        away_goals = match["AwayGoals"]

        feature_row["LiveHomeGoals"] = home_goals
        feature_row["LiveAwayGoals"] = away_goals
        feature_row["LiveGoalDiff"] = home_goals - away_goals


        htr = get_htr(score_str, home_team_api, away_team_api)
        htr_code = htr_map.get(htr, 0)

        home_team_mapped = map_live_team_name(home_team_api, team_name_map)
        away_team_mapped = map_live_team_name(away_team_api, team_name_map)

        

        # API'den olaylar ve oranları al
        event_summary = get_live_events_summary(fixture_id, home_team_api, away_team_api)
        odds = get_live_odds_from_api_football(fixture_id)
        if odds is None:
            continue
        prob = normalize_odds(odds)

        # Özellikleri hazırla
        feature_row = {
            "HY": event_summary["home_yellow_cards"],
            "AY": event_summary["away_yellow_cards"],
            "HR": event_summary["home_red_cards"],
            "AR": event_summary["away_red_cards"],
            "HTR_code": htr_code,
            "HTAG": ht_away,
            "HTHG": ht_home,
            "HomeProb": prob["HomeProb"],
            "DrawProb": prob["DrawProb"],
            "AwayProb": prob["AwayProb"],
            "LiveHomeGoals": ht_home,
            "LiveAwayGoals": ht_away,
           "LiveGoalDiff": ht_home - ht_away


        }

        row_filled = {col: feature_row.get(col, 0) for col in live_features}
        X_input = pd.DataFrame([row_filled])

        # Model tahmini
        model = live_best_models.get("E0")  # örneğin Premier League
        if model is None:
            print("❌ Model bulunamadı: E0")
            continue

        predicted = model.predict(X_input)[0]
        proba = model.predict_proba(X_input)[0]

        results.append({
            "Match": f"{home_team_api} vs {away_team_api}",
            "Elapsed": f"{elapsed} min",
            "Score": f"{ht_home}-{ht_away}",
            "Predicted": predicted,
            "Predicted_Label": {1: "Home Win", 0: "Draw", -1: "Away Win"}[predicted],
            "Home Win %": round(proba[2] * 100, 2),
            "Draw %": round(proba[1] * 100, 2),
            "Away Win %": round(proba[0] * 100, 2)
        })
with open("live_best_models.pkl", "rb") as f:
    live_best_models = pickle.load(f)
@app.route("/live_predictions", methods=["GET"])
def live_predictions():
    matches = get_live_fixtures()
    results = []


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

results = []  # ⬅️ Tüm tahminleri saklamak için

for match in live_matches:
    fixture_id = match["fixture_id"]
    home_team = match["home_team"]
    away_team = match["away_team"]
    elapsed = match["elapsed"]
  

    ht_home = match.get("ht_home_goals", 0)
    ht_away = match.get("ht_away_goals", 0)
    score_str = f"{ht_home} - {ht_away}"
    htr_map = {"A": -1, "D": 0, "H": 1}
    htr_code = htr_map.get(htr, 0) 
    htr = get_htr(score_str, home_team, away_team)

    event_summary = get_live_events_summary(fixture_id, home_team, away_team)
    odds = get_live_odds_from_api_football(fixture_id)
    
    if odds is None:
        continue

    prob = normalize_odds(odds)
    
    feature_row = {
        "HY": event_summary["home_yellow_cards"],
        "AY": event_summary["away_yellow_cards"],
        "HR": event_summary["home_red_cards"],
        "AR": event_summary["away_red_cards"],
        "HTR_code": htr_code,
        "HTAG":ht_away,
        "HTHG":ht_home,
        "HomeProb": prob["HomeProb"],
        "DrawProb": prob["DrawProb"],
        "AwayProb": prob["AwayProb"]
        # diğer feature'lar buraya eklenebilir
    }
    X_input = pd.DataFrame([feature_row])
    model = live_best_models.get("E0")
    if model is None:
        print("❌ Model bulunamadı: E0")
        continue

    row_filled = {col: feature_row.get(col, 0) for col in live_features}
    X_input = pd.DataFrame([row_filled])

    predicted =model.predict(X_input)[0]
    proba = model.predict_proba(X_input)[0]

    result_row = {
        "Match": f"{home_team} vs {away_team}",
        "Elapsed": f"{elapsed} min",
        "Score": f"{ht_home}-{ht_away}",
        "Predicted": predicted,
        "Predicted_Label": {1: "Home Win", 0: "Draw", -1: "Away Win"}[predicted],
        "Home Win %": round(proba[2] * 100, 2),
        "Draw %": round(proba[1] * 100, 2),
        "Away Win %": round(proba[0] * 100, 2),
        "league": match.get("league", "E0")

    }

    results.append(result_row)

    

    #print(f"{home_team} vs {away_team} — Feature row:")
    
    #print(feature_row)
