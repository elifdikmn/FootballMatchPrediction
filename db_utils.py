from sqlalchemy.orm import Session
from db_setup import SessionLocal
from models import Fixture, FixtureSyncState, ModelPrediction
from datetime import datetime
import os

def save_model_prediction(prediction: dict, db: Session = None):
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        fixture = db.query(Fixture).filter_by(FixtureID=prediction["FixtureID"]).first()
        if fixture:
            fixture.Predicted_Label = prediction["Predicted_Label"]
            fixture.HomeWinPct = prediction["Home Win %"]
            fixture.DrawPct = prediction["Draw %"]
            fixture.AwayWinPct = prediction["Away Win %"]
            fixture.LastUpdated = datetime.utcnow().isoformat()
            model_version = os.environ.get("MODEL_VERSION", "baseline-v1")
            stored = db.query(ModelPrediction).filter_by(
                FixtureID=fixture.FixtureID,
                model_version=model_version,
            ).first()
            if stored is None:
                stored = ModelPrediction(
                    FixtureID=fixture.FixtureID,
                    model_version=model_version,
                )
                db.add(stored)
            stored.predicted_label = prediction["Predicted_Label"]
            stored.home_win_pct = prediction["Home Win %"]
            stored.draw_pct = prediction["Draw %"]
            stored.away_win_pct = prediction["Away Win %"]
            stored.predicted_at = datetime.utcnow().isoformat()
            sync_state = db.get(FixtureSyncState, fixture.FixtureID)
            if sync_state:
                sync_state.needs_prediction = False
            db.commit()
            print(f"✅ Tahmin DB'ye yazıldı: Fixture {fixture.FixtureID}")
        else:
            print(f"❌ Fixture bulunamadı: {prediction['FixtureID']}")
    finally:
        if owns_session:
            db.close()
