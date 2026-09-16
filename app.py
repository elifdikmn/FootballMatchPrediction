from flask import Flask, jsonify, request,json
import requests
import pandas as pd
import pickle
import joblib
import numpy as np
from datetime import datetime
from fixture import get_match_from_api
from db_setup import SessionLocal
from models import Standing
from fixture import get_grouped_standings
from evaluation import evaluate_model_accuracy
from fixture import get_combined_fixtures_with_odds
from fixture import get_live_matches_with_predictions
from fixture import get_match_events
from fixture import predict_from_live_api
from fixture import get_standings_by_league
from fixture import league_ids
from feature_engineering import (
    add_latest_elo_to_fixtures,
    add_latest_elo_features_to_fixtures,
    add_all_features_to_merged_df
)
from prediction_pipeline import predict_from_merged_df
from fixture import merge_xg_to_fixtures, xg_data
from config import(
    features,
    live_features,
    features_tr,
    features_by_league,
    API_FOOTBALL_KEY
)
import os

app = Flask(__name__)

@app.route("/branding")
def branding():
    from branding import branding_catalogue
    from fixture import get_current_season
    return jsonify(branding_catalogue(league_ids, get_current_season(), API_FOOTBALL_KEY))


# Model ve encoder yükle
with open("best_models.pkl", "rb") as f:
    best_models = pickle.load(f)
with open("live_best_models.pkl", "rb") as f:
    live_best_models = pickle.load(f)
team_categories = joblib.load("team_categories.pkl")


# Historical data
historical_data_by_league = {
    "D1": pd.read_csv("D1_matches.csv", parse_dates=["Date"]),
    "E0": pd.read_csv("E0_matches.csv", parse_dates=["Date"]),
    "SP1": pd.read_csv("SP1_matches.csv", parse_dates=["Date"]),
    "I1": pd.read_csv("I1_matches.csv", parse_dates=["Date"]),
    "F1": pd.read_csv("F1_matches.csv", parse_dates=["Date"]),
    "T1": pd.read_csv("T1_matches.csv", parse_dates=["Date"])
}



@app.route("/predictionmatch")
def predictions():
    with open("prediction_cache.json") as f:
        data = json.load(f)
    return jsonify(data)



@app.route("/standings/<league_code>", methods=["GET"])
def get_standings(league_code):
    session = SessionLocal()
    try:
        db_league_id = str(league_ids.get(league_code, league_code))
        standings = session.query(Standing).filter_by(league=db_league_id).order_by(Standing.rank.asc()).all()
    finally:
        session.close()
    return jsonify([
        {
            "position": s.rank,
            "team": s.team_name,
            "playedGames": s.played,
            "won": s.win,
            "draw": s.draw,
            "lost": s.lose,
            "points": s.points,
            "goalDifference": s.goals_diff
        }
        for s in standings
    ])
@app.route("/standings/grouped")
def grouped_standings_route():
    # URL parametrelerini al
    league_id = request.args.get("league_id", default=15, type=int)
    season = request.args.get("season", default=None, type=int)

    # fixture.py içindeki fonksiyonu çağır
    standings = get_grouped_standings(league_id=league_id, season=season)
    
    return jsonify(standings)

@app.route("/scheduled-predictions")
def scheduled_predictions():
    with open("prediction_cache.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    selected_date = request.args.get("date")
    if selected_date:
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    output = []
    for fx in data.values():
        matches_date = str(fx.get("Date", ""))[:10] == selected_date if selected_date else fx.get("Status") == "SCHEDULED"
        if matches_date and fx.get("League") in league_ids:
            output.append({
                "fixture_id": fx["FixtureID"],
                "home_team": fx.get("HomeTeam") or fx.get("home_team"),
                "away_team": fx.get("AwayTeam") or fx.get("away_team"),
                "league": fx["League"],
                "date": fx["Date"],
                "predicted_label": fx.get("Predicted_Label") or fx.get("predicted_label"),
                "home_win_pct": fx.get("Home Win %") or fx.get("home_win_pct"),
                "draw_pct": fx.get("Draw %") or fx.get("draw_pct"),
                "away_win_pct": fx.get("Away Win %") or fx.get("away_win_pct"),
            })

    return jsonify(output)


@app.route("/events/<int:fixture_id>", methods=["GET"])
def match_events(fixture_id):
    events = get_match_events(fixture_id)
    return jsonify(events)


@app.route("/live-matches-with-predictions", methods=["GET"])
def live_matches_with_predictions():
    data = get_live_matches_with_predictions(best_models, features_by_league, team_categories, historical_data_by_league)
    return jsonify(data)


@app.route("/live-simple", methods=["GET"])
def live_simple():
    results = predict_from_live_api(live_best_models, live_features)
    return jsonify(results)

@app.route("/prediction/<int:fixture_id>", methods=["GET"])
def get_prediction(fixture_id):
    url = f"https://v3.football.api-sports.io/predictions?fixture={fixture_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    response = requests.get(url, headers=headers)
    data = response.json().get("response", [])

    if not data:
        return jsonify({"error": "No prediction found"}), 404

    prediction_raw = data[0]
    predictions = prediction_raw["predictions"]
    home_last5 = prediction_raw["teams"]["home"]["last_5"]
    away_last5 = prediction_raw["teams"]["away"]["last_5"]

    result = {
        "winner": predictions["winner"]["name"],
        "comment": predictions["winner"]["comment"],
        "advice": predictions["advice"],
        "home_pct": predictions["percent"]["home"],
        "draw_pct": predictions["percent"]["draw"],
        "away_pct": predictions["percent"]["away"],
        "goals_home": predictions["goals"]["home"],
        "goals_away": predictions["goals"]["away"],
        "under_over": predictions.get("under_over"),
        "form_home": prediction_raw["comparison"]["form"]["home"],
        "form_away": prediction_raw["comparison"]["form"]["away"],
        "poisson_home": prediction_raw["comparison"]["poisson_distribution"]["home"],
        "poisson_away": prediction_raw["comparison"]["poisson_distribution"]["away"],
        "h2h_home": prediction_raw["comparison"]["h2h"]["home"],
        "h2h_away": prediction_raw["comparison"]["h2h"]["away"],
        "last_5_home": {
            "form": home_last5["form"],
            "att": home_last5["att"],
            "def": home_last5["def"],
            "goals": {
                "for": {
                    "total": home_last5["goals"]["for"]["total"],
                    "average": float(home_last5["goals"]["for"]["average"])
                },
                "against": {
                    "total": home_last5["goals"]["against"]["total"],
                    "average": float(home_last5["goals"]["against"]["average"])
                }
            }
        },
        "last_5_away": {
            "form": away_last5["form"],
            "att": away_last5["att"],
            "def": away_last5["def"],
            "goals": {
                "for": {
                    "total": away_last5["goals"]["for"]["total"],
                    "average": float(away_last5["goals"]["for"]["average"])
                },
                "against": {
                    "total": away_last5["goals"]["against"]["total"],
                    "average": float(away_last5["goals"]["against"]["average"])
                }
            }
        }
    }

    return jsonify(result)

from pathlib import Path
CACHE_FILE = Path("prediction_cache.json")

@app.route("/predictioncache")
def get_predictions():
    if not CACHE_FILE.exists():
        return jsonify([])

    with open(CACHE_FILE, "r") as f:
        data = json.load(f)

    print(f"✅ {len(data)} adet tahmin yüklendi")

    # JSON objesi bir dict ise, Swift tarafı list beklediği için listeye çevir
    if isinstance(data, dict):
        return jsonify(list(data.values()))
    return jsonify(data)

@app.route("/api/evaluation")
def get_evaluation():
    return jsonify(evaluate_model_accuracy())


@app.route("/data-range", methods=["GET"])

def get_predictions_for_range():
    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    if not from_date_str or not to_date_str:
        return jsonify({"error": "Please provide from and to dates (YYYY-MM-DD)"}), 400

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # 🧠 1. Tüm maçları al
    merged_df = get_combined_fixtures_with_odds()
    merged_df = merge_xg_to_fixtures(merged_df, xg_data)
    merged_df["Date"] = pd.to_datetime(merged_df["Date"], errors="coerce").dt.date
    merged_df = merged_df.dropna(subset=["Date"])

    # 🧠 2. Tarih aralığına göre filtrele
    merged_df = merged_df[(merged_df["Date"] >= from_date) & (merged_df["Date"] <= to_date)]

    if merged_df.empty:
        return jsonify([])

    # 🧠 3. Kodlama
    merged_df["HomeTeam_code"] = pd.Categorical(merged_df["HomeTeam"], categories=team_categories).codes
    merged_df["AwayTeam_code"] = pd.Categorical(merged_df["AwayTeam"], categories=team_categories).codes

    # 🧠 4. Özellik mühendisliği
    merged_df = add_latest_elo_to_fixtures(merged_df, historical_data_by_league)
    merged_df = add_latest_elo_features_to_fixtures(merged_df, historical_data_by_league)
    merged_df = add_all_features_to_merged_df(merged_df, historical_data_by_league)

    # 🧠 5. Tahmin (sadece mümkün olanlar)
    all_predictions = []
    for league in merged_df["League"].unique():
        league_df = merged_df[merged_df["League"] == league]
        model = best_models.get(league)
        feature_set = features_by_league.get(league)
        if model and feature_set:
            preds = predict_from_merged_df(league_df, {league: model}, {league: feature_set})
            all_predictions.append(preds)
            if all_predictions:
                predicted_df = pd.concat(all_predictions, ignore_index=True)
            else:
                predicted_df = pd.DataFrame(columns=["FixtureID", "Predicted_Label", "Home Win %", "Draw %", "Away Win %"])


    # 🧠 6. Tahminleri FixtureID ile merge et
    full_df = merged_df.merge(
        predicted_df[["FixtureID", "Predicted_Label", "Home Win %", "Draw %", "Away Win %"]],
        on="FixtureID",
        how="left"
    )

    # 🔧 7. Eksik tahminleri doldur
    full_df["Predicted_Label"] = full_df["Predicted_Label"].fillna("N/A")
    full_df["Home Win %"] = full_df["Home Win %"].fillna(0)
    full_df["Draw %"] = full_df["Draw %"].fillna(0)
    full_df["Away Win %"] = full_df["Away Win %"].fillna(0)

    # 🔧 8. Skor ve dakika bilgisi varsa Score sütunu oluştur
    def format_score(row):
        if pd.notnull(row["HomeGoals"]) and pd.notnull(row["AwayGoals"]):
            return f"{row['HomeGoals']} - {row['AwayGoals']}"
        return None

    full_df["Score"] = full_df.apply(format_score, axis=1)

    # 🔧 9. Elapsed eksikse None bırak
    if "Elapsed" not in full_df.columns:
        full_df["Elapsed"] = None

    for col in ["HomeGoals", "AwayGoals", "Elapsed"]:
       full_df[col] = full_df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
    
    full_df["Date"] = full_df["Date"].astype(str)
    



    # 🧠 10. JSON çıktısı
    output = full_df[[
        "FixtureID", "Date", "League", "HomeTeam", "AwayTeam",
        "Predicted_Label", "Home Win %", "Draw %", "Away Win %",
        "HomeGoals", "AwayGoals", "Status"
    ]].to_dict(orient="records")

    for row in output:
    # Goller float gibi görünüyorsa int'e çevir
        if isinstance(row.get("HomeGoals"), float) and row["HomeGoals"].is_integer():
           row["HomeGoals"] = int(row["HomeGoals"])
        if isinstance(row.get("AwayGoals"), float) and row["AwayGoals"].is_integer():
           row["AwayGoals"] = int(row["AwayGoals"])


    return jsonify(json.loads(json.dumps(output)))



if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
