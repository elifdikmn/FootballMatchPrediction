import pandas as pd
import json
from db_utils import save_model_prediction
from db_setup import SessionLocal
from models import Fixture

from config import(
    features,
    live_features,
    features_tr,
    features_by_league
)
import datetime
import numpy as np

import pickle

def load_best_models(path="best_models.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_from_merged_df(merged_df, best_models, features_by_league):
    prediction_rows = []

    for _, row in merged_df.iterrows():
        fixture_id = row["FixtureID"]
        league = row["League"]

        model = best_models.get(league)
        feature_list = features_by_league.get(league)

        if model is None or feature_list is None:
            continue

        

        # 🧠 Özellikleri doldur
        row_filled = {}
        for f in feature_list:
            value = row.get(f)
            if pd.notna(value):
                row_filled[f] = value
            else:
                fallback = merged_df[f].mean() if f in merged_df and not merged_df[f].isna().all() else 0
                row_filled[f] = fallback

        # 📦 Model girdisi
        X_input = pd.DataFrame([row_filled])

        # 🔮 Tahmin
        predicted = model.predict(X_input)[0]
        proba = model.predict_proba(X_input)[0]

        pred_label = {1: "Home Win", 0: "Draw", -1: "Away Win"}[predicted]

        result = {
         "FixtureID": fixture_id,
            "Date": str(row.get("Date")) if row.get("Date") else None,
            "League": row.get("League"),
            "HomeTeam": row.get("HomeTeam"),
            "AwayTeam": row.get("AwayTeam"),
            "Predicted_Label": pred_label,
            "Home Win %": round(proba[2] * 100, 2),
            "Draw %": round(proba[1] * 100, 2),
            "Away Win %": round(proba[0] * 100, 2),
            "HomeGoals": row.get("HomeGoals"),
            "AwayGoals": row.get("AwayGoals"),
            "Status": row.get("Status")
        }

        save_model_prediction(result)
        prediction_rows.append(result)

    return pd.DataFrame(prediction_rows)

