import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Fixture, Event
import os
from db_setup import engine
from db_setup import SessionLocal
session = SessionLocal()

def init_db():
    Base.metadata.create_all(bind=engine)


from datetime import datetime

def load_prediction_cache(file_path='prediction_cache.json'):
    if not os.path.exists(file_path):
        print(f"⚠️ Dosya bulunamadı: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Fixture sayısı: {len(data)}")

    updated = 0
    inserted = 0

    for fixture_id, info in data.items():
        fixture_id = int(fixture_id)
        existing = session.query(Fixture).filter_by(FixtureID=fixture_id).first()

        if existing:
            # Değişiklik var mı kontrol et
            has_changed = (
                existing.Status != info.get("Status") or
                existing.HomeGoals != info.get("HomeGoals") or
                existing.AwayGoals != info.get("AwayGoals")
            )
            if has_changed:
                existing.Status = info.get("Status")
                existing.HomeGoals = info.get("HomeGoals")
                existing.AwayGoals = info.get("AwayGoals")
                existing.LastUpdated = datetime.utcnow().isoformat()
                updated += 1
        else:
            # Yeni ekle
            new_fixture = Fixture(
                FixtureID=fixture_id,
                Date=info.get("Date"),
                League=info.get("League"),
                HomeTeam=info.get("HomeTeam"),
                AwayTeam=info.get("AwayTeam"),
                Predicted_Label=info.get("Predicted_Label"),
                HomeWinPct=info.get("Home Win %"),
                DrawPct=info.get("Draw %"),
                AwayWinPct=info.get("Away Win %"),
                HomeGoals=info.get("HomeGoals"),
                AwayGoals=info.get("AwayGoals"),
                Status=info.get("Status"),
                LastUpdated=datetime.utcnow().isoformat()
            )
            session.add(new_fixture)
            inserted += 1
            print(f"İşleniyor: {fixture_id}, Status: {info.get('Status')}")


    session.commit()
    print(f"{inserted} yeni fixture eklendi, {updated} fixture güncellendi.")

def load_events_cache(file_path='events_cache.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for fixture_id, events in data.items():
        for ev in events:
            event = Event(
                FixtureID=int(fixture_id),
                minute=ev.get("minute"),
                team=ev.get("team"),
                player=ev.get("player"),
                type=ev.get("type"),
                detail=ev.get("detail"),
                assist=ev.get("assist")
            )
            session.add(event)
            count += 1

    session.commit()
    print(f"✅ {count} event verisi yüklendi.")



if __name__ == "__main__":
    load_prediction_cache()
    load_events_cache()  

