#!/usr/bin/env python3
"""
build_beta.py

Reads all comprehension JSON files from comprehension/ and merges them
with verse data from corpus/chunks.json to produce a single self-contained
fahm_beta.html file ready for beta testing.

Usage:
    python3 build_beta.py
Output:
    fahm_beta.html
"""

import json
import re
from pathlib import Path

COMPREHENSION_DIR    = Path("comprehension")
COMPREHENSION_BN_DIR = Path("comprehension_bn")
CHUNKS_PATH          = Path("corpus/chunks.json")
TRANSLIT_PATH        = Path("corpus/transliteration.json")
BN_TAISIRUL_PATH     = Path("corpus/translation_bn_taisirul.json")
BN_RAWAI_PATH        = Path("corpus/translation_bn_rawai.json")
TEMPLATE_PATH        = Path("fahm_reader_v2.html")
OUTPUT_PATH          = Path("fahm_beta.html")

JUZ_AMMA = list(range(78, 115))

print("Loading chunks...")
with open(CHUNKS_PATH) as f:
    all_chunks = json.load(f)

# Load transliteration if available
translit_map = {}
if TRANSLIT_PATH.exists():
    print("Loading transliteration...")
    with open(TRANSLIT_PATH) as f:
        translit_map = json.load(f)
else:
    print("No transliteration file found — skipping (run extract_transliteration.py first)")

# Load Bangla translations
bn_taisirul_map = {}
if BN_TAISIRUL_PATH.exists():
    print("Loading Bangla translations...")
    with open(BN_TAISIRUL_PATH, encoding="utf-8") as f:
        bn_taisirul_map = json.load(f)
    bn_rawai_map = {}
    if BN_RAWAI_PATH.exists():
        with open(BN_RAWAI_PATH, encoding="utf-8") as f:
            bn_rawai_map = json.load(f)
else:
    print("No Bangla translation files found — skipping")
    bn_rawai_map = {}

# Index chunks by surah number
chunks_by_surah = {}
for chunk in all_chunks:
    sn = chunk["surah_number"]
    if sn not in chunks_by_surah:
        chunks_by_surah[sn] = []
    chunks_by_surah[sn].append(chunk)

# Sort chunks within each surah by first verse number
for sn in chunks_by_surah:
    chunks_by_surah[sn].sort(key=lambda c: int(c["verse_keys"][0].split(":")[1]))

def parse_keyed_string(text, verse_keys):
    """Parse '[78:1] text\n[78:2] text\n...' into a list indexed by verse_keys."""
    result = {vk: "" for vk in verse_keys}
    if not text:
        return result
    # Split on [key] markers
    import re
    parts = re.split(r'\[(\d+:\d+)\]\s*', text)
    # parts = ['', '78:1', 'text...', '78:2', 'text...', ...]
    i = 1
    while i < len(parts) - 1:
        key = parts[i]
        content = parts[i + 1].strip()
        if key in result:
            result[key] = content
        i += 2
    return result

def get_verse_data(surah_num, verse_keys):
    """Get Arabic, Abdel Haleem, and Sahih International for a list of verse keys."""
    chunks = chunks_by_surah.get(surah_num, [])
    verse_map = {}
    for chunk in chunks:
        arabic = chunk.get("arabic_uthmani", "")
        abdel = chunk.get("translation_abdel_haleem", "")
        sahih = chunk.get("translation_sahih_international", "")
        chunk_keys = chunk.get("verse_keys", [])

        arabic_map = parse_keyed_string(arabic, chunk_keys)
        abdel_map = parse_keyed_string(abdel, chunk_keys)
        sahih_map = parse_keyed_string(sahih, chunk_keys)

        for vk in chunk_keys:
            verse_map[vk] = {
                "arabic": arabic_map.get(vk, ""),
                "abdel": abdel_map.get(vk, ""),
                "sahih": sahih_map.get(vk, ""),
            }

    result = {"arabic": [], "abdel": [], "sahih": [], "translit": [], "bn_taisirul": [], "bn_rawai": []}
    for vk in verse_keys:
        vdata = verse_map.get(vk, {})
        result["arabic"].append(vdata.get("arabic", ""))
        result["abdel"].append(vdata.get("abdel", ""))
        result["sahih"].append(vdata.get("sahih", ""))
        result["translit"].append(translit_map.get(vk, ""))
        result["bn_taisirul"].append(bn_taisirul_map.get(vk, ""))
        result["bn_rawai"].append(bn_rawai_map.get(vk, ""))
    return result

def normalize_verse_keys(keys):
    """Normalize verse keys to 'surah:verse' string format.
    Handles integers like 114001 → '114:1' and strings like '114:1'."""
    result = []
    for k in keys:
        if isinstance(k, int):
            # e.g. 114001 → surah=114, verse=1
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

def load_surah(surah_num):
    """Load and build a surah object from comprehension JSON + corpus data."""
    # English comprehension
    files = list(COMPREHENSION_DIR.glob(f"{surah_num:03d}_*.json"))
    if not files:
        print(f"  WARNING: No comprehension file for surah {surah_num}")
        return None

    with open(files[0]) as f:
        comp = json.load(f)

    # Bangla comprehension
    bn_files = list(COMPREHENSION_BN_DIR.glob(f"{surah_num:03d}_*.json"))
    comp_bn = {}
    if bn_files:
        with open(bn_files[0], encoding="utf-8") as f:
            comp_bn = json.load(f)
    else:
        print(f"  WARNING: No Bangla comprehension file for surah {surah_num}")

    surah_obj = {
        "number": surah_num,
        "name": comp.get("surah_name", f"Surah {surah_num}"),
        "arabic": comp.get("surah_name_arabic", ""),
        "meaning": "",
        "verses": sum(len(s.get("verse_keys", [])) for s in comp.get("sections", [])),
        "type": "Makki" if comp.get("revelation_type", "").lower() in ["makki", "makkah", "meccan"] else "Madani",
        "introduction": comp.get("introduction", ""),
        "introduction_bn": comp_bn.get("introduction", ""),
        "sections": [],
    }

    # Build a lookup for Bangla sections by section_number
    bn_sections = {s.get("section_number", i+1): s for i, s in enumerate(comp_bn.get("sections", []))}

    for i, sec in enumerate(comp.get("sections", [])):
        verse_keys = normalize_verse_keys(sec.get("verse_keys", []))
        vdata = get_verse_data(surah_num, verse_keys)

        sec_num = sec.get("section_number", i + 1)
        bn_sec = bn_sections.get(sec_num, {})

        section_obj = {
            "num": sec_num,
            "title": sec.get("title", ""),
            "title_bn": bn_sec.get("title", ""),
            "range": sec.get("verse_range", ""),
            "keys": verse_keys,
            "bridge": sec.get("bridge", ""),
            "bridge_bn": bn_sec.get("bridge", ""),
            "context": sec.get("revelation_context", ""),
            "context_bn": bn_sec.get("revelation_context", ""),
            "arabic": vdata["arabic"],
            "translation": vdata["abdel"],
            "sahih": vdata["sahih"],
            "translit": vdata["translit"],
            "bn_taisirul": vdata["bn_taisirul"],
            "bn_rawai": vdata["bn_rawai"],
        }
        surah_obj["sections"].append(section_obj)

    return surah_obj

print("Loading comprehension files...")
surahs = []
for sn in JUZ_AMMA:
    surah = load_surah(sn)
    if surah:
        surahs.append(surah)
        section_count = len(surah["sections"])
        print(f"  Surah {sn} ({surah['name']}) — {section_count} sections")

print(f"\nLoaded {len(surahs)} surahs (content now served from Supabase — build just validates)")

# Read template directly — no SURAHS injection needed
# Content (sections, verses, comprehension) is fetched from Supabase at runtime
print("\nReading template...")
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    new_html = f.read()

# Inject Supabase anon key — prefer env var (Netlify build) over
# fahm_config.json (local dev convenience, gitignored)
import os
anon_key = os.environ.get("SUPABASE_ANON_KEY")
if anon_key:
    new_html = new_html.replace("{{SUPABASE_ANON_KEY}}", anon_key)
    print("  Injected Supabase anon key from SUPABASE_ANON_KEY env var")
else:
    config_path = Path("fahm_config.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        if config.get("supabase_anon_key"):
            new_html = new_html.replace("{{SUPABASE_ANON_KEY}}", config["supabase_anon_key"])
            print("  Injected Supabase anon key from fahm_config.json")
        else:
            print("  WARNING: supabase_anon_key missing from fahm_config.json")
    else:
        print("  WARNING: no SUPABASE_ANON_KEY env var and no fahm_config.json found")
        print("  Set SUPABASE_ANON_KEY env var, or create fahm_config.json with: {\"supabase_anon_key\": \"your_key_here\"}")

# Write output
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(new_html)

print(f"Written to {OUTPUT_PATH}")
print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.0f} KB")
print("\nDone. Open fahm_beta.html in your browser to test.")
