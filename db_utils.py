from sqlalchemy.orm import Session
from db_setup import SessionLocal
from models import Fixture
from datetime import datetime

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
            db.commit()
            print(f"✅ Tahmin DB'ye yazıldı: Fixture {fixture.FixtureID}")
        else:
            print(f"❌ Fixture bulunamadı: {prediction['FixtureID']}")
    finally:
        if owns_session:
            db.close()
