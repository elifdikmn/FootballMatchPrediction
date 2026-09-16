"""Exercise the actual route without loading unrelated ML models or a database."""
import ast
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import mock_open, patch
from types import SimpleNamespace

class ScheduledDateTests(unittest.TestCase):
    def route(self, date):
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
