import pandas as pd
from datetime import datetime
from fixture import get_combined_fixtures_with_odds, save_predictions_to_cache
from prediction_pipeline import load_best_models, predict_from_merged_df
from feature_engineering import build_features_dataframe
from config import features_by_league

# 🔄 Tüm maçları al
df = get_combined_fixtures_with_odds()

# 🔍 Sadece planlanmış ve bugünden sonraki maçları al
today = datetime.utcnow().date()
df = df[(df["Status"] == "SCHEDULED") & (df["Date"] >= today)]

if df.empty:
    print("📭 Yeni planlanmış maç yok.")
    exit()

print(f"🔍 {len(df)} maç için tahmin hazırlanıyor...")

# 🧠 Özellik çıkar
historical_data_by_league = {
    "T1": pd.read_csv("T1_matches.csv", parse_dates=["Date"]),
    "E0": pd.read_csv("E0_matches.csv", parse_dates=["Date"]),
    "F1": pd.read_csv("F1_matches.csv", parse_dates=["Date"]),
    "D1": pd.read_csv("D1_matches.csv", parse_dates=["Date"]),
    "SP1": pd.read_csv("SP1_matches.csv", parse_dates=["Date"]),
    "I1": pd.read_csv("I1_matches.csv", parse_dates=["Date"]),
}

feature_df = build_features_dataframe(df.to_dict(orient="records"), historical_data_by_league)

if feature_df.empty:
    print("❌ Özellik çıkarılamadı.")
    exit()

# 🔮 Tahmin yap
best_models = load_best_models()
predicted_df = predict_from_merged_df(feature_df, best_models, features_by_league)

if predicted_df.empty:
    print("❌ Tahmin yapılamadı.")
    exit()

# 🔁 Odds dictionary
# DOĞRU OLAN:
odds_dict = {
    int(row["FixtureID"]): {
        "HomeWinPct": row.get("B365H"),
        "DrawPct": row.get("B365D"),
        "AwayWinPct": row.get("B365A")
    }
    for _, row in df.iterrows()  # ⚠️ dikkat: df, predicted_df değil!
}


# 💾 Cache'e yaz
save_predictions_to_cache(predicted_df.to_dict(orient="records"))

print("✅ Yeni tahminler prediction_cache.json dosyasına eklendi.")
