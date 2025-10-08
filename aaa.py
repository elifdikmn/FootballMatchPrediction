def deduplicate_events_cache(file_path="events_cache.json"):
    import json
    from collections import defaultdict

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned = defaultdict(list)

    for fixture_id, events in data.items():
        seen = set()
        for e in events:
            key = f"{e['minute']}-{e['player']}"
            if key in seen:
                continue
            seen.add(key)
            cleaned[fixture_id].append(e)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print("✅ Duplicate event'ler temizlenerek yazıldı.")
if __name__ == "__main__":
    deduplicate_events_cache()
