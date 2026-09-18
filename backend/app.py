from flask import Flask, jsonify, request
from datetime import datetime
import pickle
from db_setup import SessionLocal, init_db
from models import Fixture, Standing
from live_sync import read_live
from live_detail import load_events, load_live_prediction
from match_repository import prediction_dates as load_prediction_dates
from match_repository import scheduled_rows, score_value, prediction_metadata
from branding import branding_catalogue, logo_for_team
from config import LEAGUE_IDS, current_season, live_features
from paths import MODEL_ARTIFACTS_DIR, RUNTIME_DIR
import os

app = Flask(__name__)
init_db()

def get_branding_data():
    seasons = set()
    try:
        with SessionLocal() as session:
            fixtures = session.query(Fixture.Date, Fixture.League).all()
        for match_date_value, league in fixtures:
            if league not in LEAGUE_IDS:
                continue
            match_date = datetime.strptime(str(match_date_value)[:10], "%Y-%m-%d")
            seasons.add(match_date.year if match_date.month >= 7 else match_date.year - 1)
    except (ValueError, TypeError, AttributeError):
        seasons = {current_season()}

    return branding_catalogue(
        LEAGUE_IDS,
        sorted(seasons) or [current_season()],
        "",  # Use bundled branding; never spend the live-data budget here.
        cache_path=RUNTIME_DIR / "branding_cache.json",
    )


@app.route("/branding")
def branding():
    return jsonify(get_branding_data())


with open(MODEL_ARTIFACTS_DIR / "live_best_models.pkl", "rb") as f:
    live_best_models = pickle.load(f)



@app.route("/standings/<league_code>", methods=["GET"])
def get_standings(league_code):
    catalogue = get_branding_data()
    session = SessionLocal()
    try:
        db_league_id = str(LEAGUE_IDS.get(league_code, league_code))
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
@app.route("/prediction-dates")
def prediction_dates():
    with SessionLocal() as session:
        dates = load_prediction_dates(session, LEAGUE_IDS.keys())
    return jsonify(dates)


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
        rows = scheduled_rows(session, LEAGUE_IDS.keys(), selected_date)
        metadata = prediction_metadata(session, (fixture.FixtureID for fixture, _ in rows))
        live_ids = {m['fixture_id'] for m in read_live(session)}
        for fixture, _ in rows:
            metadata.setdefault(fixture.FixtureID, {})['is_live'] = fixture.FixtureID in live_ids
        output = [
            _scheduled_payload(fixture, kickoff, catalogue, metadata.get(fixture.FixtureID))
            for fixture, kickoff in rows
        ]
    return jsonify(output)


@app.route("/events/<int:fixture_id>", methods=["GET"])
def match_events(fixture_id):
    return jsonify(load_events(fixture_id))


@app.route("/live-matches-with-predictions", methods=["GET"])
def live_matches_with_predictions():
    with SessionLocal() as session:
        data = read_live(session)
    catalogue = get_branding_data()
    for match in data:
        match["home_team_logo"] = logo_for_team(catalogue, match['league'], match['home_team'])
        match["away_team_logo"] = logo_for_team(catalogue, match['league'], match['away_team'])
    return jsonify(data)


@app.route("/prediction/<int:fixture_id>", methods=["GET"])
def get_prediction(fixture_id):
    if request.args.get("type") == "live":
        detail = load_live_prediction(fixture_id, live_best_models, live_features)
        if detail is None:
            return jsonify({"error": "Live prediction unavailable: awaiting data or daily budget exhausted"}), 404
        return jsonify(detail)
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

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
