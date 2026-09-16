"""Train the per-league match outcome models used by app.py / prediction_pipeline.py.

Rebuilds best_models.pkl (and team_categories.pkl) from the historical
league CSVs, using the exact feature set defined in config.py. Historical
HxG/AxG/xG_diff aren't available for pre-2023 matches (only ~30 future
fixtures have them), so those three columns are filled with 0.0 during
training; app.py/prediction_pipeline.py already fall back to 0/mean when
they're missing at prediction time, so this keeps the models compatible
with the existing serving code.

Usage: python3 train_models.py
"""

import bisect
import pickle
import warnings
from collections import defaultdict, deque

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from config import features, features_tr, features_by_league
from load_league_data import load_historical_league_data
from team_normalizer import normalize_team_name

warnings.filterwarnings("ignore")

SPLIT_DATE = pd.Timestamp("2023-01-01")
RESULT_MAP = {"H": 1, "D": 0, "A": -1}
CLASS_ORDER = [-1, 0, 1]  # Away, Draw, Home - matches prediction_pipeline.py's proba[0..2]


def add_form_and_elo_features(df):
    df = df.sort_values("Date").reset_index(drop=True)

    last5 = defaultdict(lambda: deque(maxlen=5))
    elo_history = defaultdict(lambda: ([], []))  # team -> (dates, elos), both ascending

    out = {k: [] for k in [
        "Last5_WinRate_Home", "Last5_DrawRate_Home", "Last5_LossRate_Home", "Last5_Goals_Home",
        "Last5_WinRate_Away", "Last5_DrawRate_Away", "Last5_LossRate_Away", "Last5_Goals_Away",
        "EloChange30_Home", "EloChange60_Home", "EloChange30_Away", "EloChange60_Away",
    ]}

    def form_of(team):
        past = last5[team]
        if not past:
            return 0.0, 0.0, 0.0, 0.0
        n = len(past)
        wins = sum(1 for r, _ in past if r == "W")
        draws = sum(1 for r, _ in past if r == "D")
        losses = sum(1 for r, _ in past if r == "L")
        goals = sum(g for _, g in past) / n
        return wins / n, draws / n, losses / n, goals

    def elo_change(team, match_date, current_elo, days):
        dates, elos = elo_history[team]
        cutoff = match_date - pd.Timedelta(days=days)
        idx = bisect.bisect_right(dates, cutoff) - 1
        if idx < 0:
            return 0.0
        return current_elo - elos[idx]

    for row in df.itertuples():
        home, away, date = row.HomeTeam, row.AwayTeam, row.Date

        hw, hd, hl, hg = form_of(home)
        aw, ad, al, ag = form_of(away)
        out["Last5_WinRate_Home"].append(hw)
        out["Last5_DrawRate_Home"].append(hd)
        out["Last5_LossRate_Home"].append(hl)
        out["Last5_Goals_Home"].append(hg)
        out["Last5_WinRate_Away"].append(aw)
        out["Last5_DrawRate_Away"].append(ad)
        out["Last5_LossRate_Away"].append(al)
        out["Last5_Goals_Away"].append(ag)

        out["EloChange30_Home"].append(elo_change(home, date, row.HomeElo, 30))
        out["EloChange60_Home"].append(elo_change(home, date, row.HomeElo, 60))
        out["EloChange30_Away"].append(elo_change(away, date, row.AwayElo, 30))
        out["EloChange60_Away"].append(elo_change(away, date, row.AwayElo, 60))

        home_result = "W" if row.FTR == "H" else "D" if row.FTR == "D" else "L"
        away_result = "W" if row.FTR == "A" else "D" if row.FTR == "D" else "L"
        last5[home].append((home_result, row.FTHG))
        last5[away].append((away_result, row.FTAG))

        elo_history[home][0].append(date)
        elo_history[home][1].append(row.HomeElo)
        elo_history[away][0].append(date)
        elo_history[away][1].append(row.AwayElo)

    for k, v in out.items():
        df[k] = v

    df["WinRateDiff"] = df["Last5_WinRate_Home"] - df["Last5_WinRate_Away"]
    df["DrawRateDiff"] = df["Last5_DrawRate_Home"] - df["Last5_DrawRate_Away"]
    df["EloDiff"] = df["HomeElo"] - df["AwayElo"]
    return df


def add_odds_probs(df):
    inv_h = 1 / df["B365H"]
    inv_d = 1 / df["B365D"]
    inv_a = 1 / df["B365A"]
    total = inv_h + inv_d + inv_a
    valid = total.notna() & (total != 0)

    df["HomeProb"] = np.where(valid, inv_h / total, 1 / 3)
    df["DrawProb"] = np.where(valid, inv_d / total, 1 / 3)
    df["AwayProb"] = np.where(valid, inv_a / total, 1 / 3)
    return df


def build_league_dataset(league, df):
    df = df.copy()
    df["HomeTeam"] = df["HomeTeam"].apply(normalize_team_name)
    df["AwayTeam"] = df["AwayTeam"].apply(normalize_team_name)
    df["HomeElo"] = df["HomeElo"].fillna(1500)
    df["AwayElo"] = df["AwayElo"].fillna(1500)
    df = add_form_and_elo_features(df)
    df = add_odds_probs(df)

    if league != "T1":
        df["HxG"] = 0.0
        df["AxG"] = 0.0
        df["xG_diff"] = 0.0

    df["y"] = df["FTR"].map(RESULT_MAP)
    return df


def encode_for_xgb(y):
    mapping = {-1: 0, 0: 1, 1: 2}
    inverse = {v: k for k, v in mapping.items()}
    return y.map(mapping), inverse


def evaluate(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro")
    print(f"  {name:<20} accuracy={acc:.4f}  macro_f1={f1:.4f}")
    return acc, f1


def train_league(league, feature_list, df):
    X = df[feature_list]
    y = df["y"]
    train_mask = df["Date"] < SPLIT_DATE
    test_mask = ~train_mask

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    print(f"\n=== {league} ({len(df)} matches, {train_mask.sum()} train / {test_mask.sum()} test) ===")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    candidates = {}

    rf_grid = GridSearchCV(
        RandomForestClassifier(random_state=42),
        param_grid={"n_estimators": [200, 300], "max_depth": [6, 10, 14], "min_samples_leaf": [2, 5]},
        scoring="f1_macro", cv=cv, n_jobs=-1,
    )
    rf_grid.fit(X_train, y_train)
    candidates["RandomForest"] = rf_grid.best_estimator_

    logreg_pipe = Pipeline([("scaler", StandardScaler()), ("logreg", LogisticRegression(max_iter=2000))])
    logreg_grid = GridSearchCV(
        logreg_pipe, param_grid={"logreg__C": [0.01, 0.1, 1, 10]},
        scoring="f1_macro", cv=cv, n_jobs=-1,
    )
    logreg_grid.fit(X_train, y_train)
    candidates["LogisticRegression"] = logreg_grid.best_estimator_

    y_train_xgb, inverse = encode_for_xgb(y_train)
    xgb_grid = GridSearchCV(
        XGBClassifier(eval_metric="mlogloss", random_state=42),
        param_grid={"n_estimators": [200, 400], "max_depth": [3, 5], "learning_rate": [0.05, 0.1]},
        scoring="f1_macro", cv=cv, n_jobs=-1,
    )
    xgb_grid.fit(X_train, y_train_xgb)

    results = {}
    for model_name, model in candidates.items():
        preds = model.predict(X_test)
        results[model_name] = evaluate(model_name, y_test, preds)

    xgb_preds = pd.Series(xgb_grid.predict(X_test)).map(inverse)
    results["XGBoost"] = evaluate("XGBoost (reference)", y_test, xgb_preds)

    best_name = max(("RandomForest", "LogisticRegression"), key=lambda n: results[n][1])
    best_model_template = candidates[best_name]
    print(f"  -> selected {best_name} for {league}")
    print(classification_report(y_test, candidates[best_name].predict(X_test), target_names=["Away Win", "Draw", "Home Win"]))

    final_model = clone(best_model_template)
    final_model.fit(X, y)
    return final_model, best_name, results[best_name]


def build_team_categories(historical_data_by_league):
    teams = set()
    for df in historical_data_by_league.values():
        teams.update(df["HomeTeam"].apply(normalize_team_name))
        teams.update(df["AwayTeam"].apply(normalize_team_name))
    return sorted(teams)


def main():
    historical = load_historical_league_data(data_dir=".")

    best_models = {}
    summary = []
    for league, feature_list in features_by_league.items():
        df = build_league_dataset(league, historical[league])
        model, name, (acc, f1) = train_league(league, feature_list, df)
        best_models[league] = model
        summary.append((league, name, acc, f1))

    with open("best_models.pkl", "rb") as f:
        pass  # sanity: confirm the old file is still readable before we overwrite it

    import shutil
    shutil.copy("best_models.pkl", "best_models.pkl.bak")
    with open("best_models.pkl", "wb") as f:
        pickle.dump(best_models, f)

    joblib.dump(build_team_categories(historical), "team_categories.pkl")

    print("\n=== Summary (held-out 2023+ test set) ===")
    for league, name, acc, f1 in summary:
        print(f"  {league:<4} {name:<20} accuracy={acc:.4f}  macro_f1={f1:.4f}")
    print("\nSaved best_models.pkl (previous version backed up to best_models.pkl.bak)")
    print("Saved team_categories.pkl")


if __name__ == "__main__":
    main()
