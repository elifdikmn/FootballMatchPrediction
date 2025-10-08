import json
import requests
import time

PREDICTION_CACHE_FILE = "prediction_cache.json"
EVENTS_CACHE_FILE = "events_cache.json"
API_BASE_URL = "http://localhost:5000"

def load_fixture_ids():
    with open(PREDICTION_CACHE_FILE, "r") as f:
        predictions = json.load(f)
    return list(predictions.keys())

def fetch_events_for_fixture(fixture_id):
    url = f"{API_BASE_URL}/events/{fixture_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching {fixture_id}: {e}")
        return []

def build_events_cache():
    fixture_ids = load_fixture_ids()
    print(f"🔍 Found {len(fixture_ids)} fixture IDs in prediction_cache.json")

    all_events = {}
    for i, fixture_id in enumerate(fixture_ids):
        print(f"📦 [{i+1}/{len(fixture_ids)}] Fetching events for {fixture_id}...")
        events = fetch_events_for_fixture(fixture_id)
        all_events[fixture_id] = events
        time.sleep(0.5)  # ⏱ Delay to avoid spamming the server

    with open(EVENTS_CACHE_FILE, "w") as f:
        json.dump(all_events, f, indent=2)

    print(f"✅ Saved all events to {EVENTS_CACHE_FILE}")

if __name__ == "__main__":
    build_events_cache()
