#!/usr/bin/env python3
"""
fix_tafsir_pagination.py
Re-fetches ALL tafsir pages for all 114 chapters, replaces tafsir in full_corpus.json,
propagates tafsir forward within each chapter, then saves the fixed corpus.
Run this, then re-run build_chunks.py.
"""

import os, json, time, requests

# --- Auth ---
QF_CLIENT_ID = os.environ["QF_CLIENT_ID"]
QF_CLIENT_SECRET = os.environ["QF_CLIENT_SECRET"]
API_BASE = "https://apis.quran.foundation/content/api/v4"
AUTH_URL = "https://oauth2.quran.foundation/oauth2/token"

def get_token():
    r = requests.post(AUTH_URL, 
        auth=(QF_CLIENT_ID, QF_CLIENT_SECRET),  # Basic auth header
        data={
            "grant_type": "client_credentials",
            "scope": "content"
        }
    )
    r.raise_for_status()
    return r.json()["access_token"]

def fetch_all_tafsir_for_chapter(ch, token):
    """Fetch all pages of tafsir for a chapter, return dict of verse_key -> tafsir_text."""
    tafsir_map = {}
    page = 1
    while True:
        url = f"{API_BASE}/tafsirs/169/by_chapter/{ch}"
        params = {"per_page": 50, "page": page}
        headers = {"x-auth-token": token, "x-client-id": QF_CLIENT_ID}
        r = requests.get(url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
        
        verses = data.get("tafsirs", [])
        if not verses:
            break
        
        for entry in verses:
            vk = entry.get("verse_key")
            text = entry.get("text", "")
            if vk and text:
                tafsir_map[vk] = text
        
        # Pagination check
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.2)  # be polite
    
    return tafsir_map

def propagate_tafsir(verses):
    """
    Within a chapter's verses (sorted by verse number), propagate tafsir forward:
    if a verse has no tafsir, copy from the previous verse's tafsir.
    Tafsir is only set on the FIRST verse of each Ibn Kathir group.
    """
    last_tafsir = None
    for v in verses:
        if v.get("tafsir_text"):
            last_tafsir = v["tafsir_text"]
        elif last_tafsir:
            v["tafsir_text"] = last_tafsir
    return verses

# --- Main ---
CORPUS_PATH = "corpus/full_corpus.json"
OUTPUT_PATH = "corpus/full_corpus.json"  # overwrite in place

print("Loading corpus...")
with open(CORPUS_PATH) as f:
    corpus = json.load(f)

# Index verses by verse_key for fast lookup
verse_index = {v["verse_key"]: v for v in corpus}

print(f"Loaded {len(corpus)} verses. Starting tafsir re-fetch for 114 chapters...")

token = get_token()
token_refresh_counter = 0

for ch in range(1, 115):
    # Refresh token every 20 chapters just in case
    token_refresh_counter += 1
    if token_refresh_counter % 20 == 0:
        token = get_token()
    
    tafsir_map = fetch_all_tafsir_for_chapter(ch, token)
    
    # Clear existing tafsir for this chapter, then set fresh data
    chapter_verses = sorted(
        [v for v in corpus if v["surah_number"] == ch],
        key=lambda v: v["verse_number"]
    )
    
    for v in chapter_verses:
        v["tafsir_text"] = tafsir_map.get(v["verse_key"], "")
    
    # Propagate forward within chapter
    propagate_tafsir(chapter_verses)
    
    covered = sum(1 for v in chapter_verses if v.get("tafsir_text"))
    print(f"  Ch {ch:3d}: {len(tafsir_map):3d} tafsir entries fetched, "
          f"{covered}/{len(chapter_verses)} verses covered after propagation")
    
    time.sleep(0.3)

print(f"\nSaving fixed corpus to {OUTPUT_PATH}...")
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(corpus, f, ensure_ascii=False, indent=2)

print("Done. Now run: python build_chunks.py")