import requests
import pandas as pd
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import json
import os
import hashlib
from live_predictor import get_live_fixtures, get_live_events_summary, get_live_odds_from_api_football, get_htr, normalize_odds

from prediction_pipeline import predict_from_merged_df
from feature_engineering import (
    add_latest_elo_to_fixtures,
    add_latest_elo_features_to_fixtures,
    add_all_features_to_merged_df
)
xg_data = pd.read_csv("future_xg_matches.csv")
xg_data = xg_data.rename(columns={
    "xg_home": "HxG",
    "xg_away": "AxG",
    "home_team": "HomeTeam",
    "away_team": "AwayTeam",
    "date": "Date"
})
xg_data["Date"] = pd.to_datetime(xg_data["Date"], errors="coerce").dt.date
def merge_xg_to_fixtures(fixtures_df, xg_df):
    fixtures_df["HomeTeam"] = fixtures_df["HomeTeam"].str.strip()
    fixtures_df["AwayTeam"] = fixtures_df["AwayTeam"].str.strip()
    fixtures_df["Date"] = pd.to_datetime(fixtures_df["Date"]).dt.date
    merged = fixtures_df.merge(
        xg_df,
        on=["Date", "HomeTeam", "AwayTeam"],
        how="left"
        )
        # merge sonrası varsa _y olanları al (_x olanlar genellikle fixtures_df içeriği olur)
    if "HxG_y" in merged.columns:
        merged["HxG"] = merged["HxG_y"]
        merged["AxG"] = merged["AxG_y"]
        merged["xG_diff"] = merged["xG_diff_y"]
    elif "HxG" not in merged.columns:
        merged["HxG"] = None
        merged["AxG"] = None
        merged["xG_diff"] = None

    mean_hxg = xg_df["HxG"].mean().round(2)
    mean_axg = xg_df["AxG"].mean().round(2)
    merged["HxG"] = merged["HxG"].fillna(mean_hxg)
    merged["AxG"] = merged["AxG"].fillna(mean_axg)
    merged["xG_diff"] = merged["HxG"] - merged["AxG"]
    return merged


from config import API_FOOTBALL_KEY, THE_ODDS_API_KEY
headers_football = {"x-apisports-key": API_FOOTBALL_KEY}

ODDS_CACHE_FILE = Path("cached_odds.json")
def save_odds_to_cache(odds_data):
    with open(ODDS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(odds_data, f, ensure_ascii=False, indent=2, default=str)

def load_odds_cache():
    if ODDS_CACHE_FILE.exists():
        with open(ODDS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# fixture.py

def save_predictions_to_cache(matches, file_path="prediction_cache.json"):
    import json
    import os

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}

    for match in matches:
        fixture_id = int(match["FixtureID"])

        existing_data[fixture_id] = {
            "FixtureID": fixture_id,
            "Date": match.get("Date"),
            "League": match.get("League"),
            "HomeTeam": match.get("HomeTeam", ""),
            "AwayTeam": match.get("AwayTeam", ""),
            "Predicted_Label": match.get("Predicted_Label"),
            "Home Win %": match.get("Home Win %"),
            "Draw %": match.get("Draw %"),
            "Away Win %": match.get("Away Win %"),
            "HomeGoals": match.get("HomeGoals"),
            "AwayGoals": match.get("AwayGoals"),
            "Status": match.get("Status", "SCHEDULED")
        }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"📦 {len(matches)} maç prediction_cache.json dosyasına kaydedildi.")




league_codes = {
    "D1": 2002,  # Bundesliga
    "E0": 2021,  # Premier League
    "SP1": 2014,  # La Liga
    "I1": 2019,  # Serie A
    "F1": 2015   # Ligue 1
}
league_ids = {
    "D1": 78,    # Bundesliga
    "E0": 39,    # Premier League
    "SP1": 140,  # La Liga
    "I1": 135,   # Serie A
    "F1": 61,    # Ligue 1
    "T1":203,    #SuperLig
    
}

theoddsapi_league_keys = {
    "E0": "soccer_epl",
    "D1": "soccer_germany_bundesliga",
    "SP1": "soccer_spain_la_liga",
    "I1": "soccer_italy_serie_a",
    "F1": "soccer_france_ligue_one",
    "T1": "soccer_turkey_super_league",
}


def get_current_season():
    """api-sports.io's 'season' is the year a European league season started
    (e.g. the 2024-25 season is season=2024). Seasons roll over around July."""
    today = datetime.now().date()
    return today.year if today.month >= 7 else today.year - 1


def get_scheduled_fixtures_from_theoddsapi(code):
    """Fallback source for upcoming fixtures + odds when api-sports.io can't
    supply the current season (e.g. a Free-plan key). The Odds API returns
    upcoming events directly - team names and kickoff time - so it doubles
    as both the fixture list and the odds source, unlike api-sports.io where
    we need a fixture ID from one call before fetching odds for it."""
    league_key = theoddsapi_league_keys.get(code)
    if not league_key:
        return []

    url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"❌ The Odds API hatası ({code}):", response.status_code, response.text)
        return []

    rows = []
    for event in response.json():
        home_team = normalize_team_name(event.get("home_team", ""))
        away_team = normalize_team_name(event.get("away_team", ""))
        if not home_team or not away_team:
            continue

        odds = None
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                candidate = {}
                for outcome in market.get("outcomes", []):
                    name = normalize_team_name(outcome["name"])
                    if name == home_team:
                        candidate["B365H"] = outcome["price"]
                    elif name == away_team:
                        candidate["B365A"] = outcome["price"]
                    elif outcome["name"].lower() in ("draw", "drawn"):
                        candidate["B365D"] = outcome["price"]
                if all(k in candidate for k in ("B365H", "B365D", "B365A")):
                    odds = candidate
                    break
            if odds:
                break

        if not odds:
            continue

        # The Odds API's event IDs are opaque strings, not the integer IDs
        # the rest of the pipeline (DB schema, JSON cache keys) expects -
        # derive a stable synthetic integer FixtureID from it instead.
        fixture_id = int(hashlib.md5(event["id"].encode()).hexdigest(), 16) % (10 ** 9)

        rows.append({
            "FixtureID": fixture_id,
            "Date": pd.to_datetime(event["commence_time"]).date(),
            "HomeTeam": team_name_map.get(home_team, home_team),
            "AwayTeam": team_name_map.get(away_team, away_team),
            "Matchday": None,
            "HomeGoals": None,
            "AwayGoals": None,
            "Status": "SCHEDULED",
            "League": code,
            "B365H": odds["B365H"],
            "B365D": odds["B365D"],
            "B365A": odds["B365A"],
        })

    return rows


team_name_map = {
        # Premier League (E0)
    "AFC Bournemouth":"Bournemouth",
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Brentford FC": "Brentford",
    "Brighton & Hove Albion FC": "Brighton",
    "Burnley FC": "Burnley",
    "Chelsea FC": "Chelsea",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Luton Town FC": "Luton",
    "Manchester City FC": "Man City",
    "Manchester United FC": "Man United",
    "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "Nottm Forest",
    "Sheffield United FC": "Sheffield United",
    "Tottenham Hotspur FC": "Tottenham",
    "West Ham United FC": "West Ham",
    "Wolverhampton Wanderers FC": "Wolves",
    "Southampton FC":"Southampton",
    "Ipswich Town FC":"Ipswich",
    "Leicester City FC":"Leicester",


    # La Liga (SP1)
    "Real Madrid CF":"Real Madrid",
    "FC Barcelona":"Barcelona",
    "Espanyol": "Espanol",
    "Girona FC": "Girona",
    "RC Celta de Vigo": "Celta",
    "Real Betis Balompié": "Betis",
    "Valencia CF":"Valencia",
    "Getafe CF"	:"Getafe",
    "Sevilla FC":"Sevilla",
    "Villarreal CF":"Villarreal",
    "UD Las Palmas":"Las Palmas",
    "Club Atlético de Madrid":"Ath Madrid",
    "RCD Mallorca":"Mallorca",
    "Real Valladolid CF":"Valladolid",
    "Rayo Vallecano de Madrid":"Vallecano",
    "Real Sociedad de Fútbol":"Sociedad",
    'RCD Espanyol de Barcelona':'Espanol',
    "CD Leganés":"Leganes",
    "Athletic Club":"Ath Bilbao",
    

    # Serie A (I1)
    "AC Milan": "Milan",
    "Inter Milan": "Inter",
    "FC Internazionale Milano": "Inter",
    "SSC Napoli": "Napoli",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "Juventus FC": "Juventus",
    "Atalanta BC": "Atalanta",
    "Torino FC": "Torino",
    "Fiorentina": "Fiorentina",
    "ACF Fiorentina": "Fiorentina",
    "Udinese Calcio": "Udinese",
    "Bologna FC 1909": "Bologna",
    "Hellas Verona FC": "Verona",
    "US Lecce": "Lecce",
    "Empoli FC": "Empoli",
    "Genoa CFC": "Genoa",
    "Cagliari Calcio": "Cagliari",
    "Como 1907": "Como",
    "AC Monza": "Monza",
    "Parma Calcio 1913": "Parma",
    "Venezia FC":"Venezia",
    "Deportivo Alavés":"Alaves",
    "CA Osasuna":"Osasuna",

    # Ligue 1 (F1)
    "Paris Saint-Germain FC": "Paris SG",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "Lille OSC": "Lille",
    "OGC Nice": "Nice",
    "Stade Rennais FC 1901": "Rennes",
    "RC Strasbourg Alsace": "Strasbourg",
    "FC Nantes": "Nantes",
    "Stade Brestois 29": "Brest",
    "Toulouse FC": "Toulouse",
    "Montpellier HSC": "Montpellier",
    "Le Havre AC": "Le Havre",
    "Stade de Reims": "Reims",
    "Clermont Foot 63": "Clermont",
    "Metz": "Metz",
    "RC Lens": "Lens",
    "Angers SCO": "Angers",
    "AJ Auxerre": "Auxerre",
    "AS Saint-Étienne": "St Etienne",
    "Racing Club de Lens":"Lens",

    #Bundesliga
    "Bayer 04 Leverkusen":"Leverkusen",
    "FC Augsburg":"Augsburg",
    "FC St. Pauli 1910":"St Pauli",
    "FC St Pauli 1910":"St Pauli",
    "SV Werder Bremen":"Werder Bremen",
    "1. FC Heidenheim 1846":"Heidenheim",
    "1 FC Heidenheim 1846":"Heidenheim",
    "TSG 1899 Hoffenheim": "Hoffenheim",
    "1899 Hoffenheim": "Hoffenheim",
    "FC St Pauli": "St Pauli",
    "1 FC Heidenheim": "Heidenheim",
    "VfL Bochum 1848": "Bochum",
    'Borussia Mönchengladbach': "MGladbach",
    'Borussia Dortmund':"Dortmund",
    "Bayer Leverkusen":"Leverkusen",
    'Eintracht Frankfurt':"Ein Frankfurt",
     'VfB Stuttgart':"Stuttgart",
    "Borussia Monchengladbach": "MGladbach",
    "Bayer Leverkusen": "Leverkusen", 
    "1. FSV Mainz 05": "Mainz",
    "Mainz 05": "Mainz",
    "SC Freiburg": "Freiburg",
    "VfL Wolfsburg": "Wolfsburg",
    "VfB Stuttgart": "Stuttgart", 
    "FC Bayern München":"Bayern Munich",
    "Bayern München":"Bayern Munich",
    "1. FC Union Berlin":"Union Berlin",
    "1 FC Union Berlin":"Union Berlin",
    "TSG Hoffenheim": "Hoffenheim",
    "FC St Pauli": "St Pauli",
    "1 FC Heidenheim": "Heidenheim",
    "VfL Bochum": "Bochum",
    'Borussia Mönchengladbach': "MGladbach",
    'Borussia Dortmund':"Dortmund",
    "Bayer Leverkusen":"Leverkusen",
    'Eintracht Frankfurt':"Ein Frankfurt",
    'VfB Stuttgart':"Stuttgart",
    "Borussia Monchengladbach": "MGladbach",
    "Bayer Leverkusen": "Leverkusen", 
    "FSV Mainz 05": "Mainz",
    "SC Freiburg": "Freiburg",
    "VfL Wolfsburg": "Wolfsburg",
    "VfB Stuttgart": "Stuttgart",
    "1. FC Heidenheim":"Heidenheim",
    "Mainz 05":"Mainz",
    "FC St. Pauli":"St Pauli",
    "Bayer 04 Leverkusen":"Leverkusen",
    "FC Augsburg":"Augsburg",
    "FC St. Pauli 1910":"St Pauli",
    

    # Premier League
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Brighton and Hove Albion": "Brighton",
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Leicester City": "Leicester",
    "Nottingham Forest": "Nottm Forest",
    "Newcastle United": "Newcastle",
    "Sevilla FC":"Sevilla",
    "Ipswich Town":"Ipswich",

    # La Liga
    "Atlético Madrid": "Ath Madrid",
    "Athletic Bilbao": "Ath Bilbao",
    "RC Lens": "Lens",
    "Rayo Vallecano": "Vallecano",
    "Real Sociedad": "Sociedad",
    "Real Betis": "Betis",
    "CA Osasuna": "Osasuna",
    "Leganés": "Leganes",
    "Celta Vigo": "Celta",
    "Espanyol": "Espanol",
    "Alavés":"Alaves",

    # Serie A
    "AC Milan": "Milan",
    "Inter Milan": "Inter",
    "AS Roma": "Roma",
    "Atalanta BC": "Atalanta",
    "Hellas Verona": "Verona",
    "AS Monaco": "Monaco",  # Monaco aslında Ligue 1 ama API'de İtalya olabilir
    "Paris Saint Germain": "Paris SG",

    # Ligue 1
    "Saint Etienne": "St Etienne",
    "Stade de Reims": "Reims",
    "Racing Club de Lens":"Lens",
    "Paris Saint Germain": "Paris SG",
    "Paris Saint-Germain FC":"Paris SG",

    #SuperLig
    "Adana Demirspor": "Ad. Demirspor",
    "Adanaspor": "Adanaspor",
    "Akhisarspor": "Akhisar Belediyespor",
    "Alanyaspor": "Alanyaspor",
    "Altay": "Altay",
    "MKE Ankaragücü": "Ankaragucu",
    "Antalyaspor": "Antalyaspor",
    "Beşiktaş JK": "Besiktas",
    "Bodrumspor": "Bodrumspor",
    "Bursaspor": "Bursaspor",
    "İstanbul Başakşehir": "Buyuksehyr",
    "Denizlispor": "Denizlispor",
    "BB Erzurumspor": "Erzurum BB",
    "Eyüpspor": "Eyupspor",
    "Fenerbahçe": "Fenerbahce",
    "Galatasaray": "Galatasaray",
    "Gaziantep FK": "Gaziantep",
    "Gaziantepspor": "Gaziantepspor",
    "Gençlerbirliği": "Genclerbirligi",
    "Giresunspor": "Giresunspor",
    "Göztepe": "Goztep",
    "Hatayspor": "Hatayspor",
    "İstanbulspor": "Istanbulspor",
    "Kardemir Karabükspor": "Karabukspor",
    "Fatih Karagümrük": "Karagumruk",
    "Kasımpaşa": "Kasimpasa",
    "Kayserispor": "Kayserispor",
    "Konyaspor": "Konyaspor",
    "Osmanlıspor": "Osmanlispor",
    "Pendikspor": "Pendikspor",
    "Çaykur Rizespor": "Rizespor",
    "Samsunspor": "Samsunspor",
    "Sivasspor": "Sivasspor",
    "Trabzonspor": "Trabzonspor",
    "Ümraniyespor": "Umraniyespor",
    "Yeni Malatyaspor": "Yeni Malatyaspor",

    # The Odds API name variants (different source, different naming
    # convention than api-sports.io - discovered by comparing live Odds
    # API output against the historical CSVs' team names)
    "Hull City": "Hull",
    "Leeds United": "Leeds",
    "Deportivo La Coruña": "La Coruna",
    "Elche CF": "Elche",
    "Málaga": "Malaga",
    "1 FC Köln": "FC Koln",
    "FC Schalke 04": "Schalke 04",
    "Hamburger SV": "Hamburg",
    "SC Paderborn": "Paderborn",
    "Basaksehir": "Buyuksehyr",
    "Besiktas JK": "Besiktas",
    "Gazişehir Gaziantep": "Gaziantep",
    "Genclerbirligi SK": "Genclerbirligi",
    "Goztepe": "Goztep",
    "Kasimpasa SK": "Kasimpasa",
    "Torku Konyaspor": "Konyaspor",
}

    


def normalize_team_name(name):
    return (
        name.replace(".", "")
            .replace("’", "'")
            .replace("`", "'")
            .replace("´", "'")
            .strip()
    )
def get_standings_by_name(league_name, season=None):
    season = season or get_current_season()
    url = f"https://v3.football.api-sports.io/leagues?search={league_name}"
    res = requests.get(url, headers=headers_football)

    if res.status_code != 200:
        print(f"❌ League search failed: {res.status_code}")
        return []

    results = res.json().get("response", [])
    if not results:
        print(f"❌ League not found: {league_name}")
        return []

    # En güncel eşleşen league_id alalım
    league_id = results[0]["league"]["id"]

    standings_url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    standings_res = requests.get(standings_url, headers=headers_football)

    if standings_res.status_code != 200:
        print(f"❌ Standings fetch error: {standings_res.status_code}")
        return []

    data = standings_res.json().get("response", [])
    if not data:
        print(f"⚠️ Standings boş: {league_name} ({season})")
        return []

    table = data[0]["league"]["standings"][0]
    standings = []
    for team in table:
        stats = team["all"]
        standings.append({
            "position": team["rank"],
            "team": team["team"]["name"],
            "playedGames": stats["played"],
            "won": stats["win"],
            "draw": stats["draw"],
            "lost": stats["lose"],
            "goalDifference": team["goalsDiff"],
            "points": team["points"]
        })

    return standings

def get_standings_by_league(code):
    league_id = league_ids.get(code)
    if not league_id:
        return []

    url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={get_current_season()}"
    response = requests.get(url, headers=headers_football)
    data = response.json().get("response", [])
    if not data:
        return []

    table = data[0]["league"]["standings"][0]
    standings = []
    for team in table:
        stats = team["all"]
        standings.append({
            "position": team["rank"],
            "team": team["team"]["name"],
            "playedGames": stats["played"],
            "won": stats["win"],
            "draw": stats["draw"],
            "lost": stats["lose"],
            "goalDifference": team["goalsDiff"],
            "points": team["points"]
        })
    return standings

def save_odds_to_cache(data):
    with open(ODDS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def load_odds_cache():
    if ODDS_CACHE_FILE.exists():
        with open(ODDS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

cached_odds_data = load_odds_cache()



def enrich_with_standings(df):
    standings_map = {}
    for code in df["League"].unique():
        standings = get_standings_by_league(code)
        if standings:
            df_st = pd.DataFrame(standings)
            df_st["team"] = df_st["team"].apply(normalize_team_name).replace(team_name_map)
            standings_map[code] = df_st.set_index("team")

    df["HomeStanding"] = None
    df["AwayStanding"] = None

    for code in df["League"].unique():
        st_df = standings_map.get(code)
        if st_df is None:
            continue

        mask = df["League"] == code
        df.loc[mask, "HomeStanding"] = df.loc[mask, "HomeTeam"].map(st_df["position"])
        df.loc[mask, "AwayStanding"] = df.loc[mask, "AwayTeam"].map(st_df["position"])

    return df
def get_match_from_api(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    response = requests.get(url, headers=headers_football)
    if response.status_code != 200:
        return None

    data = response.json().get("response", [])
    if not data:
        return None

    m = data[0]
    return {
        "status": m["fixture"]["status"]["short"],
        "HomeGoals": m["goals"]["home"],
        "AwayGoals": m["goals"]["away"]
    }


def get_match_events(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
    response = requests.get(url, headers=headers_football)

    if response.status_code != 200:
        print(f"❌ Event fetch error: {response.status_code}")
        return []

    data = response.json().get("response", [])
    simplified = []

    for ev in data:
        simplified.append({
            "minute": ev["time"]["elapsed"],
            "team": ev["team"]["name"],
            "player": ev.get("player", {}).get("name"),
            "assist": ev.get("assist", {}).get("name"),
            "type": ev["type"],
            "detail": ev["detail"]
        })

    return simplified

def get_live_matches_with_predictions(best_models, features, team_categories, historical_data_by_league):
    # 🎯 1. Canlı maçları çek (tek seferde)

    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    response = requests.get(url_live, headers=headers_football)
    data_live = response.json().get("response", [])

    valid_leagues = set(league_ids.values())
    live_matches = []

    for m in data_live:
        if m["league"]["id"] not in valid_leagues:
            continue

        fixture_id = m["fixture"]["id"]
        match_date = pd.to_datetime(m["fixture"]["date"]).date()
        home_team = normalize_team_name(m["teams"]["home"]["name"])
        away_team = normalize_team_name(m["teams"]["away"]["name"])

        # Doğru code'u bulmak için
        code_match = [k for k, v in league_ids.items() if v == m["league"]["id"]]
        if not code_match:
            continue
        code = code_match[0]

        league_key = theoddsapi_league_keys.get(code)
    #    odds = get_odds_from_theoddsapi(home_team, away_team, match_date, league_key)
    #    if not odds:
        odds = get_odds_from_api_football(fixture_id)
        if not odds:
            odds = {"B365H": 3.0, "B365D": 3.0, "B365A": 3.0}

        row = {
            "FixtureID": fixture_id,
            "Date": match_date,
            "HomeTeam": team_name_map.get(home_team, home_team),
            "AwayTeam": team_name_map.get(away_team, away_team),
            "Matchday": m["league"]["round"],
            "HomeGoals": m["goals"]["home"],
            "AwayGoals": m["goals"]["away"],
            "Status": "LIVE",
            "League": code,
            "B365H": odds["B365H"],
            "B365D": odds["B365D"],
            "B365A": odds["B365A"],
            "Elapsed": m["fixture"]["status"].get("elapsed")
        }
        live_matches.append(row)

    # 🎯 2. Tahmin yap
    df_live = pd.DataFrame(live_matches)
    if df_live.empty:
        return []

    df_live["HomeTeam_code"] = pd.Categorical(df_live["HomeTeam"], categories=team_categories).codes
    df_live["AwayTeam_code"] = pd.Categorical(df_live["AwayTeam"], categories=team_categories).codes

    df_live = add_latest_elo_to_fixtures(df_live, historical_data_by_league)
    df_live = add_latest_elo_features_to_fixtures(df_live, historical_data_by_league)
    df_live = add_all_features_to_merged_df(df_live, historical_data_by_league)

   

    # Live predictions are returned to the live service and must never replace
    # the fixture's stored pre-match prediction.
    predicted_df = predict_from_merged_df(
        df_live, best_models, features, prediction_type="LIVE", persist=False
    )
    predictions_dict = predicted_df.set_index("FixtureID").to_dict(orient="index")

    # 🎯 3. Çıkış formatla
    output = []
    for row in live_matches:
        fixture_id = row["FixtureID"]
        prediction = predictions_dict.get(fixture_id)

        if isinstance(prediction, list) and len(prediction) > 0:
            prediction = prediction[0]  # İlk öğeyi al
        elif not isinstance(prediction, dict):
            prediction = None

        output.append({
            "fixture_id": fixture_id,
            "date": str(row["Date"]),
            "home_team": row["HomeTeam"],
            "away_team": row["AwayTeam"],
            "league": row["League"],
            "score": f"{row['HomeGoals']} - {row['AwayGoals']}",
            "elapsed": row.get("Elapsed"),
            "status": row["Status"],
            "predicted_label": prediction.get("Predicted_Label") if prediction else "N/A",
            "home_win_pct": float(prediction.get("Home Win %")) if prediction else None,
            "draw_pct": float(prediction.get("Draw %")) if prediction else None,
            "away_win_pct": float(prediction.get("Away Win %")) if prediction else None
        })


    return output

# fixture.py içine ekle
def predict_from_live_api(live_best_models, features):
    live_matches = get_live_fixtures()
    results = []

    for match in live_matches:
        fixture_id = match["fixture_id"]
        home_team = match["home_team"]
        away_team = match["away_team"]
        elapsed = match["elapsed"] or 0
        ht_home = match.get("ht_home_goals", 0)
        ht_away = match.get("ht_away_goals", 0)
        score_str = f"{ht_home} - {ht_away}"
        
        htr = get_htr(score_str, home_team, away_team)
        htr_code = {"H": 1, "D": 0, "A": -1}.get(htr, 0)

        # Oranları ve kartları al
        odds = get_live_odds_from_api_football(fixture_id)
        if not odds:
            continue

        prob = normalize_odds(odds)
        events = get_live_events_summary(fixture_id, home_team, away_team)

        # Özellik vektörünü oluştur
        feature_row = {
            "HY": events["home_yellow_cards"],
            "AY": events["away_yellow_cards"],
            "HR": events["home_red_cards"],
            "AR": events["away_red_cards"],
            "HTR_code": htr_code,
            "HTAG": ht_away,
            "HTHG": ht_home,
            "HomeProb": prob["HomeProb"],
            "DrawProb": prob["DrawProb"],
            "AwayProb": prob["AwayProb"]
        }

        row_filled = {col: feature_row.get(col, 0) for col in features}
        X_input = pd.DataFrame([row_filled])

        model = live_best_models.get("E0")
        if not model:
            continue

        predicted = model.predict(X_input)[0]
        proba = model.predict_proba(X_input)[0]

        label = {1: "Home Win", 0: "Draw", -1: "Away Win"}[predicted]

        result_row = {
            "fixture_id": fixture_id,
            "home_team": home_team,
            "away_team": away_team,
            "elapsed": f"{elapsed} min",
            "home_score": ht_home,
            "away_score": ht_away,
            "predicted_label": label,
            "home_win_pct": round(proba[2] * 100, 2),
            "draw_pct": round(proba[1] * 100, 2),
            "away_win_pct": round(proba[0] * 100, 2)
        }

        results.append(result_row)

    return results





#def get_odds_from_theoddsapi(home_team, away_team, match_date, league_key):
#   url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds"
#    params = {
#        "apiKey": THE_ODDS_API_KEY,
#        "regions": "eu",
#         "markets": "h2h",
#         "oddsFormat": "decimal",
#        "dateFormat": "iso"
#    }

#    response = requests.get(url, params=params)
#    if response.status_code != 200:
#        print("❌ The Odds API Hatası:", response.status_code, response.text)
 #       return None

#    data = response.json()
#    for match in data:
 #       match_home = match.get("home_team")
#        match_away = match.get("away_team")
#        date = pd.to_datetime(match["commence_time"]).date()

#        if (
#            normalize_team_name(match_home) == normalize_team_name(home_team) and
 #           normalize_team_name(match_away) == normalize_team_name(away_team) and
 #           date == match_date
 #       ):
#            odds = {}
 #           for bookmaker in match.get("bookmakers", []):
 #               for market in bookmaker.get("markets", []):
 #                   if market["key"] == "h2h":
 #                       for outcome in market.get("outcomes", []):
 #                           if normalize_team_name(outcome["name"]) == normalize_team_name(home_team):
 #                               odds["B365H"] = outcome["price"]
 #                           elif normalize_team_name(outcome["name"]) == normalize_team_name(away_team):
 #                               odds["B365A"] = outcome["price"]
 #                           elif outcome["name"].lower() in ["draw", "drawn"]:
 #                               odds["B365D"] = outcome["price"]
 #           if all(k in odds for k in ["B365H", "B365D", "B365A"]):
 #               return odds
 #   return None

def get_odds_from_api_football(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    response = requests.get(url, headers=headers_football)
    if response.status_code != 200:
        print("❌ API-Football Odds Hatası:", response.status_code, response.text)
        return None

    data = response.json().get("response", [])
    for item in data:
        for bookmaker in item.get("bookmakers", []):
            if bookmaker["name"].lower() == "bet365":
                for bet in bookmaker.get("bets", []):
                    if bet["name"].lower() == "match winner":
                        odds = {}
                        for value in bet.get("values", []):
                            outcome = value["value"].lower()
                            price = float(value["odd"])
                            if outcome == "home":
                                odds["B365H"] = price
                            elif outcome == "draw":
                                odds["B365D"] = price
                            elif outcome == "away":
                                odds["B365A"] = price
                        if all(k in odds for k in ["B365H", "B365D", "B365A"]):
                            return odds
    return None

def get_grouped_standings(league_id=15, season=None):
    season = season or get_current_season()
    url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    res = requests.get(url, headers=headers_football)

    if res.status_code != 200:
        print("❌ API hatası:", res.status_code)
        return {}

    data = res.json().get("response", [])
    if not data:
        print("❌ Standings bulunamadı.")
        return {}

    standings = data[0]["league"]["standings"]  # List of groups
    grouped = {}

    for group in standings:
        if not group:
            continue
        group_name = group[0].get("group", "Unknown")
        grouped[group_name] = []

        for team in group:
            stats = team["all"]
            grouped[group_name].append({
                "rank": team["rank"],
                "team": team["team"]["name"],
                "points": team["points"],
                "played": stats["played"],
                "won": stats["win"],
                "draw": stats["draw"],
                "lose": stats["lose"],
                "goalDiff": team["goalsDiff"]
            })

    return grouped


def get_combined_fixtures_with_odds():
    all_fixtures = []
    scheduled_with_odds = []

    for code, league_id in league_ids.items():
        # 🎯 1. Bitmiş maçlar
        url_finished = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={get_current_season()}&status=FT"
        response_finished = requests.get(url_finished, headers=headers_football)
        data_finished = response_finished.json().get("response", [])

        finished_df = pd.DataFrame([{
            "FixtureID": m["fixture"]["id"],
            "Date": pd.to_datetime(m["fixture"]["date"]).date(),
            "HomeTeam": team_name_map.get(normalize_team_name(m["teams"]["home"]["name"]), m["teams"]["home"]["name"]),
            "AwayTeam": team_name_map.get(normalize_team_name(m["teams"]["away"]["name"]), m["teams"]["away"]["name"]),
            "Matchday": m["league"]["round"],
            "HomeGoals": m["goals"]["home"],
            "AwayGoals": m["goals"]["away"],
            "Status": "FINISHED",
            "League": code
        } for m in data_finished])
        all_fixtures.append(finished_df)

        # 🎯 2. Planlanmış maçlar
        url_scheduled = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={get_current_season()}&status=NS"
        response_sched = requests.get(url_scheduled, headers=headers_football)
        data_sched = response_sched.json().get("response", [])

        if not data_sched:
            # api-sports.io returned nothing for this season/league (e.g. a
            # Free-plan key blocked from the current season) - fall back to
            # The Odds API, which supplies both the fixture list and odds.
            scheduled_with_odds.extend(get_scheduled_fixtures_from_theoddsapi(code))
            continue

        for m in data_sched:
            fixture_id = m["fixture"]["id"]
            match_date = pd.to_datetime(m["fixture"]["date"]).date()
            home_team = normalize_team_name(m["teams"]["home"]["name"])
            away_team = normalize_team_name(m["teams"]["away"]["name"])

            league_key = theoddsapi_league_keys.get(code)
        #    odds = get_odds_from_theoddsapi(home_team, away_team, match_date, league_key)
            
            odds = get_odds_from_api_football(fixture_id)

            if not odds:
                continue

            row = {
                "FixtureID": fixture_id,
                "Date": match_date,
                "HomeTeam": team_name_map.get(home_team, home_team),
                "AwayTeam": team_name_map.get(away_team, away_team),
                "Matchday": m["league"]["round"],
                "HomeGoals": None,
                "AwayGoals": None,
                "Status": "SCHEDULED",
                "League": code,
                "B365H": odds["B365H"],
                "B365D": odds["B365D"],
                "B365A": odds["B365A"]
            }
            scheduled_with_odds.append(row)
       
    # 🔄 DataFrame birleştirme
    df_sched = pd.DataFrame(scheduled_with_odds)
    df_combined = pd.concat([df_sched] + all_fixtures, ignore_index=True)

    if df_combined.empty:
        # Hiç bitmiş ya da oranlı planlanmış maç bulunamadı (örn. sezon henüz
        # başlamış/bitmiş, ya da hiçbir maç için oran verisi yok).
        df_combined = pd.DataFrame(columns=[
            "FixtureID", "Date", "HomeTeam", "AwayTeam", "Matchday",
            "HomeGoals", "AwayGoals", "Status", "League",
            "B365H", "B365D", "B365A"
        ])

    df_combined["Date"] = pd.to_datetime(df_combined["Date"], errors="coerce")
    df_combined = df_combined.dropna(subset=["Date"])
    df_combined["Date"] = df_combined["Date"].dt.date
    df_combined = df_combined.sort_values(by="Date").reset_index(drop=True)

    df_combined = enrich_with_standings(df_combined)
    df_combined = merge_xg_to_fixtures(df_combined, xg_data)
    
    return df_combined

from datetime import datetime
import requests
import pandas as pd

def get_scheduled_matches_until(cutoff_date):
    scheduled_matches = []

    for code, league_id in league_ids.items():
        url_scheduled = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={get_current_season()}&status=NS"
        response_sched = requests.get(url_scheduled, headers=headers_football)
        data_sched = response_sched.json().get("response", [])

        for m in data_sched:
            match_date = pd.to_datetime(m["fixture"]["date"]).date()
            if match_date > cutoff_date:
                continue

            fixture_id = m["fixture"]["id"]
            home_team = normalize_team_name(m["teams"]["home"]["name"])
            away_team = normalize_team_name(m["teams"]["away"]["name"])

            odds = get_odds_from_api_football(fixture_id)
            if not odds:
                continue

            row = {
                "FixtureID": fixture_id,
                "Date": match_date,
                "HomeTeam": team_name_map.get(home_team, home_team),
                "AwayTeam": team_name_map.get(away_team, away_team),
                "Matchday": m["league"]["round"],
                "HomeGoals": None,
                "AwayGoals": None,
                "Status": "SCHEDULED",
                "League": code,
                "B365H": odds["B365H"],
                "B365D": odds["B365D"],
                "B365A": odds["B365A"]
            }
            scheduled_matches.append(row)

    return pd.DataFrame(scheduled_matches)
