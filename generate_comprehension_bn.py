#!/usr/bin/env python3
"""
generate_comprehension_bn.py

Generates the Bangla comprehension layer for Fahm.
Improved version with all lessons from English generation applied:
  - BATCH_SIZE = 5 (prevents JSON truncation)
  - sanitize_text() on all input (prevents unterminated string errors)
  - 12K max_tokens per batch
  - 3 retry attempts per batch
  - Error threshold = 5
  - --range flag for parallel terminal runs
  - Already-generated check skips existing files

Sources:
  - Ibn Kathir Bengali   (tafsir_bn_ibn_kathir_propagated.json)
  - Abu Bakr Zakaria     (tafsir_bn_abu_bakr_propagated.json)
  - Taisirul Quran       (translation_bn_taisirul.json)

Output directory: comprehension_bn/

Usage:
    python3 generate_comprehension_bn.py --surah 112
    python3 generate_comprehension_bn.py --range 1-20
    python3 generate_comprehension_bn.py --range 21-50
    python3 generate_comprehension_bn.py --range 51-77
    python3 generate_comprehension_bn.py --batch all

Parallel terminals (recommended for surahs 1-77):
    Terminal 1: python3 generate_comprehension_bn.py --range 1-20
    Terminal 2: python3 generate_comprehension_bn.py --range 21-50
    Terminal 3: python3 generate_comprehension_bn.py --range 51-77
    Terminal 4: python3 generate_comprehension_bn.py --range 78-114

Env vars required:
    ANTHROPIC_API_KEY
"""

import os, json, time, argparse, re
from pathlib import Path
from collections import defaultdict
import anthropic

CORPUS_PATH = Path("corpus/full_corpus.json")
CHUNKS_PATH = Path("corpus/chunks.json")
META_PATH   = Path("corpus/meta")
OUTPUT_DIR  = Path("comprehension_bn")
OUTPUT_DIR.mkdir(exist_ok=True)

BATCH_SIZE = 5  # Small batches = fewer JSON failures

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# --- Load data ---
print("Loading corpus and chunks...")
with open(CORPUS_PATH) as f:
    corpus = json.load(f)

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

# --- Load Bangla sources ---
def load_json(path):
    if not Path(path).exists():
        print(f"  WARNING: {path} not found")
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
print()

# --- System prompt (Bangla) ---
SYSTEM_PROMPT = """আপনি Fahm-এর বাংলা কমপ্রিহেনশন লেয়ার তৈরি করছেন। Fahm একটি কুরআন পাঠ অ্যাপ যা এমন মুসলিমদের জন্য তৈরি যারা ইসলামে বিশ্বাস রাখেন কিন্তু কুরআনের সাথে গভীরভাবে পরিচিত হননি।

পাঠক: ২০-৩০ বছর বয়সী একজন বাংলাভাষী মুসলিম। বুদ্ধিমান কিন্তু কুরআনের বিষয়বস্তু, ঐতিহাসিক প্রেক্ষাপট এবং পণ্ডিতদের পরিভাষার সাথে অপরিচিত। তারা বুঝতে চান, মুগ্ধ হতে চান না।

ভাষা ও কণ্ঠস্বর: সমস্ত বিষয়বস্তু বাংলায় লিখুন। কণ্ঠস্বর হবে উষ্ণ, স্পষ্ট এবং কথ্য — যেন একজন জ্ঞানী বন্ধু সামনে বসে বুঝিয়ে দিচ্ছেন। আনুষ্ঠানিক বা একাডেমিক ভাষা এড়িয়ে চলুন। প্রতিটি বাক্য পরীক্ষা করুন: এটি কি আপনি একজন বন্ধুকে মুখে বলতেন? যদি মনে হয় মঞ্চের বক্তৃতা বা ডকুমেন্টারির ন্যারেশন, তাহলে আবার লিখুন।

সম্মানসূচক শব্দ:
- আল্লাহর নামের পরে সর্বদা ﷻ লিখুন — প্রতিটি উল্লেখে, কোনো ব্যতিক্রম নেই
- নবী মুহাম্মদ ﷺ বা রাসুলুল্লাহ ﷺ — প্রতিটি উল্লেখে
- অন্যান্য নবীদের (মূসা, ইব্রাহীম, ঈসা) প্রথম উল্লেখে (আলাইহিস সালাম) যোগ করুন

ইসলামিক পরিভাষা: প্রথম ব্যবহারে সংক্ষেপে ব্যাখ্যা করুন।

---

আপনাকে অবশ্যই এই কাঠামো অনুযায়ী বৈধ JSON-এ উত্তর দিতে হবে:
{
  "surah_number": <integer>,
  "surah_name": "<ইংরেজি নাম>",
  "surah_name_arabic": "<আরবি নাম>",
  "revelation_type": "<Makki বা Madani>",
  "introduction": "<৩ অনুচ্ছেদ — নিচের OVERVIEW নিয়ম দেখুন>",
  "sections": [
    {
      "section_number": <integer>,
      "title": "<সংক্ষিপ্ত অর্থবহ শিরোনাম, ৩-৭ শব্দ, বাংলায়>",
      "verse_range": "<যেমন 78:1-5>",
      "verse_keys": ["78:1", "78:2", "78:3", "78:4", "78:5"],
      "revelation_context": "<নিচের HISTORICAL CONTEXT নিয়ম দেখুন>",
      "bridge": "<নিচের BRIDGE নিয়ম দেখুন>"
    }
  ]
}

CRITICAL: verse_keys must be strings in "surah:verse" format like "78:1", NOT integers like 78001.

---

OVERVIEW (introduction ফিল্ড):
উদ্দেশ্য: পাঠককে সুরার সাথে পরিচয় করিয়ে দিন।

তিনটি অনুচ্ছেদ:
১. এই সুরা কী নিয়ে? প্রথম বাক্যে সুরার নাম এবং বিষয়বস্তু স্পষ্টভাবে উল্লেখ করুন। পাঠককে আগ্রহী করুন।
২. সুরায় কী ঘটে? মূল বিষয়বস্তু সুনির্দিষ্টভাবে বর্ণনা করুন।
৩. পাঠক আজকের জীবনে কী নিয়ে যাবেন? এই সুরার বিশেষ বৈশিষ্ট্য অনুযায়ী কিছু একটা — উপলব্ধি, প্রশ্ন, দৃষ্টিভঙ্গির পরিবর্তন।

Overview নিয়ম:
- সর্বদা সুরার নাম ব্যবহার করুন, কখনো "এই সুরা" নয়
- কোথায় বা কখন নাজিল হয়েছে তা উল্লেখ করবেন না — সেটি historical context-এর জন্য
- মোট ১৫০-২৫০ শব্দ

---

HISTORICAL CONTEXT (revelation_context ফিল্ড):
উদ্দেশ্য: প্রেক্ষাপট তৈরি করুন। এই আয়াতগুলো নাজিলের সময় আসলে কী ঘটছিল?

অন্তর্ভুক্ত করুন:
- তাফসির সূত্র থেকে নির্দিষ্ট ঘটনা, নাম, পরিস্থিতি
- রাসুলুল্লাহ ﷺ কী অনুভব করছিলেন
- সমাজের পরিস্থিতি
- এই নির্দিষ্ট আয়াতগুলো কী কারণে নাজিল হয়েছিল

Section 1-এর জন্য: সরাসরি ঐতিহাসিক পরিস্থিতি দিয়ে শুরু করুন।
Section 2 থেকে: আগের section-এর বিষয় থেকে স্বাভাবিকভাবে সংযোগ স্থাপন করে শুরু করুন, তারপর নির্দিষ্ট ঐতিহাসিক বিবরণ দিন।

নিয়ম:
- শুধুমাত্র তাফসির সূত্র থেকে তথ্য নিন। কিছু উদ্ভাবন করবেন না।
- ন্যূনতম ৩-৪ বাক্য
- "এই আয়াতগুলো নাজিল হয়েছিল..." দিয়ে শুরু করবেন না

---

BRIDGE (bridge ফিল্ড):
উদ্দেশ্য: পাঠক যা পড়লেন তা ব্যাখ্যা করুন।

বিষয়বস্তু:
- এই আয়াতগুলোতে আল্লাহ ﷻ কী বলছেন
- যুক্তি বা বর্ণনা কী
- পাঠক কী নিয়ে যাবেন

নিয়ম:
- ৩-৫ বাক্য
- আয়াতগুলো যা বলে তা সুনির্দিষ্টভাবে উল্লেখ করুন
- Historical context পুনরাবৃত্তি করবেন না
- প্রতিটি bridge আলাদা ভাবে শুরু করুন

---

তাফসির সূত্র ব্যবহার:
- ইবনে কাসির (বাংলা): ঐতিহাসিক ঘটনা, নির্দিষ্ট নাম, নুজুলের কারণের জন্য
- আবু বকর যাকারিয়া: ব্যবহারিক অর্থ ও সমসাময়িক প্রাসঙ্গিকতার জন্য
- সব সূত্র থেকে কিছু অন্তর্ভুক্ত করা জরুরি নয় — যেটি সত্যিকারের কিছু যোগ করে সেটি ব্যবহার করুন

---

গুরুত্বপূর্ণ নিয়ম:
- Section অবশ্যই তাফসির গ্রুপিং অনুসরণ করবে — একত্রিত বা বিভক্ত করবেন না
- verse_keys অবশ্যই "78:1" ফরম্যাটে string হবে, integer নয়
- শুধুমাত্র বৈধ JSON দিয়ে উত্তর দিন — কোনো ভূমিকা বা ব্যাখ্যা JSON-এর বাইরে নয়"""


def sanitize_text(text):
    """Remove characters that cause JSON generation failures."""
    if not text:
        return ""
    text = text.replace('\\', ' ')
    text = text.replace('\x00', '')
    text = text.replace('\r', ' ')
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
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


def build_surah_context_partial(surah_number, chunk_slice):
    """Build context for a subset of chunks (for batched generation)."""
    meta = chapter_meta.get(surah_number, {})

    lines = []
    lines.append(f"=== SURAH {surah_number} METADATA ===")
    if meta:
        lines.append(f"Name: {meta.get('name_simple', '')} / {meta.get('name_arabic', '')}")
        lines.append(f"Revelation type: {meta.get('revelation_place', '')}")
        lines.append(f"Verses: {meta.get('verses_count', '')}")
    lines.append("")
    lines.append("=== VERSE GROUPS WITH BANGLA TAFSIR SOURCES ===")
    lines.append("Use these exact groupings as your sections.")
    lines.append("")

    for i, chunk in enumerate(chunk_slice):
        lines.append(f"--- GROUP {i+1}: {chunk['verse_range']} ---")
        lines.append(f"Verse keys: {', '.join(chunk['verse_keys'])}")
        lines.append("")

        # English translation for reference
        translation = chunk.get('translation_abdel_haleem', '')
        if isinstance(translation, list):
            translation = ' '.join(translation)
        if translation:
            lines.append("English translation (reference only):")
            lines.append(sanitize_text(translation[:800]))
            lines.append("")

        tafsirs = get_tafsir_for_group(chunk['verse_keys'])

        if tafsirs["taisirul"]:
            lines.append("তাইসিরুল কুরআন (অনুবাদ — প্রসঙ্গ হিসেবে):")
            lines.append(sanitize_text(tafsirs["taisirul"][:500]))
            lines.append("")

        if tafsirs["ibn_kathir_bn"]:
            lines.append("ইবনে কাসির বাংলা (ঐতিহাসিক প্রেক্ষাপট, ঘটনা, নামের জন্য ব্যবহার করুন):")
            lines.append(sanitize_text(tafsirs["ibn_kathir_bn"][:2000]))
            lines.append("")

        if tafsirs["abu_bakr_bn"]:
            lines.append("আবু বকর যাকারিয়া (ব্যবহারিক অর্থ ও প্রাসঙ্গিকতার জন্য ব্যবহার করুন):")
            lines.append(sanitize_text(tafsirs["abu_bakr_bn"][:1500]))
            lines.append("")

    return "\n".join(lines)


def parse_raw_json(raw):
    """Strip markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def normalize_verse_keys(data):
    """Ensure verse_keys are strings in 'surah:verse' format, not integers."""
    for section in data.get("sections", []):
        fixed_keys = []
        for k in section.get("verse_keys", []):
            if isinstance(k, int):
                s = str(k)
                if len(s) <= 3:
                    fixed_keys.append(s)
                else:
                    verse = int(s[-3:])
                    surah = int(s[:-3])
                    fixed_keys.append(f"{surah}:{verse}")
            else:
                fixed_keys.append(str(k))
        section["verse_keys"] = fixed_keys
    return data


def generate_surah_comprehension_batched(surah_number):
    """Generate comprehension in batches for large surahs."""
    chunks    = chunks_by_surah.get(surah_number, [])
    meta      = chapter_meta.get(surah_number, {})
    surah_name = meta.get('name_simple', f'Surah {surah_number}')

    all_sections = []
    intro = None

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch         = chunks[batch_start:batch_start + BATCH_SIZE]
        batch_num     = batch_start // BATCH_SIZE + 1
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"             batch {batch_num}/{total_batches}...", end=" ", flush=True)

        context = build_surah_context_partial(surah_number, batch)
        is_first = batch_start == 0
        intro_instruction = "Include the 'introduction' field (3-paragraph overview in Bangla)." if is_first else "Set 'introduction' to empty string ''."

        user_message = f"""অনুগ্রহ করে সুরা {surah_number} ({surah_name})-এর বাংলা কমপ্রিহেনশন লেয়ার তৈরি করুন, section {batch_start+1} থেকে {batch_start+len(batch)} পর্যন্ত।

{context}

{intro_instruction}
Section numbers must start from {batch_start+1}.
verse_keys must be strings like "78:1", NOT integers like 78001.
শুধুমাত্র বৈধ JSON দিয়ে উত্তর দিন।"""

        for attempt in range(3):
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=12000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}]
            )
            try:
                data = parse_raw_json(response.content[0].text)
                data = normalize_verse_keys(data)
                break
            except json.JSONDecodeError:
                if attempt < 2:
                    print(f"JSON error, retrying (attempt {attempt+2})...", end=" ", flush=True)
                    time.sleep(2)
                else:
                    raise

        if is_first:
            intro = data.get("introduction", "")

        all_sections.extend(data.get("sections", []))
        print(f"got {len(data.get('sections', []))} sections")
        time.sleep(1)

    return {
        "surah_number":      surah_number,
        "surah_name":        meta.get('name_simple', f'Surah {surah_number}'),
        "surah_name_arabic": meta.get('name_arabic', ''),
        "revelation_type":   meta.get('revelation_place', 'Makki'),
        "introduction":      intro or "",
        "sections":          all_sections
    }


def generate_surah_comprehension(surah_number):
    """Generate comprehension for a single surah — always uses batched path."""
    return generate_surah_comprehension_batched(surah_number)


def save_surah_output(surah_number, data):
    name = data.get('surah_name', 'unknown').lower().replace(' ', '_').replace("'", '').replace('-', '_')
    filename = OUTPUT_DIR / f"{surah_number:03d}_{name}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filename


def already_generated(surah_number):
    return any(OUTPUT_DIR.glob(f"{surah_number:03d}_*.json"))


def run_batch(surah_numbers):
    total   = len(surah_numbers)
    success = 0
    errors  = 0

    for i, surah_number in enumerate(surah_numbers):
        if already_generated(surah_number):
            print(f"  [{i+1}/{total}] Surah {surah_number} — already generated, skipping")
            success += 1
            continue

        chunks = chunks_by_surah.get(surah_number, [])
        if not chunks:
            print(f"  [{i+1}/{total}] Surah {surah_number} — no chunks found, skipping")
            continue

        meta       = chapter_meta.get(surah_number, {})
        surah_name = meta.get('name_simple', f'Surah {surah_number}')
        print(f"  [{i+1}/{total}] Generating Surah {surah_number} ({surah_name}) — {len(chunks)} sections...")

        try:
            data     = generate_surah_comprehension(surah_number)
            filepath = save_surah_output(surah_number, data)
            section_count = len(data.get('sections', []))
            print(f"           ✓ Saved to {filepath.name} ({section_count} sections)")
            success += 1
        except json.JSONDecodeError as e:
            print(f"           ✗ JSON parse error: {e}")
            errors += 1
        except Exception as e:
            print(f"           ✗ Error: {e}")
            errors += 1
            if errors > 5:
                print("Too many errors — stopping.")
                break

        time.sleep(1)

    print(f"\nDone. Success: {success}, Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Fahm Bangla comprehension layer")
    parser.add_argument("--batch", choices=["juz_amma", "all"], help="Generate a batch")
    parser.add_argument("--surah", type=int, help="Generate a single surah by number")
    parser.add_argument("--range", type=str, help="Generate a range e.g. --range 1-20")
    args = parser.parse_args()

    if args.surah:
        print(f"Generating single surah: {args.surah}")
        meta = chapter_meta.get(args.surah, {})
        surah_name = meta.get('name_simple', f'Surah {args.surah}')
        print(f"Surah: {surah_name}")
        data     = generate_surah_comprehension(args.surah)
        filepath = save_surah_output(args.surah, data)
        print(f"Saved to {filepath}")
        print(f"Sections: {len(data.get('sections', []))}")

    elif args.range:
        start, end = map(int, args.range.split('-'))
        surah_list = list(range(start, end + 1))
        print(f"Generating surahs {start}-{end} ({len(surah_list)} surahs)...")
        run_batch(surah_list)

    elif args.batch == "juz_amma":
        print("Generating Bangla comprehension for Juz Amma (Surahs 78-114)...")
        run_batch(list(range(78, 115)))

    elif args.batch == "all":
        print("Generating Bangla comprehension for all 114 surahs...")
        run_batch(list(range(1, 115)))

    else:
        parser.print_help()
