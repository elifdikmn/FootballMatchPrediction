"""Exercise the actual route without loading unrelated ML models or a database."""
import ast
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import mock_open, patch
from types import SimpleNamespace

class ScheduledDateTests(unittest.TestCase):
    def route(self, date, goals=None):
        tree = ast.parse(Path('app.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'scheduled_predictions')
        function.decorator_list = []
        namespace = dict(request=SimpleNamespace(args={'date': date}), datetime=datetime,
                         json=json, jsonify=lambda value: value, league_ids={'E0': 39})
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'app.py', 'exec'), namespace)
        data = {
            '1': {'FixtureID': 1, 'Date': '2026-09-15', 'League': 'E0', 'Status': 'FINISHED'},
            '2': {'FixtureID': 2, 'Date': '2026-09-17', 'League': 'E0', 'Status': 'SCHEDULED'},
        }
        if goals is not None:
            data['1'].update(HomeGoals=goals[0], AwayGoals=goals[1])
        with patch('builtins.open', mock_open(read_data=json.dumps(data))):
            return namespace['scheduled_predictions']()

    def test_past_day_includes_saved_finished_match(self):
        self.assertEqual([r['fixture_id'] for r in self.route('2026-09-15')], [1])

    def test_future_and_empty_days(self):
        self.assertEqual([r['fixture_id'] for r in self.route('2026-09-17')], [2])
        self.assertEqual(self.route('2026-09-16'), [])

    def test_default_retains_scheduled_contract(self):
        self.assertEqual([r['fixture_id'] for r in self.route(None)], [2])

    def test_invalid_date(self):
        self.assertEqual(self.route('2026-02-30')[1], 400)

    def test_final_score_preserves_scoreless_draw(self):
        row = self.route('2026-09-15', (0.0, 0.0))[0]
        self.assertEqual((row['home_goals'], row['away_goals'], row['status']), (0, 0, 'FINISHED'))

    def test_final_score_accepts_legacy_floats(self):
        row = self.route('2026-09-15', (1.0, 2.0))[0]
        self.assertEqual((row['home_goals'], row['away_goals']), (1, 2))

    def test_missing_or_invalid_score_is_not_fabricated(self):
        for goals in [(None, None), (float('nan'), float('inf')), (-1, 1.5)]:
            row = self.route('2026-09-15', goals)[0]
            self.assertIsNone(row['home_goals'])
            self.assertIsNone(row['away_goals'])
