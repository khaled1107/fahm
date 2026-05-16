#!/usr/bin/env python3
"""
fix_missing_sections_bn.py

Generates comprehension only for MISSING verse groups in Bangla,
then merges them into the existing comprehension_bn/ JSON file.
Mirrors fix_missing_sections.py but uses Bangla tafsir sources
and generates Bangla output.

Usage:
    python3 fix_missing_sections_bn.py --surah 4
    python3 fix_missing_sections_bn.py --surah 12
    python3 fix_missing_sections_bn.py --surah 40
"""

import os, json, time, argparse, re
from pathlib import Path
from collections import defaultdict
import anthropic

CHUNKS_PATH          = Path("corpus/chunks.json")
META_PATH            = Path("corpus/meta")
COMPREHENSION_BN_DIR = Path("comprehension_bn")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

with open(CHUNKS_PATH) as f:
    all_chunks = json.load(f)

chapter_meta = {}
meta_file = META_PATH / "chapters.json"
if meta_file.exists():
    with open(meta_file) as f:
        chapters = json.load(f)
        if isinstance(chapters, list):
            for ch in chapters:
                chapter_meta[ch["id"]] = ch
        elif isinstance(chapters, dict):
            chapter_meta = {int(k): v for k, v in chapters.items()}

chunks_by_surah = defaultdict(list)
for chunk in all_chunks:
    chunks_by_surah[chunk["surah_number"]].append(chunk)

def load_json(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

print("Loading Bangla tafsir sources...")
TAFSIR_IBN_KATHIR_BN = load_json("corpus/tafsir_bn_ibn_kathir_propagated.json")
TAFSIR_ABU_BAKR_BN   = load_json("corpus/tafsir_bn_abu_bakr_propagated.json")
TRANS_TAISIRUL       = load_json("corpus/translation_bn_taisirul.json")
print(f"  Ibn Kathir Bengali: {len(TAFSIR_IBN_KATHIR_BN)} verses")
print(f"  Abu Bakr Zakaria: {len(TAFSIR_ABU_BAKR_BN)} verses")
print(f"  Taisirul Quran: {len(TRANS_TAISIRUL)} verses")

SYSTEM_PROMPT = """আপনি Fahm-এর বাংলা কম্প্রিহেনশন লেয়ারের missing sections তৈরি করছেন।

বিদ্যমান content-এর মতো একই style-এ sections generate করুন:
- উষ্ণ, কথ্য ভাষা — যেন একজন জ্ঞানী বন্ধু বুঝিয়ে দিচ্ছেন
- আল্লাহ ﷻ প্রতিটি উল্লেখে, নবী মুহাম্মদ ﷺ প্রতিটি উল্লেখে
- revelation_context: ঐতিহাসিক প্রেক্ষাপট, নির্দিষ্ট নাম ও ঘটনা
- bridge: আয়াতগুলো কী বলছে তার প্রতিফলন, ৩-৫ বাক্য
- সমস্ত বিষয়বস্তু বাংলায় লিখুন (title, revelation_context, bridge)

শুধুমাত্র এই কাঠামো অনুযায়ী valid JSON দিয়ে উত্তর দিন:
{
  "sections": [
    {
      "section_number": <integer>,
      "title": "<৩-৭ শব্দের অর্থবহ শিরোনাম, বাংলায়>",
      "verse_range": "<যেমন 4:17-18>",
      "verse_keys": [<আয়াতের কী-এর তালিকা>],
      "revelation_context": "<ঐতিহাসিক প্রেক্ষাপট, কমপক্ষে ৩-৪ বাক্য>",
      "bridge": "<আয়াতগুলো বোঝা, ৩-৫ বাক্য>"
    }
  ]
}"""

def sanitize_text(text):
    if not text:
        return ""
    text = text.replace('\\', ' ')
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()

def get_tafsir_for_group(verse_keys):
    def collect(index, keys):
        for vk in keys:
            text = index.get(vk, "").strip()
            if text:
                return text
        return ""
    return {
        "ibn_kathir_bn": collect(TAFSIR_IBN_KATHIR_BN, verse_keys),
        "abu_bakr_bn":   collect(TAFSIR_ABU_BAKR_BN,   verse_keys),
        "taisirul":      collect(TRANS_TAISIRUL,         verse_keys),
    }

def build_context_for_chunks(surah_number, missing_chunks):
    meta = chapter_meta.get(surah_number, {})
    lines = []
    lines.append(f"=== SURAH {surah_number} — {meta.get('name_simple', '')} ===")
    lines.append(f"Revelation type: {meta.get('revelation_place', '')}")
    lines.append("")
    lines.append("শুধুমাত্র এই verse groups-এর জন্য sections generate করুন:")
    lines.append("")

    for i, chunk in enumerate(missing_chunks):
        lines.append(f"--- GROUP {i+1}: {chunk['verse_range']} ---")
        lines.append(f"Verse keys: {', '.join(chunk['verse_keys'])}")
        lines.append("")

        translation = chunk.get('translation_abdel_haleem', '')
        if isinstance(translation, list):
            translation = ' '.join(translation)
        if translation:
            lines.append("English translation (reference only):")
            lines.append(sanitize_text(translation[:1000]))
            lines.append("")

        tafsirs = get_tafsir_for_group(chunk['verse_keys'])

        if tafsirs["taisirul"]:
            lines.append("তাইসিরুল কুরআন (অনুবাদ — প্রসঙ্গ হিসেবে):")
            lines.append(sanitize_text(tafsirs["taisirul"][:500]))
            lines.append("")

        if tafsirs["ibn_kathir_bn"]:
            lines.append("ইবনে কাসির বাংলা (ঐতিহাসিক প্রেক্ষাপট, ঘটনা, নামের জন্য):")
            lines.append(sanitize_text(tafsirs["ibn_kathir_bn"][:2000]))
            lines.append("")

        if tafsirs["abu_bakr_bn"]:
            lines.append("আবু বকর যাকারিয়া (ব্যবহারিক অর্থ ও প্রাসঙ্গিকতার জন্য):")
            lines.append(sanitize_text(tafsirs["abu_bakr_bn"][:1500]))
            lines.append("")

    return "\n".join(lines)

def fix_surah(surah_number):
    files = list(COMPREHENSION_BN_DIR.glob(f"{surah_number:03d}_*.json"))
    if not files:
        print(f"No existing Bangla file for surah {surah_number}")
        return

    with open(files[0], encoding="utf-8") as f:
        existing = json.load(f)

    covered_keys = set()
    for sec in existing.get("sections", []):
        for k in sec.get("verse_keys", []):
            covered_keys.add(str(k))

    all_surah_chunks = chunks_by_surah.get(surah_number, [])
    missing_chunks = []
    for chunk in all_surah_chunks:
        chunk_keys = set(str(k) for k in chunk["verse_keys"])
        if not chunk_keys.intersection(covered_keys):
            missing_chunks.append(chunk)

    if not missing_chunks:
        print(f"Surah {surah_number} — no missing chunks found")
        return

    print(f"Surah {surah_number} — found {len(missing_chunks)} missing chunk(s):")
    for c in missing_chunks:
        print(f"  {c['verse_range']} ({len(c['verse_keys'])} verses)")

    context = build_context_for_chunks(surah_number, missing_chunks)
    meta = chapter_meta.get(surah_number, {})
    surah_name = meta.get('name_simple', f'Surah {surah_number}')

    user_message = f"""অনুগ্রহ করে Surah {surah_number} ({surah_name})-এর missing Bangla comprehension sections তৈরি করুন।

{context}

বিদ্যমান sections-এর sequence-এ মানানসই section numbers দিন।
শুধুমাত্র valid JSON দিয়ে উত্তর দিন।"""

    for attempt in range(3):
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            new_data = json.loads(raw.strip())
            break
        except json.JSONDecodeError as e:
            if attempt < 2:
                print(f"  JSON error, retrying... ({e})")
                time.sleep(2)
            else:
                print(f"  Failed after 3 attempts: {e}")
                return

    new_sections = new_data.get("sections", [])
    print(f"  Generated {len(new_sections)} new section(s)")

    all_sections = existing.get("sections", []) + new_sections

    def section_sort_key(sec):
        keys = sec.get("verse_keys", [])
        if not keys:
            return (0, 0)
        k = str(keys[0])
        if ":" in k:
            parts = k.split(":")
            return (int(parts[0]), int(parts[1]))
        return (0, 0)

    all_sections.sort(key=section_sort_key)

    for i, sec in enumerate(all_sections):
        sec["section_number"] = i + 1

    existing["sections"] = all_sections

    with open(files[0], "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  Saved — {len(all_sections)} total sections")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--surah", type=int, required=True)
    args = parser.parse_args()
    fix_surah(args.surah)
