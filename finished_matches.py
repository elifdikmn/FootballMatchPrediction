import json
from sqlalchemy.orm import Session
from db_setup import SessionLocal, init_db
from models import save_matches_to_db

with open("prediction_cache.json", "r", encoding="utf-8") as f:
    finished_matches = json.load(f)

init_db()
session = SessionLocal()

# Odds alanları bu dosyada varsa direkt alınır, yoksa None bırakılır
save_matches_to_db(finished_matches, odds_data={}, db_session=session)
