import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from db_setup import SessionLocal
from models import Fixture, Event, Standing
from config import features_by_league
from models import PredictionInfo
from fixture import get_combined_fixtures_with_odds, get_current_season
from feature_engineering import build_features_dataframe
from prediction_pipeline import predict_from_merged_df, load_best_models
from fixture import get_odds_from_api_football  # varsa
from fixture import merge_xg_to_fixtures  # varsa
session = SessionLocal()


# 📌 API bilgileri
from config import API_FOOTBALL_KEY
BASE_URL = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_FOOTBALL_KEY}

# 🔁 xG verisini yükle
xg_data = pd.read_csv("future_xg_matches.csv")
xg_data = xg_data.rename(columns={
    "xg_home": "HxG",
    "xg_away": "AxG",
    "home_team": "HomeTeam",
    "away_team": "AwayTeam",
    "date": "Date"
})
xg_data["Date"] = pd.to_datetime(xg_data["Date"], errors="coerce").dt.date


def predict_and_save_scheduled_matches():
    from prediction_pipeline import load_best_models, predict_from_merged_df
    from feature_engineering import build_features_dataframe
    from config import features_by_league

    print("📥 Planlanmış maçlar ve oranlar yükleniyor...")
    df_combined = get_combined_fixtures_with_odds()

    # Sadece gelecek maçları al
    today = datetime.utcnow().date()
    df_scheduled = df_combined[df_combined["Status"] == "SCHEDULED"]
    df_scheduled = df_scheduled[df_scheduled["Date"] >= today]

    if df_scheduled.empty:
        print("📭 Tahmin yapılacak maç yok.")
        return

    print(f"🔢 {len(df_scheduled)} planlanmış maç için tahmin hazırlanıyor...")

    # Özellik çıkarımı
    historical_data_by_league = {
        "T1": pd.read_csv("T1_matches.csv", parse_dates=["Date"]),
        "E0": pd.read_csv("E0_matches.csv", parse_dates=["Date"]),
        "F1": pd.read_csv("F1_matches.csv", parse_dates=["Date"]),
        "D1": pd.read_csv("D1_matches.csv", parse_dates=["Date"]),
        "SP1": pd.read_csv("SP1_matches.csv", parse_dates=["Date"]),
        "I1": pd.read_csv("I1_matches.csv", parse_dates=["Date"])
    }

    feature_df = build_features_dataframe(df_scheduled.to_dict(orient="records"), historical_data_by_league)

    if feature_df.empty:
        print("❌ Feature dataframe boş, tahmin yapılamaz.")
        return

    # Tahmin
    best_models = load_best_models()
    predictions_df = predict_from_merged_df(
        feature_df,
        best_models=best_models,
        features_by_league=features_by_league
    )

    if predictions_df.empty:
        print("❌ Tahminler başarısız.")
        return

    print(f"✅ {len(predictions_df)} maç için tahmin yapıldı. Veritabanına yazılıyor...")

    # Veritabanına yaz
    session = SessionLocal()
    for _, row in predictions_df.iterrows():
        fixture = session.query(Fixture).filter_by(FixtureID=row["FixtureID"]).first()
        if fixture:
            fixture.Predicted_Label = row["Predicted_Label"]
            fixture.HomeWinPct = row["Home Win %"]
            fixture.DrawPct = row["Draw %"]
            fixture.AwayWinPct = row["Away Win %"]
            fixture.LastUpdated = datetime.utcnow().isoformat()
    session.commit()
    print("💾 Tahminler veritabanına kaydedildi.")


# ✅ 1. Haftalık fikstürleri getir
def import_upcoming_week_fixtures():
    session = SessionLocal()
    today = datetime.utcnow().date()
    next_week = today + timedelta(days=7)
    leagues = [15,203, 39, 140, 135, 61, 78]
    added = 0

    for league_id in leagues:
        url = f"{BASE_URL}/fixtures?league={league_id}&season={get_current_season()}&from={today}&to={next_week}"
        response = requests.get(url, headers=headers)
        data = response.json().get("response", [])
        for item in data:
            fixture_id = item["fixture"]["id"]
            exists = session.query(Fixture).filter_by(FixtureID=fixture_id).first()
            if exists:
                continue
            fixture = Fixture(
                FixtureID=fixture_id,
                Date=item["fixture"]["date"][:10],
                League=str(league_id),
                HomeTeam=item["teams"]["home"]["name"],
                AwayTeam=item["teams"]["away"]["name"],
                Status="SCHEDULED",
                LastUpdated=datetime.utcnow().isoformat()
            )
            session.add(fixture)
            added += 1
    session.commit()
    print(f"📆 {added} yeni fixture eklendi.")


# ✅ 2. Odds ve xG geldiyse fixture tablosunu güncelle
def update_fixtures_with_odds_and_xg():
    session = SessionLocal()
    fixtures = session.query(Fixture).filter(Fixture.Status == "SCHEDULED").all()
    df = pd.DataFrame([f.__dict__ for f in fixtures if hasattr(f, '__dict__')])

    if df.empty:
        print("📭 Güncellenecek fixture yok.")
        return

    df = merge_xg_to_fixtures(df, xg_data)

    updated = 0
    for _, row in df.iterrows():
        fixture = session.query(Fixture).filter_by(FixtureID=row["FixtureID"]).first()
        if fixture:
            fixture.HxG = row.get("HxG")
            fixture.AxG = row.get("AxG")
            fixture.xG_diff = row.get("xG_diff")
            fixture.LastUpdated = datetime.utcnow().isoformat()
            updated += 1

    session.commit()
    print(f"📊 {updated} fixture odds + xG ile güncellendi.")


# ✅ 3. Odds/xG sonrası tahminleri yeniden hesapla
def recalculate_predictions_if_features_completed():
    session = SessionLocal()
    fixtures = session.query(Fixture).filter(Fixture.Predicted_Label != None).all()
    historical_data_by_league = {
        "T1": pd.read_csv("T1_matches.csv", parse_dates=["Date"]),
        "E0": pd.read_csv("E0_matches.csv", parse_dates=["Date"]),
        "F1": pd.read_csv("F1_matches.csv", parse_dates=["Date"]),
        "D1": pd.read_csv("D1_matches.csv", parse_dates=["Date"]),
        "SP1": pd.read_csv("SP1_matches.csv", parse_dates=["Date"]),
        "I1": pd.read_csv("I1_matches.csv", parse_dates=["Date"]),
    }
    df = build_features_dataframe(fixtures, historical_data_by_league)
    def is_important_feature_updated(row):
        return (
            pd.notnull(row.get("B365H")) and
            pd.notnull(row.get("B365D")) and
            pd.notnull(row.get("B365A")) and
            pd.notnull(row.get("HxG")) and
            pd.notnull(row.get("AxG"))
        )
    to_update = df[df.apply(is_important_feature_updated, axis=1)]
    if to_update.empty:
        print("📭 Güncellenecek tahmin yok.")
        return
    print(f"♻️ {len(to_update)} fixture yeniden tahmin ediliyor...")
    best_models = load_best_models()
    predict_from_merged_df(
        to_update,
        best_models=best_models,
        features_by_league=features_by_league
    )


# ✅ 4. SCHEDULED maç FINISHED olduysa güncelle + event ekle
def update_scheduled_fixtures():
    session = SessionLocal()
    fixtures = session.query(Fixture).filter_by(Status="SCHEDULED").all()
    updated = 0
    for fx in fixtures:
        url = f"{BASE_URL}/fixtures?id={fx.FixtureID}"
        response = requests.get(url, headers=headers)
        data = response.json().get("response")
        
        if not data:
            continue
        status = data[0]["fixture"]["status"]["short"]
        if status in ("FT", "AET", "PEN"):
            fx.Status = "FINISHED"
            fx.HomeGoals = data[0]["goals"]["home"]
            fx.AwayGoals = data[0]["goals"]["away"]
            fx.LastUpdated = datetime.utcnow().isoformat()
            session.query(Event).filter_by(FixtureID=fx.FixtureID).delete()
            url_events = f"{BASE_URL}/fixtures/events?fixture={fx.FixtureID}"
            ev_data = requests.get(url_events, headers=headers).json().get("response", [])
            for ev in ev_data:
                event = Event(
                    FixtureID=fx.FixtureID,
                    minute=ev["time"]["elapsed"],
                    team=ev["team"]["name"],
                    player=ev["player"]["name"],
                    type=ev["type"],
                    detail=ev["detail"],
                    assist=ev["assist"]["name"] if ev["assist"] else None
                )
                session.add(event)
            updated += 1
    session.commit()
    print(f"✅ {updated} fixture FINISHED olarak güncellendi.")


# ✅ 5. Puan durumu güncelle
def update_standings(league_id):
    session = SessionLocal()
    url = f"{BASE_URL}/standings?league={league_id}&season={get_current_season()}"
    response = requests.get(url, headers=headers)
    data = response.json().get("response", [])
    if not data:
        print("⚠️ Standings boş")
        return
    standings_data = data[0]["league"]["standings"][0]
    session.query(Standing).filter_by(league=str(league_id)).delete()
    for team in standings_data:
        standing = Standing(
            league=str(league_id),
            team_name=team["team"]["name"],
            rank=team["rank"],
            points=team["points"],
            goals_diff=team["goalsDiff"],
            played=team["all"]["played"],
            win=team["all"]["win"],
            draw=team["all"]["draw"],
            lose=team["all"]["lose"],
            last_updated=datetime.utcnow().isoformat()
        )
        session.add(standing)
    session.commit()
    print(f"📊 {league_id} standings güncellendi.")

def update_all_standings():
    leagues = [15,203, 39, 140, 135, 61, 78]
    for lid in leagues:
        update_standings(lid)


# ✅ 6. Yeni maçlara tahmin yap
def predict_new_fixtures():
    session = SessionLocal()
    fixtures = session.query(Fixture).filter(Fixture.Predicted_Label == None).all()
    if not fixtures:
        print("📭 Yeni tahminlik fixture yok.")
        return
    print(f"🔍 {len(fixtures)} fixture için tahmin yapılıyor...")
    historical_data_by_league = {
        "T1": pd.read_csv("T1_matches.csv", parse_dates=["Date"]),
        "E0": pd.read_csv("E0_matches.csv", parse_dates=["Date"]),
        "F1": pd.read_csv("F1_matches.csv", parse_dates=["Date"]),
        "D1": pd.read_csv("D1_matches.csv", parse_dates=["Date"]),
        "SP1": pd.read_csv("SP1_matches.csv", parse_dates=["Date"]),
        "I1": pd.read_csv("I1_matches.csv", parse_dates=["Date"]),
    }
    merged_df = build_features_dataframe(fixtures, historical_data_by_league)
    if merged_df.empty:
        print("❌ merged_df boş — hiç özellik hesaplanamamış.")
        return
    predictions_df = predict_from_merged_df(
        merged_df,
        best_models=load_best_models(),
        features_by_league=features_by_league
    )
    if predictions_df.empty:
        print("⚠️ Tahmin üretilemedi. Feature'lar eksik olabilir.")
    else:
        print(f"✅ {len(predictions_df)} fixture tahmini kaydedildi.")

def update_prediction_info(fixture_id):
    url = f"{BASE_URL}/predictions?fixture={fixture_id}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Prediction info alınamadı: {fixture_id}")
        return

    data = response.json().get("response")
    if not data:
        print(f"❌ Prediction info boş: {fixture_id}")
        return

    pred = data[0]["predictions"]
    teams = data[0]["teams"]

    prediction = PredictionInfo(
        FixtureID=fixture_id,
        winner=pred.get("winner", {}).get("name"),
        advice=pred.get("advice"),
        home_pct=pred.get("percent", {}).get("home"),
        draw_pct=pred.get("percent", {}).get("draw"),
        away_pct=pred.get("percent", {}).get("away"),
        form_home=pred.get("form", {}).get(teams["home"]["name"]),
        form_away=pred.get("form", {}).get(teams["away"]["name"]),
        goals_home=str(pred.get("goals", {}).get("home")),
        goals_away=str(pred.get("goals", {}).get("away")),
        h2h_home=pred.get("h2h", {}).get(teams["home"]["name"]),
        h2h_away=pred.get("h2h", {}).get(teams["away"]["name"]),
        poisson_home=pred.get("poisson_distribution", {}).get("home"),
        poisson_away=pred.get("poisson_distribution", {}).get("away"),
        last_5_home=pred.get("last_5", {}).get("home"),
        last_5_away=pred.get("last_5", {}).get("away"),
        comment=pred.get("comparison", {}).get("comment"),
        under_over=pred.get("under_over")
    )

    session.merge(prediction)
    session.commit()
    print(f"🔮 Prediction info eklendi: {fixture_id}")

def update_all_prediction_info():
    fixtures = session.query(Fixture).all()
    for f in fixtures:
        exists = session.query(PredictionInfo).filter_by(FixtureID=f.FixtureID).first()
        if exists:
            continue
        update_prediction_info(f.FixtureID)


# ✅ Ana fonksiyon
if __name__ == "__main__":
    import_upcoming_week_fixtures()
    update_fixtures_with_odds_and_xg()
    recalculate_predictions_if_features_completed()
    update_scheduled_fixtures()
    update_all_standings()
    predict_new_fixtures()
    update_all_prediction_info() 
    predict_and_save_scheduled_matches()
