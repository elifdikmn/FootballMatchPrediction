import json
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report

# JSON dosyasını oku
with open("prediction_cache.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Sözlükten listeye dönüştür
data = list(raw_data.values())

# DataFrame'e çevir
df = pd.DataFrame(data)

# Sadece bitmiş maçlar
df = df[df["Status"] == "FINISHED"]

# Gerçek sonucu belirle
def get_actual_label(row):
    if row["HomeGoals"] > row["AwayGoals"]:
        return "Home Win"
    elif row["HomeGoals"] < row["AwayGoals"]:
        return "Away Win"
    else:
        return "Draw"

df["Actual_Label"] = df.apply(get_actual_label, axis=1)

# Lig bazlı değerlendirme
leagues = df["League"].unique()

print("\n📊 Lig Bazlı Model Performansı:\n")

summary = []

for league in leagues:
    sub_df = df[df["League"] == league]

    y_true = sub_df["Actual_Label"]
    y_pred = sub_df["Predicted_Label"]

    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro")

    print(f"📌 {league} Ligi:")
    print(f"   🔹 Accuracy: {acc:.4f}")
    print(f"   🔹 Macro F1 Score: {f1:.4f}")
    print(f"   🔹 Maç Sayısı: {len(sub_df)}")
    print(classification_report(y_true, y_pred, target_names=["Away Win", "Draw", "Home Win"]))
    print("-" * 50)

    summary.append({
        "League": league,
        "Accuracy": acc,
        "F1_macro": f1,
        "Samples": len(sub_df)
    })

# Özet tabloyu yazdır
summary_df = pd.DataFrame(summary).sort_values("F1_macro", ascending=False).round(4)
print("\n✅ Lig Bazlı Özet Skorlar:")
print(summary_df.to_string(index=False))
