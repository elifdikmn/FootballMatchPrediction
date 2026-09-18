"""Central score worker. App list requests never call the provider."""
from datetime import datetime, timezone, timedelta
import json

from db_setup import SessionLocal, init_db
from fixture_sync import normalize_status
from live_predictor import API_FOOTBALL_LEAGUES
from live_repository import persist_live_matches
from models import Fixture, FixtureSyncState, LiveMatchState, ProviderCache, PredictionSnapshot
from provider_cache import FootballClient, insert_missing
from team_normalizer import normalize_team_name

LIVE_KEY = 'live-list'


def in_match_window(db, now):
    rows = db.query(FixtureSyncState.kickoff_utc).join(
        Fixture, Fixture.FixtureID == FixtureSyncState.FixtureID
    ).filter(Fixture.League.in_(API_FOOTBALL_LEAGUES.values()),
             Fixture.Status.in_(['SCHEDULED', 'LIVE', 'AWAITING_RESULT'])).all()
    for (value,) in rows:
        kickoff = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        if kickoff - timedelta(minutes=5) <= now <= kickoff + timedelta(hours=4):
            return True
    return False


def parse_match(item):
    code = API_FOOTBALL_LEAGUES.get(item.get('league', {}).get('id'))
    if not code:
        return None
    goals = item.get('goals') or {}
    fixture = item['fixture']
    return {
        'fixture_id': fixture['id'], 'date': fixture['date'][:10], 'league': code,
        'home_team': normalize_team_name(item['teams']['home']['name']),
        'away_team': normalize_team_name(item['teams']['away']['name']),
        'score': f"{goals.get('home') if goals.get('home') is not None else '?'} - {goals.get('away') if goals.get('away') is not None else '?'}",
        'elapsed': fixture['status'].get('elapsed'),
        'status': normalize_status(fixture['status']['short']),
        'predicted_label': None, 'home_win_pct': None, 'draw_pct': None, 'away_win_pct': None,
    }


def sync_live(client=None, sessions=SessionLocal, now=None):
    client = client or FootballClient(sessions=sessions)
    now = now or datetime.now(timezone.utc)
    if not client.key:
        return {'status': 'missing_api_football_key'}
    with sessions() as db:
        if not in_match_window(db, now):
            return {'status': 'outside_match_window'}
    payload, updated = client.fetch('fixtures', {'live': 'all'}, purpose='live')
    if payload is None or now.timestamp() - updated > 300:
        return {'status': 'unavailable_or_budget_exhausted'}
    matches = [m for item in payload['response'] if (m := parse_match(item)) and m['status'] == 'LIVE']
    with sessions() as db:
        old = db.get(ProviderCache, LIVE_KEY)
        previous = old.payload if old and old.payload else []
        matches = persist_live_matches(db, matches)
        ids = {m.get('provider_fixture_id', m['fixture_id']) for m in matches}
        missing = [m for m in previous if m.get('provider_fixture_id', m['fixture_id']) not in ids]
        # Disappearance alone is not proof of full time.
        for match in missing:
            row = db.get(Fixture, match['fixture_id'])
            state = db.get(LiveMatchState, match['fixture_id'])
            if row and row.Status == 'LIVE':
                row.Status = 'AWAITING_RESULT'
            if state:
                state.status = 'AWAITING_RESULT'
        insert_missing(db, ProviderCache, {'key': LIVE_KEY, 'updated_at': 0, 'lease_until': 0})
        row = db.get(ProviderCache, LIVE_KEY)
        row.payload, row.updated_at = matches, updated
        db.commit()
        pending = db.query(LiveMatchState).filter_by(status='AWAITING_RESULT').all()
        missing_ids = [s.provider_fixture_id for s in pending][:20]
    if missing_ids:
        final, timestamp = client.fetch('fixtures', {'ids': '-'.join(sorted(missing_ids))}, purpose='live')
        if final and now.timestamp() - timestamp <= 300:
            finished = [m for item in final['response'] if (m := parse_match(item)) and m['status'] != 'LIVE']
            with sessions() as db:
                persist_live_matches(db, finished)
    return {'status': 'updated', 'matches': len(matches)}


def read_live(db):
    row = db.get(ProviderCache, LIVE_KEY)
    if not row:
        return []
    # Expired data is not presented as a currently live game.
    if datetime.now(timezone.utc).timestamp() - row.updated_at > 900:
        return []
    output = []
    for raw in row.payload or []:
        match = dict(raw)
        snapshot = db.query(PredictionSnapshot).filter_by(
            FixtureID=match['fixture_id'], prediction_type='LIVE'
        ).order_by(PredictionSnapshot.version.desc()).first()
        if snapshot:
            for key in ('predicted_label', 'home_win_pct', 'draw_pct', 'away_win_pct'):
                match[key] = getattr(snapshot, key)
            match['prediction_updated_at'] = snapshot.predicted_at
        match['updated_at'] = datetime.fromtimestamp(row.updated_at, timezone.utc).isoformat()
        output.append(match)
    return output


if __name__ == '__main__':
    init_db()
    print(json.dumps(sync_live()))
