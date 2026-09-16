"""API-Football identities, shared with the iOS client (keys stay server-side)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
import requests
from team_normalizer import normalize_team_name, team_name_map

_cache = {}
_lock = Lock()


def _season_list(seasons):
    if isinstance(seasons, int):
        return [seasons]
    return sorted(set(seasons))


def league_branding(code, league_id, seasons, api_key):
    seasons = _season_list(seasons)
    key = (code, tuple(seasons))
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < 86400:
            return cached[1]

    if not api_key:
        raise ValueError('API_FOOTBALL_KEY is not configured')

    teams_by_id = {}
    loaded_seasons = []
    for season in seasons:
        response = requests.get(
            'https://v3.football.api-sports.io/teams',
            params={'league': league_id, 'season': season},
            headers={'x-apisports-key': api_key}, timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors') or not payload.get('response'):
            continue
        loaded_seasons.append(season)
        for item in payload['response']:
            team = item['team']
            raw = normalize_team_name(team['name'])
            canonical = team_name_map.get(raw, raw)
            aliases = {raw, team['name'], canonical}
            aliases.update(name for name, mapped in team_name_map.items() if mapped == canonical)
            existing = teams_by_id.setdefault(team['id'], {
                'id': team['id'],
                'names': set(),
                'logo': team.get('logo') or f"https://media.api-sports.io/football/teams/{team['id']}.png",
            })
            existing['names'].update(aliases)

    if not loaded_seasons:
        raise ValueError('Team catalogue unavailable')

    teams = [
        {**team, 'names': sorted(team['names'])}
        for team in teams_by_id.values()
    ]
    result = {'code': code, 'logo': f'https://media.api-sports.io/football/leagues/{league_id}.png', 'teams': teams}
    with _lock:
        _cache[key] = (monotonic(), result)
    return result


def branding_catalogue(leagues, seasons, api_key):
    seasons = _season_list(seasons)

    def fetch(pair):
        code, league_id = pair
        try:
            return league_branding(code, league_id, seasons, api_key)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            with _lock:
                previous = _cache.get((code, tuple(seasons)))
            return previous[1] if previous else {
                'code': code, 'logo': f'https://media.api-sports.io/football/leagues/{league_id}.png', 'teams': []}
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(fetch, leagues.items()))


def logo_for_team(catalogue, league_code, team_name):
    """Return a logo only when a league-scoped name resolves to one team ID."""
    canonical = normalize_team_name(team_name)
    matches = []
    for league in catalogue:
        if league['code'] != league_code:
            continue
        for team in league['teams']:
            if any(normalize_team_name(alias) == canonical for alias in team['names']):
                matches.append(team)
    if len({team['id'] for team in matches}) != 1:
        return None
    return matches[0]['logo']
