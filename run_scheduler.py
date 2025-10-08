from apscheduler.schedulers.blocking import BlockingScheduler
from update_data import (
    update_scheduled_fixtures,
    update_all_standings,
    import_upcoming_week_fixtures
)
from datetime import date, timedelta

# Takvim bilgisi
TODAY = date.today()
NEXT_WEEK = TODAY + timedelta(days=7)

# ⚙️ Zamanlayıcı başlatılıyor
scheduler = BlockingScheduler()

@scheduler.scheduled_job('interval', minutes=30)
def scheduled_update():
    print("🔁 [SCHEDULER] Güncelleme başladı...")

    # 1. Scheduled maçları kontrol et
    update_scheduled_fixtures()

    # 2. Standings güncelle (6 lig)
    update_all_standings()

    # 3. (Opsiyonel) Gelecek 7 gün içindeki yeni maçları ekle
    leagues = [32,15,5,203, 39, 140, 135, 61, 78]  # Süper Lig, EPL, La Liga, Serie A, Ligue 1, Bundesliga
    for league_id in leagues:
        import_upcoming_week_fixtures(league_id, str(TODAY), str(NEXT_WEEK))

    print("✅ [SCHEDULER] Güncelleme tamamlandı.\n")

if __name__ == "__main__":
    print("🕒 run_scheduler.py çalışıyor... Her 30 dakikada bir veri güncellenecek.")
    scheduler.start()
