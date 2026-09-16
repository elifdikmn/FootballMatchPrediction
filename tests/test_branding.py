import unittest
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory
from pathlib import Path
import branding

class BrandingTests(unittest.TestCase):
    def setUp(self):
        branding._cache.clear()

    @patch('branding.requests.get')
    def test_aliases_ids_and_cache(self, get):
        get.return_value = Mock(json=lambda: {'response': [{'team': {'id': 33, 'name': 'Manchester United'}}]})
        result = branding.league_branding('E0', 39, 2026, 'test-key')
        self.assertIn('Man United', result['teams'][0]['names'])
        self.assertIn('Manchester United FC', result['teams'][0]['names'])
        self.assertEqual(result['teams'][0]['logo'], 'https://media.api-sports.io/football/teams/33.png')
        self.assertEqual(result, branding.league_branding('E0', 39, 2026, 'test-key'))
        self.assertEqual(get.call_count, 1)

    @patch('branding.requests.get')
    def test_multiple_seasons_are_merged_by_team_id(self, get):
        get.side_effect = [
            Mock(json=lambda: {'response': [{'team': {'id': 1, 'name': 'Old Name', 'logo': 'old.png'}}]}),
            Mock(json=lambda: {'response': [
                {'team': {'id': 1, 'name': 'New Name', 'logo': 'new.png'}},
                {'team': {'id': 2, 'name': 'Promoted Club', 'logo': 'promoted.png'}},
            ]}),
        ]
        result = branding.league_branding('E0', 39, [2024, 2025], 'test-key')
        self.assertEqual({team['id'] for team in result['teams']}, {1, 2})
        merged = next(team for team in result['teams'] if team['id'] == 1)
        self.assertEqual(set(merged['names']), {'Old Name', 'New Name'})
        self.assertEqual(get.call_count, 2)

    def test_logo_lookup_is_league_scoped(self):
        catalogue = [
            {'code': 'E0', 'teams': [{'id': 33, 'names': ['Manchester United', 'Man United'], 'logo': 'man-u.png'}]},
            {'code': 'D1', 'teams': [{'id': 33, 'names': ['Different Club'], 'logo': 'other.png'}]},
        ]
        self.assertEqual(branding.logo_for_team(catalogue, 'E0', 'Man United'), 'man-u.png')
        self.assertIsNone(branding.logo_for_team(catalogue, 'D1', 'Man United'))

    @patch('branding.requests.get')
    def test_successful_catalogue_is_reused_from_disk(self, get):
        get.return_value = Mock(json=lambda: {'response': [
            {'team': {'id': 33, 'name': 'Manchester United', 'logo': 'man-u.png'}}
        ]})
        with TemporaryDirectory() as directory:
            cache = Path(directory) / 'branding.json'
            first = branding.branding_catalogue({'E0': 39}, [2024], 'test-key', cache)
            branding._cache.clear()
            second = branding.branding_catalogue({'E0': 39}, [2024], 'test-key', cache)
        self.assertEqual(first, second)
        self.assertEqual(get.call_count, 1)

    @patch('branding.requests.get')
    def test_provider_errors_are_not_cached(self, get):
        get.return_value = Mock(json=lambda: {'errors': {'token': 'unavailable'}, 'response': []})
        result = branding.branding_catalogue({'E0': 39, 'T1': 203}, 2026, 'test-key')
        self.assertEqual(len(result), 2)
        self.assertTrue(all(not item['teams'] for item in result))
        self.assertEqual(branding._cache, {})

if __name__ == '__main__':
    unittest.main()
