"""API-Football identities, shared with the iOS client (keys stay server-side)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
import requests
from team_normalizer import normalize_team_name, team_name_map

_cache = {}
_lock = Lock()


def league_branding(code, league_id, season, api_key):
    key = (code, season)
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < 86400:
            return cached[1]
    response = requests.get(
        'https://v3.football.api-sports.io/teams',
        params={'league': league_id, 'season': season},
        headers={'x-apisports-key': api_key}, timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get('errors') or not payload.get('response'):
        raise ValueError('Team catalogue unavailable')
    teams = []
    for item in payload['response']:
        team = item['team']
        raw = normalize_team_name(team['name'])
        canonical = team_name_map.get(raw, raw)
        aliases = {raw, team['name'], canonical}
        aliases.update(name for name, mapped in team_name_map.items() if mapped == canonical)
        teams.append({'id': team['id'], 'names': sorted(aliases),
                      'logo': f"https://media.api-sports.io/football/teams/{team['id']}.png"})
    result = {'code': code, 'logo': f'https://media.api-sports.io/football/leagues/{league_id}.png', 'teams': teams}
    with _lock:
        _cache[key] = (monotonic(), result)
    return result


def branding_catalogue(leagues, season, api_key):
    def fetch(pair):
        code, league_id = pair
        try:
            return league_branding(code, league_id, season, api_key)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            with _lock:
                previous = _cache.get((code, season))
            return previous[1] if previous else {
                'code': code, 'logo': f'https://media.api-sports.io/football/leagues/{league_id}.png', 'teams': []}
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(fetch, leagues.items()))
