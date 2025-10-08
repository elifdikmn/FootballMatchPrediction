import re
import json
from pathlib import Path

CACHE_FILE = Path("prediction_cache.json")

# 1. JSON dosyasını düz metin olarak oku
with open(CACHE_FILE, "r") as f:
    raw = f.read()

# 2. NaN -> null (JSON standardına çevir)
# Not: sadece NaN olan değerleri hedef alır
cleaned_raw = re.sub(r'(?<=:\s)NaN', 'null', raw)

# 3. Dönüştürülmüş hali kontrol et
try:
    data = json.loads(cleaned_raw)
except json.JSONDecodeError as e:
    print("❌ JSON hala bozuk:", e)
    exit(1)

# 4. Temizlenmiş JSON’u yeniden yaz
with open(CACHE_FILE, "w") as f:
    json.dump(data, f, indent=2)

print("✅ prediction_cache.json içindeki NaN -> null dönüştürüldü.")
