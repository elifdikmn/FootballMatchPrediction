import pandas as pd
from datetime import timedelta
from team_normalizer import normalize_team_name, team_name_map

def build_features_dataframe(fixtures, historical_data_by_league):
    import pandas as pd

    # 1️⃣ Fixture objelerini DataFrame'e dönüştür
    rows = []
    for fx in fixtures:
        # dict veya objeyi destekle
        is_dict = isinstance(fx, dict)

        rows.append({
            "FixtureID": fx["FixtureID"] if is_dict else fx.FixtureID,
            "Date": fx["Date"] if is_dict else fx.Date,
            "League": fx["League"] if is_dict else fx.League,
            "HomeTeam": fx["HomeTeam"] if is_dict else fx.HomeTeam,
            "AwayTeam": fx["AwayTeam"] if is_dict else fx.AwayTeam,
            "B365H": fx.get("B365H") if is_dict else getattr(fx, "B365H", None),
            "B365D": fx.get("B365D") if is_dict else getattr(fx, "B365D", None),
            "B365A": fx.get("B365A") if is_dict else getattr(fx, "B365A", None)
        })
    merged_df = pd.DataFrame(rows)

    if merged_df.empty:
        return merged_df


    # 2️⃣ ELO ve form özelliklerini ekle
    merged_df = add_latest_elo_to_fixtures(merged_df, historical_data_by_league)
    merged_df = add_latest_elo_features_to_fixtures(merged_df, historical_data_by_league)
    merged_df = add_all_features_to_merged_df(merged_df, historical_data_by_league)

    return merged_df

def add_latest_elo_to_fixtures(merged_df, historical_data_by_league):
    merged_df = merged_df.copy()
    home_elos = []
    away_elos = []

    for _, row in merged_df.iterrows():
        league = row["League"]
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]
        match_date = pd.to_datetime(row["Date"])

        df_hist = historical_data_by_league.get(league)
        if df_hist is None:
            home_elos.append(1500)
            away_elos.append(1500)
            continue

        df_hist = df_hist[df_hist["Date"] < match_date]

        # Home Elo
        home_match = df_hist[(df_hist["HomeTeam"] == home_team) | (df_hist["AwayTeam"] == home_team)] \
            .sort_values("Date", ascending=False).head(1)

        if not home_match.empty:
            row_home = home_match.iloc[0]
            home_elo = row_home["HomeElo"] if row_home["HomeTeam"] == home_team else row_home["AwayElo"]
        else:
            home_elo = 1500

        # Away Elo
        away_match = df_hist[(df_hist["HomeTeam"] == away_team) | (df_hist["AwayTeam"] == away_team)] \
            .sort_values("Date", ascending=False).head(1)

        if not away_match.empty:
            row_away = away_match.iloc[0]
            away_elo = row_away["HomeElo"] if row_away["HomeTeam"] == away_team else row_away["AwayElo"]
        else:
            away_elo = 1500

        home_elos.append(home_elo)
        away_elos.append(away_elo)

    merged_df["HomeElo"] = home_elos
    merged_df["AwayElo"] = away_elos
    merged_df["EloDiff"] = merged_df["HomeElo"] - merged_df["AwayElo"]

    return merged_df


def add_latest_elo_features_to_fixtures(merged_df, historical_data_by_league):
    merged_df = merged_df.copy()
    elo_cols = ["EloChange30_Home", "EloChange60_Home", "EloChange30_Away", "EloChange60_Away"]

    for col in elo_cols:
        merged_df[col] = 0.0

    for i, row in merged_df.iterrows():
        league = row["League"]
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        match_date = pd.to_datetime(row["Date"])

        hist_df = historical_data_by_league.get(league)
        if hist_df is None:
            continue

        hist_df = hist_df[hist_df["Date"] < match_date]

        # Home geçmiş
        home_past_30 = hist_df[(hist_df["HomeTeam"] == home) | (hist_df["AwayTeam"] == home)]
        home_past_30 = home_past_30[home_past_30["Date"] < match_date - timedelta(days=30)]
        home_past_60 = hist_df[(hist_df["HomeTeam"] == home) | (hist_df["AwayTeam"] == home)]
        home_past_60 = home_past_60[home_past_60["Date"] < match_date - timedelta(days=60)]

        if not home_past_30.empty:
            latest = home_past_30.sort_values("Date", ascending=False).iloc[0]
            merged_df.at[i, "EloChange30_Home"] = row["HomeElo"] - (
                latest["HomeElo"] if latest["HomeTeam"] == home else latest["AwayElo"]
            )

        if not home_past_60.empty:
            latest = home_past_60.sort_values("Date", ascending=False).iloc[0]
            merged_df.at[i, "EloChange60_Home"] = row["HomeElo"] - (
                latest["HomeElo"] if latest["HomeTeam"] == home else latest["AwayElo"]
            )

        # Away geçmiş
        away_past_30 = hist_df[(hist_df["HomeTeam"] == away) | (hist_df["AwayTeam"] == away)]
        away_past_30 = away_past_30[away_past_30["Date"] < match_date - timedelta(days=30)]
        away_past_60 = hist_df[(hist_df["HomeTeam"] == away) | (hist_df["AwayTeam"] == away)]
        away_past_60 = away_past_60[away_past_60["Date"] < match_date - timedelta(days=60)]

        if not away_past_30.empty:
            latest = away_past_30.sort_values("Date", ascending=False).iloc[0]
            merged_df.at[i, "EloChange30_Away"] = row["AwayElo"] - (
                latest["HomeElo"] if latest["HomeTeam"] == away else latest["AwayElo"]
            )

        if not away_past_60.empty:
            latest = away_past_60.sort_values("Date", ascending=False).iloc[0]
            merged_df.at[i, "EloChange60_Away"] = row["AwayElo"] - (
                latest["HomeElo"] if latest["HomeTeam"] == away else latest["AwayElo"]
            )

    return merged_df



def add_all_features_to_merged_df(merged_df, historical_data_by_league):
    merged_df["HomeTeam"] = merged_df["HomeTeam"].apply(normalize_team_name).replace(team_name_map)
    merged_df["AwayTeam"] = merged_df["AwayTeam"].apply(normalize_team_name).replace(team_name_map)

    merged_df = merged_df.copy()

    def extract_team_features_before_date(team, date, league_df):
        past_matches = league_df[
            (league_df["Date"] < date) &
            ((league_df["HomeTeam"] == team) | (league_df["AwayTeam"] == team))
        ].sort_values("Date", ascending=False).head(5)

        if past_matches.empty:
            return {
                "WinRate": 0, "DrawRate": 0, "LossRate": 0,
                "AvgGoals": 0, "AvgGoalsConceded": 0
            }

        results = past_matches.apply(lambda r:
            "W" if (r["HomeTeam"] == team and r["FTR"] == "H") or
                  (r["AwayTeam"] == team and r["FTR"] == "A") else
            "D" if r["FTR"] == "D" else "L", axis=1)

        goals_for = past_matches.apply(lambda r: r["FTHG"] if r["HomeTeam"] == team else r["FTAG"], axis=1)
        goals_against = past_matches.apply(lambda r: r["FTAG"] if r["HomeTeam"] == team else r["FTHG"], axis=1)

        return {
            "WinRate": (results == "W").mean(),
            "DrawRate": (results == "D").mean(),
            "LossRate": (results == "L").mean(),
            "AvgGoals": goals_for.mean(),
            "AvgGoalsConceded": goals_against.mean()
        }

    feature_rows = []

    for _, row in merged_df.iterrows():
        league = row["League"]
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        match_date = pd.to_datetime(row["Date"])

        hist_df = historical_data_by_league.get(league)
        if hist_df is None:
            continue

        home_form = extract_team_features_before_date(home, match_date, hist_df)
        away_form = extract_team_features_before_date(away, match_date, hist_df)

        # Betting odds
        try:
            home_prob = 1 / row["B365H"]
            draw_prob = 1 / row["B365D"]
            away_prob = 1 / row["B365A"]
            total = home_prob + draw_prob + away_prob
        except Exception:
            home_prob, draw_prob, away_prob = 0.33, 0.33, 0.33
            total = 1

        row["WinRateDiff"] = home_form["WinRate"] - away_form["WinRate"]
        row["DrawRateDiff"] = home_form["DrawRate"] - away_form["DrawRate"]
        row["Last5_WinRate_Home"] = home_form["WinRate"]
        row["Last5_DrawRate_Home"] = home_form["DrawRate"]
        row["Last5_LossRate_Home"] = home_form["LossRate"]
        row["Last5_WinRate_Away"] = away_form["WinRate"]
        row["Last5_DrawRate_Away"] = away_form["DrawRate"]
        row["Last5_LossRate_Away"] = away_form["LossRate"]
        row["Last5_Goals_Home"] = home_form["AvgGoals"]
        row["Last5_Goals_Away"] = away_form["AvgGoals"]
        row["HomeProb"] = home_prob / total
        row["DrawProb"] = draw_prob / total
        row["AwayProb"] = away_prob / total

        feature_rows.append(row)

    return pd.DataFrame(feature_rows)
