"""Reconcile API-Football live IDs with stored fixtures and retain live snapshots."""

from datetime import datetime, timezone
import hashlib

from db_utils import save_model_prediction
from models import Event, Fixture, FixtureSyncState, LiveMatchState, PredictionSnapshot
from team_normalizer import team_identity


FINISHED_STATUSES = {"FINISHED", "FT", "AET", "PEN"}


def _score_values(score):
    try:
        home, away = [int(value.strip()) for value in score.replace("–", "-").split("-")]
        return home, away
    except (AttributeError, TypeError, ValueError):
        return None, None


def _canonical_fixture(db, match):
    existing = db.query(LiveMatchState).filter_by(provider_fixture_id=str(match['fixture_id'])).first()
    linked = db.get(Fixture, existing.FixtureID) if existing else None
    day = str(match.get("date") or "")[:10]
    home = team_identity(match.get("home_team"))
    away = team_identity(match.get("away_team"))
    candidates = db.query(Fixture).filter_by(League=match.get("league"), Date=day).all()
    matches = [
        fixture for fixture in candidates
        if team_identity(fixture.HomeTeam) == home
        and team_identity(fixture.AwayTeam) == away
    ]
    if not matches:
        return linked, existing

    def preference(fixture):
        return (
            db.get(FixtureSyncState, fixture.FixtureID) is not None,
            (fixture.Status or "").upper() in FINISHED_STATUSES,
            fixture.Predicted_Label is not None,
            fixture.FixtureID < 2_000_000_000,
        )

    return max(matches, key=preference), existing


def _rebind_live_state(db, existing, fixture, provider_fixture_id, now):
    """Move a provider mapping off an old synthetic duplicate."""
    if existing is None or existing.FixtureID == fixture.FixtureID:
        return db.get(LiveMatchState, fixture.FixtureID)

    old_fixture_id = existing.FixtureID
    db.delete(existing)
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
    db.query(Event).filter_by(FixtureID=old_fixture_id).update(
        {Event.FixtureID: fixture.FixtureID}, synchronize_session=False
    )
    if not db.query(PredictionSnapshot).filter_by(
        FixtureID=fixture.FixtureID, prediction_type="LIVE"
    ).first():
        db.query(PredictionSnapshot).filter_by(
            FixtureID=old_fixture_id, prediction_type="LIVE"
        ).update({PredictionSnapshot.FixtureID: fixture.FixtureID}, synchronize_session=False)
    else:
        db.query(PredictionSnapshot).filter_by(
            FixtureID=old_fixture_id, prediction_type="LIVE"
        ).delete(synchronize_session=False)
    orphan = db.get(Fixture, old_fixture_id)
    if orphan is not None and db.get(FixtureSyncState, old_fixture_id) is None:
        orphan.Status = "DUPLICATE"
    return state


def persist_live_matches(db, matches):
    """Store the latest live state without mutating the pre-match prediction."""
    now = datetime.now(timezone.utc).isoformat()
    output = []
    for raw in matches:
        match = dict(raw)
        provider_fixture_id = str(match["fixture_id"])
        fixture, existing_state = _canonical_fixture(db, match)
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

        # Never let a delayed live-provider response roll a final result back
        # to LIVE or make it appear as a second match.
        if (
            (fixture.Status or "").upper() in FINISHED_STATUSES
            and (match.get("status") or "").upper() == "LIVE"
        ):
            if existing_state is not None:
                existing_state.status = "FINISHED"
                existing_state.updated_at = now
                orphan = db.get(Fixture, existing_state.FixtureID)
                if orphan is not None and orphan.FixtureID != fixture.FixtureID:
                    orphan.Status = "DUPLICATE"
            continue

        state = _rebind_live_state(db, existing_state, fixture, provider_fixture_id, now)
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
