
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
   # "HomeTeam_code","AwayTeam_code",
    #"Home_Wins", "Away_Wins", "Home_Draws", "Away_Draws",
   # "HomeAvgGoals", "AwayAvgGoals", 
    #"Home_AvgGoalsConceded", "Away_AvgGoalsConceded",
  # "HomeAvgShots", "AwayAvgShots", "HomeAvgShotsOnTarget", "AwayAvgShotsOnTarget",
  #  "HomeAvgShotsConceded", "AwayAvgShotsConceded", 
    "WinRateDiff", "DrawRateDiff",
    #"HomeRecentGoalDiff", "AwayRecentGoalDiff",
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
