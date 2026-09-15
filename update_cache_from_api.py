import json
import requests
from datetime import datetime
import time
import pandas as pd
from config import API_FOOTBALL_KEY, features_by_league
from fixture import get_combined_fixtures_with_odds, get_current_season
from feature_engineering import (
    add_latest_elo_to_fixtures,
    add_latest_elo_features_to_fixtures,
    add_all_features_to_merged_df,
)
from prediction_pipeline import predict_from_merged_df, load_best_models
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

# Dosya yolları
FIXTURE_CACHE = "upcoming_fixtures_cache.json"
PREDICTION_CACHE = "prediction_cache.json"
EVENTS_CACHE = "events_cache.json"

from datetime import datetime

# sync_events_cache_from_db.py

import json
from sqlalchemy.orm import sessionmaker
from db_setup import SessionLocal
from models import Event

def sync_events_cache(file_path="events_cache.json"):
    session = SessionLocal()
    all_events = session.query(Event).all()

    cache = {}
    for ev in all_events:
        fid = str(ev.FixtureID)
        if fid not in cache:
            cache[fid] = []
        cache[fid].append({
            "minute": ev.minute,
            "team": ev.team,
            "player": ev.player,
            "type": ev.type,
            "detail": ev.detail,
            "assist": ev.assist
        })

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f"✅ events_cache.json veritabanından güncellendi. Toplam {len(cache)} maç.")

if __name__ == "__main__":
    sync_events_cache()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def fetch_fixture_info(fixture_id):
    url = f"{BASE_URL}/fixtures?id={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        response = res.json().get("response", [])
        return response[0] if response else None
    return None

import os

def save_fixtures_to_cache(league_id, season=None, file_path="upcoming_fixtures_cache.json"):
    season = season or get_current_season()
    headers = HEADERS

    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={season}&status=NS"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        print(f"❌ Fixture API hatası (lig: {league_id})")
        return

    response = res.json().get("response", [])

    # 📥 Önce mevcut cache’i oku (varsa)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    new_count = 0

    for item in response:
        fixture_id = str(item["fixture"]["id"])  # 🔑 string key olsun
        if fixture_id in cache:
            continue  # zaten varsa geç
        cache[fixture_id] = {
            "FixtureID": int(fixture_id),
            "Date": item["fixture"]["date"],
            "League": item["league"]["name"],
            "HomeTeam": item["teams"]["home"]["name"],
            "AwayTeam": item["teams"]["away"]["name"]
        }
        new_count += 1

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"📦 {new_count} yeni fikstür cache'e eklendi.")

def fetch_fixture_events(fixture_id):
    url = f"{BASE_URL}/fixtures/events?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return res.json().get("response", [])
    return []

def update_prediction_and_events():
    pred_cache = load_json(PREDICTION_CACHE)
    event_cache = load_json(EVENTS_CACHE)

    updated = 0

    for fixture_id, data in pred_cache.items():
        if data.get("Status") != "SCHEDULED":
            continue

        fixture = fetch_fixture_info(fixture_id)
        if not fixture:
            continue

        status = fixture["fixture"]["status"]["short"]
        if status in ("FT", "AET", "PEN"):  # Maç bitti
            home_goals = fixture["goals"]["home"]
            away_goals = fixture["goals"]["away"]

            # 🔁 Güncelle
            pred_cache[fixture_id]["Status"] = "FINISHED"
            pred_cache[fixture_id]["HomeGoals"] = home_goals
            pred_cache[fixture_id]["AwayGoals"] = away_goals

            # 📝 Event’leri ekle
            events = fetch_fixture_events(fixture_id)
            event_list = []
            seen = set()
            for ev in events:
                key = f"{ev['time']['elapsed']}-{ev['player']['name']}"
                if key in seen:
                    continue
                seen.add(key)
                event_list.append({
                    "minute": ev["time"]["elapsed"],
                    "team": ev["team"]["name"],
                    "player": ev["player"]["name"],
                    "type": ev["type"],
                    "detail": ev["detail"],
                    "assist": ev["assist"]["name"] if ev["assist"] else None
                })
            event_cache[fixture_id] = event_list

            print(f"✅ Güncellendi: {fixture_id}")
            updated += 1

            time.sleep(1.5)  # API sınırına karşı biraz bekle

    save_json(PREDICTION_CACHE, pred_cache)
    save_json(EVENTS_CACHE, event_cache)

    print(f"\n🎉 Toplam {updated} maç güncellendi.")

def update_prediction_cache_from_own_models():
    """Populate PREDICTION_CACHE with predictions from this project's own
    trained models (best_models.pkl + engineered features), instead of
    relaying api-sports.io's own /predictions endpoint."""
    best_models = load_best_models()
    historical_data_by_league = {
        code: pd.read_csv(f"{code}_matches.csv", parse_dates=["Date"])
        for code in features_by_league
    }

    prediction_cache = load_json(PREDICTION_CACHE)

    combined_df = get_combined_fixtures_with_odds()
    scheduled_df = combined_df[combined_df["Status"] == "SCHEDULED"].reset_index(drop=True)

    if scheduled_df.empty:
        print("🔕 Tahmin edilecek planlanmış maç yok.")
        return

    scheduled_df = add_latest_elo_to_fixtures(scheduled_df, historical_data_by_league)
    scheduled_df = add_latest_elo_features_to_fixtures(scheduled_df, historical_data_by_league)
    scheduled_df = add_all_features_to_merged_df(scheduled_df, historical_data_by_league)

    predicted_df = predict_from_merged_df(scheduled_df, best_models, features_by_league)

    updated = 0
    for _, row in predicted_df.iterrows():
        fixture_id = str(int(row["FixtureID"]))
        prediction_cache[fixture_id] = {
            "FixtureID": int(row["FixtureID"]),
            "HomeTeam": row["HomeTeam"],
            "AwayTeam": row["AwayTeam"],
            "Date": row["Date"],
            "League": row["League"],
            "Predicted_Label": row["Predicted_Label"],
            "Home Win %": row["Home Win %"],
            "Draw %": row["Draw %"],
            "Away Win %": row["Away Win %"],
            "Status": "SCHEDULED",
        }
        updated += 1

    save_json(PREDICTION_CACHE, prediction_cache)
    print(f"\n✅ {updated} tahmin (kendi modelimizle) prediction_cache'e kaydedildi.")

def fix_prediction_cache_dates(file_path="prediction_cache.json"):
    import json

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for item in data.values():
        date_str = item.get("Date")
        if not date_str:
            continue
        try:
            # Her türlü date formatını parse etmeye çalış
            parsed = datetime.fromisoformat(date_str.replace("Z", "").replace("T", " "))
            item["Date"] = parsed.strftime("%Y-%m-%d")
            updated += 1
        except Exception:
            print(f"⚠️ Formatlanamayan tarih: {date_str}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"✅ {updated} tarih normalize edildi.")
def deduplicate_events_cache(file_path="events_cache.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    from collections import defaultdict
    cleaned = defaultdict(list)

    for fixture_id, events in data.items():
        seen = set()
        for e in events:
            key = f"{e['minute']}-{e['player']}"
            if key in seen:
                continue
            seen.add(key)
            cleaned[fixture_id].append(e)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print("✅ events_cache.json temizlendi.")


if __name__ == "__main__":
    league_ids = [15,5,32,39,203,78]  # Premier League, Türkiye, Almanya, vs.
    for league_id in league_ids:
        save_fixtures_to_cache(league_id)
    update_prediction_and_events()
    update_prediction_cache_from_own_models()
    fix_prediction_cache_dates()
    deduplicate_events_cache()
    
