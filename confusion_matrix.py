import json
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    classification_report,
)
import matplotlib.pyplot as plt

# 📥 1. JSON dosyasını oku
with open("prediction_cache.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# 📊 2. JSON'dan DataFrame'e dönüştür
df = pd.DataFrame(list(raw_data.values()))

# ⏹ 3. Sadece tamamlanmış maçları al
df = df[df["Status"] == "FINISHED"]

# 🎯 4. Gerçek sonucu hesapla
def get_actual_label(row):
    if row["HomeGoals"] > row["AwayGoals"]:
        return "Home Win"
    elif row["HomeGoals"] < row["AwayGoals"]:
        return "Away Win"
    else:
        return "Draw"

df["Actual_Label"] = df.apply(get_actual_label, axis=1)

# 🧼 5. Boş değerleri filtrele
df = df.dropna(subset=["Actual_Label", "Predicted_Label"])

# 🎯 6. Confusion Matrix ve metrikler
y_true = df["Actual_Label"]
y_pred = df["Predicted_Label"]
labels = ["Home Win", "Draw", "Away Win"]

cm = confusion_matrix(y_true, y_pred, labels=labels)
acc = accuracy_score(y_true, y_pred)
f1 = f1_score(y_true, y_pred, average="macro")

# 📋 7. Sonuçları yazdır
print(f"🔎 Accuracy: {acc:.4f} → %{acc * 100:.2f}")
print(f"🎯 Macro F1 Score: {f1:.4f} → %{f1 * 100:.2f}")
print("\n📋 Classification Report:")
print(classification_report(y_true, y_pred, labels=labels))

# 📈 8. Confusion matrix görselleştir
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
disp.plot(cmap="Blues", values_format='d')
plt.title("Confusion Matrix for All Leagues (Finished Matches)")
plt.show()
