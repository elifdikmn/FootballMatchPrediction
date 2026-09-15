from apscheduler.schedulers.blocking import BlockingScheduler
from update_data import (
    update_scheduled_fixtures,
    update_all_standings,
    import_upcoming_week_fixtures
)
from update_cache_from_api import update_prediction_cache_from_own_models

# ⚙️ Zamanlayıcı başlatılıyor
scheduler = BlockingScheduler()

@scheduler.scheduled_job('interval', minutes=30)
def scheduled_update():
    print("🔁 [SCHEDULER] Güncelleme başladı...")

    # 1. Scheduled maçları kontrol et
    update_scheduled_fixtures()

    # 2. Standings güncelle (6 lig)
    update_all_standings()

    # 3. Gelecek 7 gün içindeki yeni maçları ekle
    import_upcoming_week_fixtures()

    # 4. Kendi modelimizle scheduled maçlar için tahmin cache'ini güncelle
    update_prediction_cache_from_own_models()

    print("✅ [SCHEDULER] Güncelleme tamamlandı.\n")

if __name__ == "__main__":
    print("🕒 run_scheduler.py çalışıyor... Her 30 dakikada bir veri güncellenecek.")
    scheduler.start()
