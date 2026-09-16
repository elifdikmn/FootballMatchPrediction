import unittest
from unittest.mock import Mock, patch
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
    def test_provider_errors_are_not_cached(self, get):
        get.return_value = Mock(json=lambda: {'errors': {'token': 'unavailable'}, 'response': []})
        result = branding.branding_catalogue({'E0': 39, 'T1': 203}, 2026, 'test-key')
        self.assertEqual(len(result), 2)
        self.assertTrue(all(not item['teams'] for item in result))
        self.assertEqual(branding._cache, {})

if __name__ == '__main__':
    unittest.main()
