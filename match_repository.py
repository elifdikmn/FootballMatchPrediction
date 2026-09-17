"""Small database queries shared by Flask routes and tests."""

from models import Fixture, FixtureSyncState


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
