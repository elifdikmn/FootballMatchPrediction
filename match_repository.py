"""Small database queries shared by Flask routes and tests."""

from models import Fixture, FixtureSyncState, ModelPrediction, PredictionSnapshot


def prediction_dates(db, supported_leagues):
    dates = {}
    rows = db.query(Fixture.Date, Fixture.League).filter(
        Fixture.League.in_(supported_leagues)
    ).all()
    for day, code in rows:
        if day:
            dates.setdefault(code, set()).add(str(day)[:10])
    return {code: sorted(days) for code, days in dates.items()}


def scheduled_rows(db, supported_leagues, selected_date=None):
    query = db.query(Fixture, FixtureSyncState.kickoff_utc).outerjoin(
        FixtureSyncState, FixtureSyncState.FixtureID == Fixture.FixtureID
    ).filter(Fixture.League.in_(supported_leagues))
    if selected_date:
        query = query.filter(Fixture.Date == selected_date)
    else:
        query = query.filter(Fixture.Status == "SCHEDULED")
    return query.order_by(Fixture.Date.asc(), Fixture.FixtureID.asc()).all()


def score_value(value):
    try:
        number = float(value)
        return int(number) if number >= 0 and number.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        return None


def prediction_metadata(db, fixture_ids):
    """Latest pre-match version and its movement from the previous version."""
    fixture_ids = list(fixture_ids)
    if not fixture_ids:
        return {}
    rows = (
        db.query(PredictionSnapshot)
        .filter(
            PredictionSnapshot.FixtureID.in_(fixture_ids),
            PredictionSnapshot.prediction_type == "PRE_MATCH",
        )
        .order_by(PredictionSnapshot.FixtureID, PredictionSnapshot.version.desc())
        .all()
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row.FixtureID, []).append(row)

    # Existing deployments already have current predictions. Expose their
    # timestamp while snapshots are populated by future prediction runs.
    legacy = {
        row.FixtureID: row
        for row in db.query(ModelPrediction)
        .filter(ModelPrediction.FixtureID.in_(fixture_ids))
        .all()
    }
    output = {}
    for fixture_id in fixture_ids:
        snapshots = grouped.get(fixture_id, [])
        if snapshots:
            latest = snapshots[0]
            previous = snapshots[1] if len(snapshots) > 1 else None
            output[fixture_id] = {
                "prediction_version": latest.version,
                "prediction_updated_at": latest.predicted_at,
                "prediction_trigger": latest.trigger,
                "home_delta": latest.home_win_pct - previous.home_win_pct if previous else None,
                "draw_delta": latest.draw_pct - previous.draw_pct if previous else None,
                "away_delta": latest.away_win_pct - previous.away_win_pct if previous else None,
            }
        elif fixture_id in legacy:
            output[fixture_id] = {
                "prediction_version": 1,
                "prediction_updated_at": legacy[fixture_id].predicted_at,
                "prediction_trigger": "INITIAL",
                "home_delta": None,
                "draw_delta": None,
                "away_delta": None,
            }
    return output
