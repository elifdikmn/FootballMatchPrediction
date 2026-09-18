"""On-demand events and live predictions, sharing the central request budget."""
from datetime import datetime, timezone

from db_setup import SessionLocal
from db_utils import save_model_prediction
from live_repository import cached_events, replace_events
from models import LiveMatchState, Fixture, PredictionSnapshot
from provider_cache import FootballClient
from live_predictor import parse_live_odds, _empty_event_summary


def load_events(fixture_id, client=None, sessions=SessionLocal):
    client = client or FootballClient(sessions=sessions)
    with sessions() as db:
        state = db.get(LiveMatchState, fixture_id)
        if not state:
            # Canonical football-data.org IDs are not API-Football IDs.
            return cached_events(db, fixture_id)
        payload, updated = client.fetch('fixtures/events', {'fixture': state.provider_fixture_id}, ttl=86400 if state.status == 'FINISHED' else 300)
        if payload is not None:
            events = [{
                'minute': e.get('time', {}).get('elapsed'), 'team': e.get('team', {}).get('name'),
                'player': (e.get('player') or {}).get('name'),
                'assist': (e.get('assist') or {}).get('name'), 'type': e.get('type'),
                'detail': e.get('detail'),
            } for e in payload['response']]
            replace_events(db, fixture_id, events)
        return cached_events(db, fixture_id)


def load_live_prediction(fixture_id, models, features, client=None, sessions=SessionLocal):
    from fixture import predict_from_live_api
    client = client or FootballClient(sessions=sessions)
    now = client.clock()
    with sessions() as db:
        state = db.get(LiveMatchState, fixture_id)
        fixture = db.query(Fixture).filter_by(FixtureID=fixture_id).with_for_update().first()
        if not state or not fixture:
            return None
        provider_id = state.provider_fixture_id
        payload, timestamp = client.read('fixtures:{"live": "all"}')
        raw = next((m for m in (payload or {}).get('response', [])
                    if str(m['fixture']['id']) == provider_id), None)
        if raw and now - timestamp <= 300 and state.status == 'LIVE':
            odds_payload, odds_time = client.fetch('odds/live', {'fixture': provider_id})
            event_payload, event_time = client.fetch('fixtures/events', {'fixture': provider_id})
            odds = parse_live_odds(odds_payload or {}, provider_id)
            if odds and event_payload is not None and now - min(odds_time, event_time) <= 300:
                summary = _empty_event_summary()
                for event in event_payload['response']:
                    if event.get('type') != 'Card':
                        continue
                    side = 'home' if event['team']['id'] == raw['teams']['home']['id'] else 'away'
                    color = {'Yellow Card': 'yellow', 'Red Card': 'red', 'Second Yellow card': 'red'}.get(event.get('detail'))
                    if color:
                        summary[f'{side}_{color}_cards'] += 1
                ht = (raw.get('score') or {}).get('halftime') or {}
                match = {
                    'fixture_id': fixture_id, 'date': fixture.Date, 'league': fixture.League,
                    'home_team': fixture.HomeTeam, 'away_team': fixture.AwayTeam,
                    'elapsed': state.elapsed, 'home_goals': raw['goals']['home'],
                    'away_goals': raw['goals']['away'], 'ht_home_goals': ht.get('home') or 0,
                    'ht_away_goals': ht.get('away') or 0, 'status': 'LIVE',
                }
                result = predict_from_live_api(models, features, [match],
                    odds_loader=lambda _: odds, events_loader=lambda *args: summary)[0]
                if result['predicted_label'] is not None:
                    save_model_prediction({'FixtureID': fixture_id,
                        'Predicted_Label': result['predicted_label'],
                        'Home Win %': result['home_win_pct'], 'Draw %': result['draw_pct'],
                        'Away Win %': result['away_win_pct']}, db=db, prediction_type='LIVE', trigger='DETAIL_REQUEST')
                    db.commit()
        snapshot = db.query(PredictionSnapshot).filter_by(FixtureID=fixture_id, prediction_type='LIVE').order_by(PredictionSnapshot.version.desc()).first()
        if snapshot is None:
            return None
        return {
            'winner': {'Home Win': fixture.HomeTeam, 'Away Win': fixture.AwayTeam}.get(snapshot.predicted_label, 'Draw'),
            'comment': 'Live model prediction. Last calculated: ' + snapshot.predicted_at,
            'advice': 'Most likely outcome: ' + snapshot.predicted_label,
            'home_pct': f'{snapshot.home_win_pct:.2f}%', 'draw_pct': f'{snapshot.draw_pct:.2f}%',
            'away_pct': f'{snapshot.away_win_pct:.2f}%', 'last_5_home': None, 'last_5_away': None,
        }
