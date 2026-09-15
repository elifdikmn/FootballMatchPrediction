from sqlalchemy.orm import Session
from db_setup import SessionLocal
from models import Fixture
from collections import defaultdict

def evaluate_model_accuracy():
    db: Session = SessionLocal()
    try:
        finished_fixtures = db.query(Fixture).filter_by(Status="FINISHED").all()
    finally:
        db.close()

    total = 0
    correct = 0
    wrong_fixtures = []
    league_stats = defaultdict(lambda: {"total": 0, "correct": 0})

    for f in finished_fixtures:
        if f.HomeGoals is None or f.AwayGoals is None or f.Predicted_Label is None:
            continue  # eksik veri varsa geç

        if f.HomeGoals > f.AwayGoals:
            actual = "Home Win"
        elif f.HomeGoals < f.AwayGoals:
            actual = "Away Win"
        else:
            actual = "Draw"

        predicted = f.Predicted_Label

        is_correct = (predicted == actual)
        if is_correct:
            correct += 1
        else:
            wrong_fixtures.append({
                "FixtureID": f.FixtureID,
                "League": f.League,
                "HomeTeam": f.HomeTeam,
                "AwayTeam": f.AwayTeam,
                "Score": f"{f.HomeGoals}-{f.AwayGoals}",
                "Predicted": predicted,
                "Actual": actual
            })

        total += 1

        # Lig bazlı istatistik
        league_stats[f.League]["total"] += 1
        if is_correct:
            league_stats[f.League]["correct"] += 1

    # Genel başarı oranı
    overall_accuracy = round((correct / total) * 100, 2) if total > 0 else 0.0

    # Lig bazlı başarı
    league_accuracy = {
        league: round((v["correct"] / v["total"]) * 100, 2)
        for league, v in league_stats.items() if v["total"] > 0
    }

    return {
        "total_finished": total,
        "correct_predictions": correct,
        "overall_accuracy": overall_accuracy,
        "league_accuracy": league_accuracy,
        "wrong_predictions": wrong_fixtures
    }

# Lokal test için
if __name__ == "__main__":
    stats = evaluate_model_accuracy()
    print(f"\n✅ GENEL DOĞRULUK: {stats['overall_accuracy']}%")
    print(f"📊 Lig Bazlı:\n{stats['league_accuracy']}")
    print(f"\n❌ Yanlış Tahminler ({len(stats['wrong_predictions'])} maç):")
    for m in stats['wrong_predictions'][:5]:  # sadece ilk 5'i göster
        print(f"- {m['HomeTeam']} vs {m['AwayTeam']} | Skor: {m['Score']} | Tahmin: {m['Predicted']} | Gerçek: {m['Actual']}")
