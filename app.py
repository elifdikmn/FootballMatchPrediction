from flask import Flask, jsonify, request,json
import requests
import pandas as pd
import pickle
import joblib
import numpy as np
from datetime import datetime
from threading import Lock
from time import monotonic
from fixture import get_match_from_api
from db_setup import SessionLocal, init_db
from models import Fixture, Standing, LiveMatchState
from live_repository import cached_events, persist_live_matches, replace_events
from match_repository import prediction_dates as load_prediction_dates
from match_repository import scheduled_rows, score_value, prediction_metadata
from fixture import get_grouped_standings
from evaluation import evaluate_model_accuracy
from fixture import get_combined_fixtures_with_odds
from fixture import get_live_matches_with_predictions
from fixture import get_match_events
from fixture import predict_from_live_api
from fixture import get_standings_by_league
from fixture import league_ids
from fixture import get_current_season
from branding import branding_catalogue, logo_for_team
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
init_db()

_live_cache = {"updated": 0.0, "matches": []}
_live_cache_lock = Lock()
_event_cache_times = {}
_event_cache_lock = Lock()


def get_branding_data():
    seasons = set()
    try:
        with SessionLocal() as session:
            fixtures = session.query(Fixture.Date, Fixture.League).all()
        for match_date_value, league in fixtures:
            if league not in league_ids:
                continue
            match_date = datetime.strptime(str(match_date_value)[:10], "%Y-%m-%d")
            seasons.add(match_date.year if match_date.month >= 7 else match_date.year - 1)
    except (ValueError, TypeError, AttributeError):
        seasons = {get_current_season()}

    return branding_catalogue(
        league_ids,
        sorted(seasons) or [get_current_season()],
        API_FOOTBALL_KEY,
        cache_path="branding_cache.json",
    )


@app.route("/branding")
def branding():
    return jsonify(get_branding_data())


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
    with SessionLocal() as session:
        fixtures = session.query(Fixture).all()
        data = {str(f.FixtureID): _legacy_fixture_payload(f) for f in fixtures}
    return jsonify(data)



@app.route("/standings/<league_code>", methods=["GET"])
def get_standings(league_code):
    catalogue = get_branding_data()
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
            "team_logo": logo_for_team(catalogue, league_code, s.team_name),
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

@app.route("/prediction-dates")
def prediction_dates():
    with SessionLocal() as session:
        dates = load_prediction_dates(session, league_ids.keys())
    return jsonify(dates)


def _legacy_fixture_payload(fixture):
    return {
        "FixtureID": fixture.FixtureID,
        "Date": fixture.Date,
        "League": fixture.League,
        "HomeTeam": fixture.HomeTeam,
        "AwayTeam": fixture.AwayTeam,
        "Predicted_Label": fixture.Predicted_Label,
        "Home Win %": fixture.HomeWinPct,
        "Draw %": fixture.DrawPct,
        "Away Win %": fixture.AwayWinPct,
        "HomeGoals": score_value(fixture.HomeGoals),
        "AwayGoals": score_value(fixture.AwayGoals),
        "Status": fixture.Status,
    }


def _scheduled_payload(fixture, kickoff_utc, catalogue, metadata=None):
    payload = {
        "fixture_id": fixture.FixtureID,
        "home_team": fixture.HomeTeam,
        "away_team": fixture.AwayTeam,
        "home_team_logo": logo_for_team(catalogue, fixture.League, fixture.HomeTeam),
        "away_team_logo": logo_for_team(catalogue, fixture.League, fixture.AwayTeam),
        "league": fixture.League,
        "date": kickoff_utc or fixture.Date,
        "status": fixture.Status,
        "home_goals": score_value(fixture.HomeGoals),
        "away_goals": score_value(fixture.AwayGoals),
        "predicted_label": fixture.Predicted_Label,
        "home_win_pct": fixture.HomeWinPct,
        "draw_pct": fixture.DrawPct,
        "away_win_pct": fixture.AwayWinPct,
        "is_live": fixture.Status == "LIVE",
    }
    payload.update(metadata or {})
    return payload


@app.route("/scheduled-predictions")
def scheduled_predictions():
    selected_date = request.args.get("date")
    if selected_date:
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    catalogue = get_branding_data()
    with SessionLocal() as session:
        rows = scheduled_rows(session, league_ids.keys(), selected_date)
        metadata = prediction_metadata(session, (fixture.FixtureID for fixture, _ in rows))
        output = [
            _scheduled_payload(fixture, kickoff, catalogue, metadata.get(fixture.FixtureID))
            for fixture, kickoff in rows
        ]
    return jsonify(output)


@app.route("/events/<int:fixture_id>", methods=["GET"])
def match_events(fixture_id):
    with SessionLocal() as session:
        state = session.get(LiveMatchState, fixture_id)
        provider_fixture_id = int(state.provider_fixture_id) if state else fixture_id
        with _event_cache_lock:
            cache_fresh = monotonic() - _event_cache_times.get(fixture_id, 0) < 90
            if cache_fresh:
                events = cached_events(session, fixture_id)
            else:
                events = get_match_events(provider_fixture_id)
                if events:
                    replace_events(session, fixture_id, events)
                else:
                    events = cached_events(session, fixture_id)
                _event_cache_times[fixture_id] = monotonic()
    return jsonify(events)


@app.route("/live-matches-with-predictions", methods=["GET"])
def live_matches_with_predictions():
    with _live_cache_lock:
        if monotonic() - _live_cache["updated"] < 300:
            data = [dict(match) for match in _live_cache["matches"]]
        else:
            data = get_live_matches_with_predictions(
                best_models, features_by_league, team_categories, historical_data_by_league
            )
            with SessionLocal() as session:
                data = persist_live_matches(session, data)
            _live_cache["matches"] = [dict(match) for match in data]
            _live_cache["updated"] = monotonic()
    catalogue = get_branding_data()
    for match in data:
        league = match.get("league") or match.get("League")
        home = match.get("home_team") or match.get("HomeTeam")
        away = match.get("away_team") or match.get("AwayTeam")
        match["home_team_logo"] = logo_for_team(catalogue, league, home) if league and home else None
        match["away_team_logo"] = logo_for_team(catalogue, league, away) if league and away else None
    return jsonify(data)


@app.route("/live-simple", methods=["GET"])
def live_simple():
    results = predict_from_live_api(live_best_models, live_features)
    return jsonify(results)

@app.route("/prediction/<int:fixture_id>", methods=["GET"])
def get_prediction(fixture_id):
    with SessionLocal() as session:
        fixture = session.get(Fixture, fixture_id)
    if fixture is None or fixture.Predicted_Label is None:
        return jsonify({"error": "No prediction found"}), 404
    winner = {
        "Home Win": fixture.HomeTeam,
        "Away Win": fixture.AwayTeam,
        "Draw": "Draw",
    }.get(fixture.Predicted_Label, fixture.Predicted_Label)
    return jsonify({
        "winner": winner,
        "comment": "Prediction generated by the MatchdayLedger model from recent form and rating features.",
        "advice": f"Most likely outcome: {fixture.Predicted_Label}.",
        "home_pct": f"{fixture.HomeWinPct:.2f}%" if fixture.HomeWinPct is not None else None,
        "draw_pct": f"{fixture.DrawPct:.2f}%" if fixture.DrawPct is not None else None,
        "away_pct": f"{fixture.AwayWinPct:.2f}%" if fixture.AwayWinPct is not None else None,
        "last_5_home": None,
        "last_5_away": None,
    })

@app.route("/predictioncache")
def get_predictions():
    with SessionLocal() as session:
        data = {
            str(f.FixtureID): _legacy_fixture_payload(f)
            for f in session.query(Fixture).all()
        }
    print(f"✅ {len(data)} adet tahmin veritabanından yüklendi")

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
