from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Fixture, FixtureSyncState, ProviderRequestBudget, ProviderCache, LiveMatchState
from provider_cache import FootballClient
from live_sync import sync_live, read_live


class CentralLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + self.tmp.name + '/test.db', connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.now = datetime.now(timezone.utc)
        self.http = Mock()
        self.client = FootballClient(self.sessions, self.http, 'test', clock=lambda: self.now.timestamp())

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def match(self, status='2H'):
        return {'fixture': {'id': 123, 'date': self.now.isoformat(), 'status': {'short': status, 'elapsed': 60}},
                'league': {'id': 39}, 'teams': {'home': {'id': 1, 'name': 'Arsenal'}, 'away': {'id': 2, 'name': 'Chelsea'}},
                'goals': {'home': 2, 'away': 1}, 'score': {'halftime': {'home': 0, 'away': 0}}}

    def window(self):
        with self.sessions() as db:
            db.add(Fixture(FixtureID=1, Date=self.now.date().isoformat(), League='E0', HomeTeam='Arsenal', AwayTeam='Chelsea', Status='SCHEDULED', HomeWinPct=50))
            db.add(FixtureSyncState(FixtureID=1, provider='football-data.org', provider_fixture_id='1', kickoff_utc=self.now.isoformat(), source_hash='a', synced_at=self.now.isoformat()))
            db.commit()

    def response(self, items):
        response = Mock()
        response.json.return_value = {'response': items, 'errors': []}
        return response

    def test_detail_prediction_is_cached_separately_from_pre_match(self):
        import numpy as np
        from live_detail import load_live_prediction, load_events
        from models import PredictionSnapshot
        self.window()
        self.http.get.return_value = self.response([self.match()])
        sync_live(self.client, self.sessions, self.now)
        live_model = Mock()
        live_model.classes_ = np.array([-1, 0, 1])
        live_model.predict.return_value = np.array([1])
        live_model.predict_proba.return_value = np.array([[.1, .2, .7]])
        odds = {'fixture': {'id': 123}, 'status': {}, 'odds': [
            {'name': 'Fulltime Result', 'values': [{'value': name, 'odd': odd}
                for name, odd in [('Home', '1.5'), ('Draw', '4'), ('Away', '7')]]}]}
        self.http.get.side_effect = [self.response([odds]), self.response([])]
        result = load_live_prediction(1, {'E0': live_model}, ['HomeProb'], self.client, self.sessions)
        self.assertEqual(result['home_pct'], '70.00%')
        load_live_prediction(1, {'E0': live_model}, ['HomeProb'], self.client, self.sessions)
        self.assertEqual(load_events(1, self.client, self.sessions), [])
        self.assertEqual(self.http.get.call_count, 3)  # one score, one odds, one events
        with self.sessions() as db:
            self.assertEqual(db.get(Fixture, 1).HomeWinPct, 50)
            self.assertEqual(db.query(PredictionSnapshot).count(), 1)

    def test_unmapped_detail_never_sends_foreign_provider_id(self):
        from live_detail import load_events
        self.assertEqual(load_events(987, self.client, self.sessions), [])
        self.http.get.assert_not_called()

    def test_shared_cache_empty_responses_and_budget(self):
        self.http.get.return_value = self.response([])
        self.client.fetch('fixtures', {'live': 'all'}, purpose='live')
        FootballClient(self.sessions, self.http, 'test', clock=self.client.clock).fetch('fixtures', {'live': 'all'}, purpose='live')
        self.http.get.assert_called_once()
        with self.sessions() as db:
            self.assertEqual(db.query(ProviderRequestBudget).one().used, 1)

    def test_atomic_budget_across_concurrent_clients(self):
        with self.sessions() as db:
            db.add(ProviderRequestBudget(day=self.now.date().isoformat(), used=97))
            db.commit()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.client.reserve('standings'), range(12)))
        self.assertEqual(sum(results), 3)
        self.assertFalse(self.client.reserve('live'))
        self.assertFalse(self.client.reserve('detail'))

    def test_no_call_outside_match_hours(self):
        self.assertEqual(sync_live(self.client, self.sessions, self.now)['status'], 'outside_match_window')
        self.http.get.assert_not_called()

    def test_worker_writes_scores_but_never_fetches_odds_or_events(self):
        self.window()
        self.http.get.return_value = self.response([self.match()])
        sync_live(self.client, self.sessions, self.now)
        self.http.get.assert_called_once()
        self.assertEqual(self.http.get.call_args.kwargs['params'], {'live': 'all'})
        with self.sessions() as db:
            self.assertEqual(read_live(db)[0]['score'], '2 - 1')
            self.assertEqual(db.get(Fixture, 1).HomeWinPct, 50)

    def test_final_score_is_verified_not_inferred_from_disappearance(self):
        self.window()
        self.http.get.return_value = self.response([self.match()])
        sync_live(self.client, self.sessions, self.now)
        with self.sessions() as db:
            row = db.query(ProviderCache).filter_by(key='fixtures:{"live": "all"}').one()
            row.updated_at = 0
            db.commit()
        self.http.get.side_effect = [self.response([]), self.response([self.match('FT')])]
        sync_live(self.client, self.sessions, self.now)
        with self.sessions() as db:
            self.assertEqual(read_live(db), [])
            self.assertEqual(db.get(Fixture, 1).Status, 'FINISHED')
            self.assertEqual(db.get(Fixture, 1).HomeGoals, 2)

    def test_exhausted_budget_returns_cache_without_http(self):
        with self.sessions() as db:
            db.add(ProviderRequestBudget(day=self.now.date().isoformat(), used=80))
            db.commit()
        self.assertEqual(self.client.fetch('odds/live', {'fixture': '123'}), (None, 0))
        self.http.get.assert_not_called()

    def test_concurrent_fetches_share_one_request(self):
        self.http.get.return_value = self.response([])
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.client.fetch('fixtures/events', {'fixture': '123'}), range(8)))
        self.http.get.assert_called_once()

    def test_failed_provider_request_is_counted_and_retains_cache(self):
        import requests
        self.http.get.side_effect = requests.Timeout()
        self.assertEqual(self.client.fetch('fixtures', {'live': 'all'}, purpose='live'), (None, 0))
        with self.sessions() as db:
            self.assertEqual(db.query(ProviderRequestBudget).one().used, 1)


if __name__ == '__main__':
    unittest.main()
