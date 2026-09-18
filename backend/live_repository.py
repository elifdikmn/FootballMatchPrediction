"""Reconcile API-Football live IDs with stored fixtures and retain live snapshots."""

from datetime import datetime, timezone
import hashlib

from db_utils import save_model_prediction
from models import Event, Fixture, LiveMatchState
from team_normalizer import normalize_team_name


def _score_values(score):
    try:
        home, away = [int(value.strip()) for value in score.replace("–", "-").split("-")]
        return home, away
    except (AttributeError, TypeError, ValueError):
        return None, None


def _canonical_fixture(db, match):
    existing = db.query(LiveMatchState).filter_by(provider_fixture_id=str(match['fixture_id'])).first()
    if existing:
        return db.get(Fixture, existing.FixtureID)
    day = str(match.get("date") or "")[:10]
    home = normalize_team_name(match.get("home_team") or "")
    away = normalize_team_name(match.get("away_team") or "")
    candidates = db.query(Fixture).filter_by(League=match.get("league"), Date=day).all()
    return next(
        (
            fixture for fixture in candidates
            if normalize_team_name(fixture.HomeTeam) == home
            and normalize_team_name(fixture.AwayTeam) == away
        ),
        None,
    )


def persist_live_matches(db, matches):
    """Store the latest live state without mutating the pre-match prediction."""
    now = datetime.now(timezone.utc).isoformat()
    output = []
    for raw in matches:
        match = dict(raw)
        provider_fixture_id = str(match["fixture_id"])
        fixture = _canonical_fixture(db, match)
        if fixture is None:
            # A dedicated deterministic namespace avoids mixing provider IDs.
            identity = int(hashlib.sha256(('api-football:' + provider_fixture_id).encode()).hexdigest()[:12], 16)
            fixture_id = 2_000_000_000 + identity % 100_000_000
            if db.get(Fixture, fixture_id) is not None:
                continue
            fixture = Fixture(FixtureID=fixture_id, Date=str(match.get('date') or '')[:10],
                              League=match['league'], HomeTeam=match['home_team'], AwayTeam=match['away_team'])
            db.add(fixture)
            db.flush()

        state = db.get(LiveMatchState, fixture.FixtureID)
        if state is None:
            state = LiveMatchState(
                FixtureID=fixture.FixtureID,
                provider_fixture_id=provider_fixture_id,
                league=fixture.League,
                status="LIVE",
                updated_at=now,
            )
            db.add(state)
        state.provider_fixture_id = provider_fixture_id
        state.league = fixture.League
        state.score = match.get("score")
        state.elapsed = match.get("elapsed")
        state.status = match.get("status") or "LIVE"
        state.updated_at = now

        home_goals, away_goals = _score_values(match.get("score"))
        fixture.Status = match.get("status") or "LIVE"
        fixture.HomeGoals = home_goals
        fixture.AwayGoals = away_goals
        fixture.LastUpdated = now

        if all(match.get(key) is not None for key in (
            "predicted_label", "home_win_pct", "draw_pct", "away_win_pct"
        )):
            save_model_prediction({
                "FixtureID": fixture.FixtureID,
                "Predicted_Label": match["predicted_label"],
                "Home Win %": match["home_win_pct"],
                "Draw %": match["draw_pct"],
                "Away Win %": match["away_win_pct"],
            }, db=db, prediction_type="LIVE", trigger="LIVE_STATE")
        match["provider_fixture_id"] = int(provider_fixture_id)
        match["fixture_id"] = fixture.FixtureID
        output.append(match)
    db.commit()
    return output


def replace_events(db, fixture_id, events):
    db.query(Event).filter_by(FixtureID=fixture_id).delete()
    for item in events:
        db.add(Event(
            FixtureID=fixture_id,
            minute=item.get("minute"),
            team=item.get("team"),
            player=item.get("player"),
            assist=item.get("assist"),
            type=item.get("type") or "Event",
            detail=item.get("detail") or "",
        ))
    db.commit()


def cached_events(db, fixture_id):
    return [{
        "minute": row.minute,
        "team": row.team,
        "player": row.player,
        "assist": row.assist,
        "type": row.type,
        "detail": row.detail,
    } for row in db.query(Event).filter_by(FixtureID=fixture_id).order_by(Event.minute).all()]
