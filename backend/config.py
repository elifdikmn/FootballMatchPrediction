import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")

LEAGUE_IDS = {
    "D1": 78,
    "E0": 39,
    "SP1": 140,
    "I1": 135,
    "F1": 61,
    "T1": 203,
}


def current_season() -> int:
    today = datetime.now().date()
    return today.year if today.month >= 7 else today.year - 1

features = [
    "WinRateDiff", "DrawRateDiff",
    "Last5_WinRate_Home", "Last5_DrawRate_Home", "Last5_LossRate_Home",
    "Last5_WinRate_Away", "Last5_DrawRate_Away", "Last5_LossRate_Away",
    "Last5_Goals_Home", "Last5_Goals_Away",
    "HomeProb", "AwayProb", "DrawProb",
    "EloDiff", "EloChange30_Home", "EloChange60_Home",
    "EloChange30_Away", "EloChange60_Away","HxG","AxG","xG_diff"
]

features_tr = [
    "WinRateDiff", "DrawRateDiff",
    "Last5_WinRate_Home", "Last5_DrawRate_Home", "Last5_LossRate_Home",
    "Last5_WinRate_Away", "Last5_DrawRate_Away", "Last5_LossRate_Away",
    "Last5_Goals_Home", "Last5_Goals_Away",
    "HomeProb","AwayProb","DrawProb",
    "EloDiff","EloChange30_Home", "EloChange60_Home","EloChange30_Away", "EloChange60_Away",   
] 
live_features =["HomeProb","AwayProb","DrawProb","HY","AY","HR","AR","HTR_code","HTAG","HTHG"]

features_by_league = {
    "T1": features_tr,  # TR1
    "E0": features,
    "SP1": features,
    "I1": features,
    "F1": features,
    "D1": features,
}
