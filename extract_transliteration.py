#!/usr/bin/env python3
"""
extract_transliteration.py

Extracts full-verse transliteration for all 6,236 verses from the
Quran Foundation API using translations=57 (English transliteration resource).

Output: corpus/transliteration.json
  {
    "78:1": "ʿamma yatasāʾalūn",
    "78:2": "ʿani l-nabaʾi l-ʿaẓīm",
    ...
  }

Usage:
    python3 extract_transliteration.py

Env vars required:
    QF_CLIENT_ID, QF_CLIENT_SECRET
"""

import os, json, time, requests
from pathlib import Path
from requests.auth import HTTPBasicAuth

API_BASE  = "https://apis.quran.foundation/content/api/v4"
AUTH_URL  = "https://oauth2.quran.foundation/oauth2/token"
OUTPUT    = Path("corpus/transliteration.json")

QF_CLIENT_ID     = os.environ["QF_CLIENT_ID"]
QF_CLIENT_SECRET = os.environ["QF_CLIENT_SECRET"]

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

def fetch_chapter_transliteration(chapter, token):
    """Fetch all pages of verses with transliteration for a chapter."""
    results = {}
    page = 1
    headers = {"x-auth-token": token, "x-client-id": QF_CLIENT_ID}

    while True:
        url = (f"{API_BASE}/verses/by_chapter/{chapter}"
               f"?translations=57&per_page=50&page={page}"
               f"&fields=verse_key")
        r = requests.get(url, headers=headers)

        if r.status_code == 401:
            print(f"  Token expired at chapter {chapter} page {page}, refreshing...")
            token = get_token()
            headers["x-auth-token"] = token
            continue

        r.raise_for_status()
        data = r.json()
        verses = data.get("verses", [])

        for verse in verses:
            vk = verse.get("verse_key", "")
            translations = verse.get("translations", [])
            if translations and vk:
                # Strip any HTML tags from the transliteration text
                text = translations[0].get("text", "")
                import re
                text = re.sub(r"<[^>]+>", "", text).strip()
                results[vk] = text

        pagination = data.get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break
        page += 1
        time.sleep(0.15)

    return results, token

def main():
    print("Extracting transliteration for all 114 chapters...")
    token = get_token()
    all_transliteration = {}
    total_chapters = 114

    for ch in range(1, total_chapters + 1):
        expected = VERSE_COUNTS[ch - 1]
        print(f"  Chapter {ch:3d}/114 ({expected} verses)...", end=" ", flush=True)

        results, token = fetch_chapter_transliteration(ch, token)
        all_transliteration.update(results)
        print(f"got {len(results)} verses")
        time.sleep(0.2)

    total = len(all_transliteration)
    print(f"\nTotal verses extracted: {total}")

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_transliteration, f, ensure_ascii=False, indent=2)

    print(f"Saved to {OUTPUT}")

    # Quick validation
    missing = []
    for ch, count in enumerate(VERSE_COUNTS, 1):
        for v in range(1, count + 1):
            if f"{ch}:{v}" not in all_transliteration:
                missing.append(f"{ch}:{v}")
    if missing:
        print(f"WARNING: {len(missing)} verses missing transliteration:")
        for vk in missing[:10]:
            print(f"  {vk}")
        if len(missing) > 10:
            print(f"  ... and {len(missing)-10} more")
    else:
        print("All verses accounted for.")

if __name__ == "__main__":
    main()
