import ast
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import mock_open, patch

class PredictionDatesTests(unittest.TestCase):
    def test_dates_are_sorted_unique_valid_and_scoped_to_supported_leagues(self):
        tree = ast.parse(Path('app.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prediction_dates')
        function.decorator_list = []
        namespace = dict(datetime=datetime, json=json, jsonify=lambda v: v, league_ids={'E0': 39})
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'app.py', 'exec'), namespace)
        rows = [{'FixtureID': 1, 'League': 'E0', 'Date': d} for d in ['2025-06-01', '2025-05-18', '2025-05-18', 'invalid']]
        rows.append({'FixtureID': 2, 'League': 'OTHER', 'Date': '2026-09-16'})
        with patch('builtins.open', mock_open(read_data=json.dumps(dict(enumerate(rows))))):
            self.assertEqual(namespace['prediction_dates'](), {'E0': ['2025-05-18', '2025-06-01']})
