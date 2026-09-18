import json
from datetime import datetime

# Global cache (main.py'de çağrıldığında boş olacak)
live_prediction_cache = {}

def cache_live_prediction(fixture_id, result_row):
    result_row["timestamp"] = datetime.now().isoformat()
    live_prediction_cache[fixture_id] = result_row

def save_cache_to_file(path="live_prediction_cache.json"):
    with open(path, "w") as f:
        json.dump(live_prediction_cache, f, indent=2)

def load_cache_from_file(path="live_prediction_cache.json"):
    global live_prediction_cache
    try:
        with open(path, "r") as f:
            live_prediction_cache = json.load(f)
    except FileNotFoundError:
        live_prediction_cache = {}

def update_actual_result_in_cache(fixture_id, actual_result_code):
    if fixture_id in live_prediction_cache:
        live_prediction_cache[fixture_id]["actual_result"] = actual_result_code
