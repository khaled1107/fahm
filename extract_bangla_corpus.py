#!/usr/bin/env python3
"""
extract_bangla_corpus.py

Extracts Bangla translations and tafsirs from the Quran Foundation API:

Translations:
  - Taisirul Quran       (ID 161) — primary Bangla translation
  - Rawai Al-bayan       (ID 162) — secondary Bangla translation

Tafsirs:
  - Ibn Kathir Bengali   (ID 164) — primary Bangla tafsir
  - Abu Bakr Zakaria     (ID 166) — secondary Bangla tafsir

Outputs (in corpus/):
  - translation_bn_taisirul.json       — raw, keyed by verse_key
  - translation_bn_rawai.json          — raw, keyed by verse_key
  - tafsir_bn_ibn_kathir_raw.json      — raw, keyed by verse_key
  - tafsir_bn_ibn_kathir_propagated.json
  - tafsir_bn_abu_bakr_raw.json        — raw, keyed by verse_key
  - tafsir_bn_abu_bakr_propagated.json

Usage:
    python3 extract_bangla_corpus.py

Env vars required:
    QF_CLIENT_ID, QF_CLIENT_SECRET
"""

import os, json, time, re, requests
from pathlib import Path
from requests.auth import HTTPBasicAuth

API_BASE  = "https://apis.quran.foundation/content/api/v4"
AUTH_URL  = "https://oauth2.quran.foundation/oauth2/token"
OUTPUT_DIR = Path("corpus")
OUTPUT_DIR.mkdir(exist_ok=True)

QF_CLIENT_ID     = os.environ["QF_CLIENT_ID"]
QF_CLIENT_SECRET = os.environ["QF_CLIENT_SECRET"]

VERSE_COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,
                110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,
                182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,
                29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,
                50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,
                8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]

TRANSLATIONS = [
    {"id": 161, "name": "bn_taisirul", "label": "Taisirul Quran (Bangla)"},
    {"id": 162, "name": "bn_rawai",    "label": "Rawai Al-bayan (Bangla)"},
]

TAFSIRS = [
    {"id": 164, "name": "bn_ibn_kathir", "label": "Ibn Kathir Bengali"},
    {"id": 166, "name": "bn_abu_bakr",   "label": "Abu Bakr Zakaria"},
]

def get_token():
    r = requests.post(
        AUTH_URL,
        auth=HTTPBasicAuth(QF_CLIENT_ID, QF_CLIENT_SECRET),
        data={"grant_type": "client_credentials", "scope": "content"}
    )
    r.raise_for_status()
    return r.json()["access_token"]

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ── TRANSLATIONS ──────────────────────────────────────────────

def fetch_translation_chapter(translation_id, chapter, token):
    """Fetch all pages of a translation for one chapter."""
    results = {}
    page = 1
    headers = {"x-auth-token": token, "x-client-id": QF_CLIENT_ID}

    while True:
        url = (f"{API_BASE}/verses/by_chapter/{chapter}"
               f"?translations={translation_id}&per_page=50&page={page}"
               f"&fields=verse_key")
        r = requests.get(url, headers=headers)

        if r.status_code == 401:
            print(f"    Token expired, refreshing...")
            token = get_token()
            headers["x-auth-token"] = token
            continue

        r.raise_for_status()
        data = r.json()

        for verse in data.get("verses", []):
            vk = verse.get("verse_key", "")
            translations = verse.get("translations", [])
            if translations and vk:
                results[vk] = clean_html(translations[0].get("text", ""))

        pagination = data.get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break
        page += 1
        time.sleep(0.15)

    return results, token

def extract_translation(config):
    t_id   = config["id"]
    name   = config["name"]
    label  = config["label"]
    output = OUTPUT_DIR / f"translation_{name}.json"

    print(f"\n{'='*60}")
    print(f"Extracting translation: {label} (ID {t_id})")
    print(f"{'='*60}")

    token = get_token()
    all_results = {}

    for ch in range(1, 115):
        expected = VERSE_COUNTS[ch - 1]
        print(f"  Chapter {ch:3d}/114 ({expected} verses)...", end=" ", flush=True)
        results, token = fetch_translation_chapter(t_id, ch, token)
        all_results.update(results)
        print(f"got {len(results)}")
        time.sleep(0.2)

    total = len(all_results)
    print(f"\nTotal verses: {total}")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output}")

    # Validation
    missing = [f"{ch}:{v}" for ch, cnt in enumerate(VERSE_COUNTS, 1)
               for v in range(1, cnt + 1) if f"{ch}:{v}" not in all_results]
    if missing:
        print(f"WARNING: {len(missing)} verses missing. First 10: {missing[:10]}")
    else:
        print("All verses accounted for.")

# ── TAFSIRS ───────────────────────────────────────────────────

def fetch_tafsir_chapter(tafsir_id, chapter, token):
    """Fetch all pages of tafsir for one chapter."""
    entries = []
    page = 1
    headers = {"x-auth-token": token, "x-client-id": QF_CLIENT_ID}

    while True:
        url = f"{API_BASE}/tafsirs/{tafsir_id}/by_chapter/{chapter}"
        r = requests.get(url, headers=headers, params={"per_page": 50, "page": page})

        if r.status_code == 401:
            print(f"    Token expired, refreshing...")
            token = get_token()
            headers["x-auth-token"] = token
            continue

        r.raise_for_status()
        data = r.json()
        entries.extend(data.get("tafsirs", []))

        pagination = data.get("pagination", {})
        if not pagination.get("next_page"):
            break
        page += 1
        time.sleep(0.1)

    return entries, token

def propagate_tafsir(tafsir_by_vk, surah_num):
    """Propagate tafsir forward within a surah to fill gaps."""
    verse_count = VERSE_COUNTS[surah_num - 1]
    last = None
    for v in range(1, verse_count + 1):
        vk = f"{surah_num}:{v}"
        if vk in tafsir_by_vk and tafsir_by_vk[vk]:
            last = tafsir_by_vk[vk]
        elif last:
            tafsir_by_vk[vk] = last
    return tafsir_by_vk

def extract_tafsir(config):
    t_id   = config["id"]
    name   = config["name"]
    label  = config["label"]
    raw_path  = OUTPUT_DIR / f"tafsir_{name}_raw.json"
    prop_path = OUTPUT_DIR / f"tafsir_{name}_propagated.json"

    print(f"\n{'='*60}")
    print(f"Extracting tafsir: {label} (ID {t_id})")
    print(f"{'='*60}")

    token = get_token()
    all_raw = {}

    for ch in range(1, 115):
        print(f"  Chapter {ch:3d}/114...", end=" ", flush=True)
        entries, token = fetch_tafsir_chapter(t_id, ch, token)

        ch_entries = {}
        for entry in entries:
            vk = entry.get("verse_key", "")
            text = clean_html(entry.get("text", ""))
            if vk and text:
                ch_entries[vk] = text

        all_raw.update(ch_entries)
        print(f"got {len(ch_entries)} entries")
        time.sleep(0.2)

    print(f"\nRaw entries: {len(all_raw)}")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_raw, f, ensure_ascii=False, indent=2)
    print(f"Saved raw to {raw_path}")

    # Propagate
    all_propagated = dict(all_raw)
    for ch in range(1, 115):
        propagate_tafsir(all_propagated, ch)

    print(f"Propagated entries: {len(all_propagated)}")
    with open(prop_path, "w", encoding="utf-8") as f:
        json.dump(all_propagated, f, ensure_ascii=False, indent=2)
    print(f"Saved propagated to {prop_path}")

# ── MAIN ──────────────────────────────────────────────────────

def main():
    print("Fahm — Bangla Corpus Extraction")
    print("="*60)

    for config in TRANSLATIONS:
        extract_translation(config)

    for config in TAFSIRS:
        extract_tafsir(config)

    print("\n" + "="*60)
    print("Done. Files written to corpus/:")
    print("  translation_bn_taisirul.json")
    print("  translation_bn_rawai.json")
    print("  tafsir_bn_ibn_kathir_raw.json")
    print("  tafsir_bn_ibn_kathir_propagated.json")
    print("  tafsir_bn_abu_bakr_raw.json")
    print("  tafsir_bn_abu_bakr_propagated.json")

if __name__ == "__main__":
    main()
