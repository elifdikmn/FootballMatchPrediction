import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
THE_ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "")

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
