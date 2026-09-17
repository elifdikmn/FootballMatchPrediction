"""CLI entry point used locally and by GitHub Actions."""

import argparse
from datetime import datetime, timezone

import pandas as pd

from config import features_by_league
from db_setup import SessionLocal, init_db
from feature_engineering import (
    add_all_features_to_merged_df,
    add_latest_elo_features_to_fixtures,
    add_latest_elo_to_fixtures,
)
from fixture_sync import sync_all
from models import Fixture, FixtureSyncState
from prediction_pipeline import load_best_models, predict_from_merged_df


def _historical_data():
    return {
        code: pd.read_csv(f"{code}_matches.csv", parse_dates=["Date"])
        for code in features_by_league
    }


def predict_pending_fixtures() -> int:
    with SessionLocal() as db:
        fixtures = (
            db.query(Fixture)
            .join(FixtureSyncState, FixtureSyncState.FixtureID == Fixture.FixtureID)
            .filter(
                FixtureSyncState.needs_prediction.is_(True),
                Fixture.Status == "SCHEDULED",
                Fixture.Date >= datetime.now(timezone.utc).date().isoformat(),
            )
            .all()
        )

        if not fixtures:
            return 0

        frame = pd.DataFrame(
            [
                {
                    "FixtureID": fixture.FixtureID,
                    "Date": fixture.Date,
                    "League": fixture.League,
                    "HomeTeam": fixture.HomeTeam,
                    "AwayTeam": fixture.AwayTeam,
                    "B365H": fixture.B365H,
                    "B365D": fixture.B365D,
                    "B365A": fixture.B365A,
                }
                for fixture in fixtures
            ]
        )
        historical = _historical_data()
        frame = add_latest_elo_to_fixtures(frame, historical)
        frame = add_latest_elo_features_to_fixtures(frame, historical)
        frame = add_all_features_to_merged_df(frame, historical)
        # The current non-Turkish models were trained with xG. Until a free-data
        # model is retrained, explicit neutral values are safer than missing data.
        for column in ("HxG", "AxG", "xG_diff"):
            if column not in frame:
                frame[column] = 0.0
        predictions = predict_from_merged_df(
            frame,
            load_best_models(),
            features_by_league,
            db=db,
        )
        db.commit()
        return len(predictions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "refresh"), default="refresh")
    parser.add_argument("--skip-predictions", action="store_true")
    args = parser.parse_args()

    init_db()
    totals = sync_all(args.mode)
    prediction_count = 0 if args.skip_predictions else predict_pending_fixtures()
    print(
        "Fixture sync complete:",
        {**totals, "predictions": prediction_count, "mode": args.mode},
    )


if __name__ == "__main__":
    main()
