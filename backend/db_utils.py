from sqlalchemy.orm import Session
from db_setup import SessionLocal
from models import Fixture, FixtureSyncState, ModelPrediction, PredictionSnapshot
from datetime import datetime, timezone
import os


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _same_probabilities(snapshot, prediction):
    return snapshot is not None and all(
        abs(float(current) - float(incoming)) < 0.005
        for current, incoming in (
            (snapshot.home_win_pct, prediction["Home Win %"]),
            (snapshot.draw_pct, prediction["Draw %"]),
            (snapshot.away_win_pct, prediction["Away Win %"]),
        )
    ) and snapshot.predicted_label == prediction["Predicted_Label"]


def save_prediction_snapshot(
    prediction: dict,
    db: Session,
    prediction_type: str = "PRE_MATCH",
    trigger: str = "INITIAL",
):
    prediction_type = prediction_type.upper()
    latest = (
        db.query(PredictionSnapshot)
        .filter_by(FixtureID=prediction["FixtureID"], prediction_type=prediction_type)
        .order_by(PredictionSnapshot.version.desc())
        .first()
    )
    model_version = os.environ.get("MODEL_VERSION", "baseline-v1")
    if _same_probabilities(latest, prediction) and latest.model_version == model_version:
        return latest

    snapshot = PredictionSnapshot(
        FixtureID=prediction["FixtureID"],
        prediction_type=prediction_type,
        version=(latest.version + 1) if latest else 1,
        trigger=trigger,
        model_version=model_version,
        predicted_label=prediction["Predicted_Label"],
        home_win_pct=prediction["Home Win %"],
        draw_pct=prediction["Draw %"],
        away_win_pct=prediction["Away Win %"],
        feature_snapshot=prediction.get("feature_snapshot"),
        predicted_at=_utc_now(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def save_model_prediction(
    prediction: dict,
    db: Session = None,
    prediction_type: str = "PRE_MATCH",
    trigger: str = "INITIAL",
):
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        fixture = db.query(Fixture).filter_by(FixtureID=prediction["FixtureID"]).first()
        if fixture:
            if prediction_type.upper() == "LIVE":
                save_prediction_snapshot(prediction, db, "LIVE", trigger)
                if owns_session:
                    db.commit()
                return

            fixture.Predicted_Label = prediction["Predicted_Label"]
            fixture.HomeWinPct = prediction["Home Win %"]
            fixture.DrawPct = prediction["Draw %"]
            fixture.AwayWinPct = prediction["Away Win %"]
            fixture.LastUpdated = _utc_now()
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
            stored.predicted_at = _utc_now()
            save_prediction_snapshot(prediction, db, "PRE_MATCH", trigger)
            sync_state = db.get(FixtureSyncState, fixture.FixtureID)
            if sync_state:
                sync_state.needs_prediction = False
            if owns_session:
                db.commit()
            else:
                db.flush()
            print(f"✅ Tahmin DB'ye yazıldı: Fixture {fixture.FixtureID}")
        else:
            print(f"❌ Fixture bulunamadı: {prediction['FixtureID']}")
    finally:
        if owns_session:
            db.close()
