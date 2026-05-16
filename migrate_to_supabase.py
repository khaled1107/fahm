#!/usr/bin/env python3
"""
migrate_to_supabase.py

One-time migration: loads all Fahm content into Supabase.

Reads from:
  - comprehension/         (English comprehension JSON files)
  - comprehension_bn/      (Bangla comprehension JSON files)
  - corpus/chunks.json     (verse content)
  - corpus/transliteration.json
  - corpus/translation_bn_taisirul.json
  - corpus/translation_bn_rawai.json

Writes to Supabase:
  - fahm_surahs
  - fahm_sections
  - fahm_verses

Usage:
    python3 migrate_to_supabase.py
    python3 migrate_to_supabase.py --surah 78        # single surah
    python3 migrate_to_supabase.py --only verses     # only verses table
    python3 migrate_to_supabase.py --only surahs     # only surahs + sections

Env vars required:
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, json, re, argparse, time, requests
from pathlib import Path

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

COMPREHENSION_DIR    = Path("comprehension")
COMPREHENSION_BN_DIR = Path("comprehension_bn")
CHUNKS_PATH          = Path("corpus/chunks.json")
TRANSLIT_PATH        = Path("corpus/transliteration.json")
BN_TAISIRUL_PATH     = Path("corpus/translation_bn_taisirul.json")
BN_RAWAI_PATH        = Path("corpus/translation_bn_rawai.json")

JUZ_AMMA = list(range(78, 115))

VERSE_COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,
                110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,
                182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,
                29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,
                50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,
                8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]

def load_json(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_verse_keys(keys):
    result = []
    for k in keys:
        if isinstance(k, int):
            s = str(k)
            if len(s) <= 3:
                result.append(s)
            else:
                verse = int(s[-3:])
                surah = int(s[:-3])
                result.append(f"{surah}:{verse}")
        else:
            result.append(str(k))
    return result

def parse_keyed_string(text, verse_keys):
    result = {vk: "" for vk in verse_keys}
    if not text:
        return result
    parts = re.split(r'\[(\d+:\d+)\]\s*', text)
    i = 1
    while i < len(parts) - 1:
        key = parts[i]
        content = parts[i + 1].strip()
        if key in result:
            result[key] = content
        i += 2
    return result

def upsert(table, rows):
    """Upsert rows into a Supabase table via REST API."""
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data = rows if isinstance(rows, list) else [rows]
    headers = dict(HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    r = requests.post(url, headers=headers, json=data)
    if r.status_code not in (200, 201):
        raise Exception(f"Upsert to {table} failed: {r.status_code} {r.text[:200]}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--surah", type=int, help="Migrate a single surah")
    parser.add_argument("--only", choices=["surahs", "verses"], help="Migrate only one table group")
    args = parser.parse_args()

    print("Connecting to Supabase...")
    # Quick connectivity check
    r = requests.get(f"{SUPABASE_URL}/rest/v1/fahm_surahs?limit=1", headers=HEADERS)
    if r.status_code != 200:
        print(f"Connection failed: {r.status_code} {r.text}")
        return
    print("Connected.\n")

    # --- Load source data ---
    print("Loading source files...")
    chunks_raw = load_json(CHUNKS_PATH)
    translit   = load_json(TRANSLIT_PATH)
    bn_tais    = load_json(BN_TAISIRUL_PATH)
    bn_rawai   = load_json(BN_RAWAI_PATH)

    # Index chunks by surah
    chunks_by_surah = {}
    for chunk in chunks_raw:
        sn = chunk["surah_number"]
        if sn not in chunks_by_surah:
            chunks_by_surah[sn] = []
        chunks_by_surah[sn].append(chunk)
    for sn in chunks_by_surah:
        chunks_by_surah[sn].sort(key=lambda c: int(c["verse_keys"][0].split(":")[1]))

    surah_numbers = [args.surah] if args.surah else list(range(1, 115))
    do_surahs = args.only in (None, "surahs")
    do_verses = args.only in (None, "verses")

    for surah_num in surah_numbers:
        en_files = list(COMPREHENSION_DIR.glob(f"{surah_num:03d}_*.json"))
        bn_files = list(COMPREHENSION_BN_DIR.glob(f"{surah_num:03d}_*.json"))

        if not en_files:
            print(f"  Surah {surah_num} — no English comprehension file, skipping")
            continue

        comp_en = json.loads(en_files[0].read_text(encoding="utf-8"))
        comp_bn = json.loads(bn_files[0].read_text(encoding="utf-8")) if bn_files else {}

        surah_name = comp_en.get("surah_name", f"Surah {surah_num}")
        print(f"  [{surah_num}] {surah_name}", end=" ", flush=True)

        # ── SURAHS + SECTIONS ─────────────────────────────────
        if do_surahs:
            sections = comp_en.get("sections", [])
            verse_count = sum(len(normalize_verse_keys(s.get("verse_keys", []))) for s in sections)

            surah_row = {
                "number":          surah_num,
                "name":            surah_name,
                "arabic":          comp_en.get("surah_name_arabic", ""),
                "type":            "Makki" if comp_en.get("revelation_type", "").lower() in ["makki", "makkah", "meccan"] else "Madani",
                "verses_count":    verse_count,
                "meaning":         "",
                "introduction_en": comp_en.get("introduction", ""),
                "introduction_bn": comp_bn.get("introduction", ""),
            }

            upsert("fahm_surahs", surah_row)

            bn_sections = {s.get("section_number", i+1): s for i, s in enumerate(comp_bn.get("sections", []))}

            section_rows = []
            for i, sec in enumerate(sections):
                sec_num = sec.get("section_number", i + 1)
                bn_sec  = bn_sections.get(sec_num, {})
                vkeys   = normalize_verse_keys(sec.get("verse_keys", []))

                section_rows.append({
                    "surah_number":   surah_num,
                    "section_number": sec_num,
                    "title_en":       sec.get("title", ""),
                    "title_bn":       bn_sec.get("title", ""),
                    "verse_range":    sec.get("verse_range", ""),
                    "verse_keys":     vkeys,
                    "context_en":     sec.get("revelation_context", ""),
                    "context_bn":     bn_sec.get("revelation_context", ""),
                    "bridge_en":      sec.get("bridge", ""),
                    "bridge_bn":      bn_sec.get("bridge", ""),
                })

            if section_rows:
                upsert("fahm_sections", section_rows)

            print(f"({len(section_rows)} sections)", end=" ", flush=True)

        # ── VERSES ────────────────────────────────────────────
        if do_verses:
            chunks = chunks_by_surah.get(surah_num, [])
            verse_rows = []

            for chunk in chunks:
                chunk_keys = chunk.get("verse_keys", [])
                arabic_map = parse_keyed_string(chunk.get("arabic_uthmani", ""), chunk_keys)
                abdel_map  = parse_keyed_string(chunk.get("translation_abdel_haleem", ""), chunk_keys)
                sahih_map  = parse_keyed_string(chunk.get("translation_sahih_international", ""), chunk_keys)

                for vk in chunk_keys:
                    parts = vk.split(":")
                    verse_rows.append({
                        "verse_key":           vk,
                        "surah_number":        surah_num,
                        "verse_number":        int(parts[1]),
                        "arabic":              arabic_map.get(vk, ""),
                        "transliteration":     translit.get(vk, ""),
                        "abdel_haleem":        abdel_map.get(vk, ""),
                        "sahih_international": sahih_map.get(vk, ""),
                        "bn_taisirul":         bn_tais.get(vk, ""),
                        "bn_rawai":            bn_rawai.get(vk, ""),
                    })

            # Deduplicate verse rows by verse_key before upserting
            seen_keys = set()
            deduped_rows = []
            for vr in verse_rows:
                if vr["verse_key"] not in seen_keys:
                    seen_keys.add(vr["verse_key"])
                    deduped_rows.append(vr)
            verse_rows = deduped_rows
            # Upsert in batches of 200
            for i in range(0, len(verse_rows), 200):
                upsert("fahm_verses", verse_rows[i:i+200])

            print(f"({len(verse_rows)} verses)", end=" ", flush=True)

        print("✓")
        time.sleep(0.2)

    print(f"\nDone. Migrated {len(surah_numbers)} surahs.")

if __name__ == "__main__":
    main()
