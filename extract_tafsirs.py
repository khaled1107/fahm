#!/usr/bin/env python3
"""
extract_tafsirs.py

Extracts three English tafsirs from the Quran Foundation API:
- Ibn Kathir (ID 169)
- Ma'arif al-Qur'an (ID 168)
- Tazkirul Quran (ID 817)

Saves raw keyed JSON and propagated JSON for each.

Usage:
    python3 extract_tafsirs.py

Env vars required:
    QF_CLIENT_ID, QF_CLIENT_SECRET
"""

import os, json, time, requests
from pathlib import Path
from requests.auth import HTTPBasicAuth

# --- Config ---
API_BASE = "https://apis.quran.foundation/content/api/v4"
AUTH_URL = "https://oauth2.quran.foundation/oauth2/token"
OUTPUT_DIR = Path("corpus")
OUTPUT_DIR.mkdir(exist_ok=True)

QF_CLIENT_ID = os.environ["QF_CLIENT_ID"]
QF_CLIENT_SECRET = os.environ["QF_CLIENT_SECRET"]

TAFSIRS = [
    {"id": 169, "name": "ibn_kathir",  "label": "Ibn Kathir"},
    {"id": 168, "name": "maarif",      "label": "Ma'arif al-Qur'an"},
    {"id": 817, "name": "tazkirul",    "label": "Tazkirul Quran"},
]

# Standard verse counts per surah for propagation
VERSE_COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,
                110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,
                182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,
                29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,
                50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,
                8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]

def get_token():
    r = requests.post(
        AUTH_URL,
        auth=HTTPBasicAuth(QF_CLIENT_ID, QF_CLIENT_SECRET),
        data={"grant_type": "client_credentials", "scope": "content"}
    )
    r.raise_for_status()
    return r.json()["access_token"]

def fetch_tafsir_chapter(tafsir_id, chapter, token):
    """Fetch all pages of tafsir for a chapter. Returns list of tafsir entries."""
    entries = []
    page = 1
    headers = {
        "x-auth-token": token,
        "x-client-id": QF_CLIENT_ID
    }

    while True:
        url = f"{API_BASE}/tafsirs/{tafsir_id}/by_chapter/{chapter}"
        params = {"per_page": 50, "page": page}

        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

        page_entries = data.get("tafsirs", [])
        entries.extend(page_entries)

        pagination = data.get("pagination", {})
        next_page = pagination.get("next_page")
        if not next_page:
            break

        page += 1
        time.sleep(0.1)

    return entries

def propagate_tafsir(tafsir_by_verse_key, surah_num):
    """
    Propagate tafsir forward within a surah.
    Ibn Kathir (and possibly others) attach tafsir only to the first verse
    in a group. Copy forward until a verse has its own entry.
    """
    verse_count = VERSE_COUNTS[surah_num - 1] if surah_num <= len(VERSE_COUNTS) else 0
    last_tafsir = None

    for verse_num in range(1, verse_count + 1):
        vk = f"{surah_num}:{verse_num}"
        if vk in tafsir_by_verse_key and tafsir_by_verse_key[vk]:
            last_tafsir = tafsir_by_verse_key[vk]
        elif last_tafsir:
            tafsir_by_verse_key[vk] = last_tafsir

    return tafsir_by_verse_key

def extract_tafsir(tafsir_config):
    tafsir_id = tafsir_config["id"]
    name = tafsir_config["name"]
    label = tafsir_config["label"]

    raw_path = OUTPUT_DIR / f"tafsir_{name}.json"
    propagated_path = OUTPUT_DIR / f"tafsir_{name}_propagated.json"

    print(f"\n{'='*60}")
    print(f"Extracting: {label} (ID {tafsir_id})")
    print(f"{'='*60}")

    token = get_token()
    token_call_count = 0

    all_entries = {}  # verse_key -> tafsir text
    total_entries = 0

    for ch in range(1, 115):
        # Refresh token every 30 chapters
        token_call_count += 1
        if token_call_count % 30 == 0:
            token = get_token()

        try:
            entries = fetch_tafsir_chapter(tafsir_id, ch, token)

            chapter_map = {}
            for entry in entries:
                vk = entry.get("verse_key", "")
                text = entry.get("text", "").strip()
                if vk and text:
                    chapter_map[vk] = text

            all_entries.update(chapter_map)
            total_entries += len(chapter_map)
            print(f"  Ch {ch:3d}: {len(chapter_map):3d} entries fetched", end="")

            # Show pagination info if chapter had multiple pages
            if len(entries) == 50:
                print(f" (may have had multiple pages)", end="")
            print()

        except Exception as e:
            print(f"  Ch {ch:3d}: ERROR — {e}")

        time.sleep(0.3)

    # Save raw file
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    print(f"\nRaw file saved: {raw_path} ({total_entries} entries)")

    # Apply propagation
    print("Applying tafsir propagation...")
    propagated = dict(all_entries)
    for surah_num in range(1, 115):
        propagated = propagate_tafsir(propagated, surah_num)

    propagated_count = sum(1 for v in propagated.values() if v)
    with open(propagated_path, "w", encoding="utf-8") as f:
        json.dump(propagated, f, ensure_ascii=False, indent=2)
    print(f"Propagated file saved: {propagated_path} ({propagated_count} verses covered)")

    return total_entries, propagated_count


# --- Main ---
print("Quran Foundation Tafsir Extractor")
print(f"Extracting {len(TAFSIRS)} tafsirs for all 114 chapters\n")

results = []
for tafsir_config in TAFSIRS:
    raw_count, prop_count = extract_tafsir(tafsir_config)
    results.append({
        "label": tafsir_config["label"],
        "id": tafsir_config["id"],
        "raw_entries": raw_count,
        "propagated_verses": prop_count
    })
    time.sleep(1)

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for r in results:
    print(f"{r['label']} (ID {r['id']})")
    print(f"  Raw entries:        {r['raw_entries']}")
    print(f"  Propagated verses:  {r['propagated_verses']}")
    print()

print("Done. Files saved to corpus/:")
for tafsir_config in TAFSIRS:
    print(f"  tafsir_{tafsir_config['name']}.json")
    print(f"  tafsir_{tafsir_config['name']}_propagated.json")
