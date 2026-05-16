#!/usr/bin/env python3
"""
fix_missing_sections.py

Generates comprehension only for missing verse groups in a surah,
then merges them into the existing JSON file.

Usage:
    python3 fix_missing_sections.py --surah 9
    python3 fix_missing_sections.py --surah 12
"""

import os, json, time, argparse, re
from pathlib import Path
from collections import defaultdict
import anthropic

CHUNKS_PATH      = Path("corpus/chunks.json")
META_PATH        = Path("corpus/meta")
COMPREHENSION_DIR = Path("comprehension")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Load data
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

def load_tafsir(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

print("Loading tafsir sources...")
TAFSIR_IBN_KATHIR = load_tafsir("corpus/tafsir_ibn_kathir_propagated.json")
TAFSIR_MAARIF     = load_tafsir("corpus/tafsir_maarif_propagated.json")
TAFSIR_TAZKIRUL   = load_tafsir("corpus/tafsir_tazkirul_propagated.json")

SYSTEM_PROMPT = """You are generating missing sections for Fahm, a Quran comprehension app.
Generate comprehension sections in the same style as the existing content:
- Warm, conversational tone — like a knowledgeable friend explaining
- Allah ﷻ every mention, Prophet ﷺ every mention
- revelation_context: historical background, specific names and events
- bridge: reflection on what the verses say, 3-5 sentences
Respond with valid JSON only matching this structure:
{
  "sections": [
    {
      "section_number": <integer>,
      "title": "<3-7 word evocative title>",
      "verse_range": "<e.g. 9:5-7>",
      "verse_keys": [<list of verse key strings>],
      "revelation_context": "<historical context, min 3-4 sentences>",
      "bridge": "<reflection on the verses, 3-5 sentences>"
    }
  ]
}"""

def sanitize_text(text):
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
        "ibn_kathir": collect(TAFSIR_IBN_KATHIR, verse_keys),
        "maarif":     collect(TAFSIR_MAARIF, verse_keys),
        "tazkirul":   collect(TAFSIR_TAZKIRUL, verse_keys),
    }

def build_context_for_chunks(surah_number, missing_chunks):
    meta = chapter_meta.get(surah_number, {})
    lines = []
    lines.append(f"=== SURAH {surah_number} — {meta.get('name_simple', '')} ===")
    lines.append(f"Revelation type: {meta.get('revelation_place', '')}")
    lines.append("")
    lines.append("Generate sections ONLY for these verse groups:")
    lines.append("")

    for i, chunk in enumerate(missing_chunks):
        lines.append(f"--- GROUP {i+1}: {chunk['verse_range']} ---")
        lines.append(f"Verse keys: {', '.join(chunk['verse_keys'])}")
        lines.append("")

        translation = chunk.get('translation_abdel_haleem', '')
        if isinstance(translation, list):
            translation = ' '.join(translation)
        if translation:
            lines.append("Translation (Abdel Haleem):")
            lines.append(sanitize_text(translation[:1500]))
            lines.append("")

        tafsirs = get_tafsir_for_group(chunk['verse_keys'])
        if tafsirs["ibn_kathir"]:
            lines.append("Ibn Kathir:")
            lines.append(sanitize_text(tafsirs["ibn_kathir"][:2000]))
            lines.append("")
        if tafsirs["maarif"]:
            lines.append("Ma'arif al-Qur'an:")
            lines.append(sanitize_text(tafsirs["maarif"][:1500]))
            lines.append("")
        if tafsirs["tazkirul"]:
            lines.append("Tazkirul Quran:")
            lines.append(sanitize_text(tafsirs["tazkirul"][:1000]))
            lines.append("")

    return "\n".join(lines)

def fix_surah(surah_number):
    # Load existing file
    files = list(COMPREHENSION_DIR.glob(f"{surah_number:03d}_*.json"))
    if not files:
        print(f"No existing file for surah {surah_number}")
        return

    with open(files[0], encoding="utf-8") as f:
        existing = json.load(f)

    # Find which verse keys are already covered
    covered_keys = set()
    for sec in existing.get("sections", []):
        for k in sec.get("verse_keys", []):
            covered_keys.add(str(k))

    # Find missing chunks
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

    # Generate missing sections
    context = build_context_for_chunks(surah_number, missing_chunks)
    meta = chapter_meta.get(surah_number, {})
    surah_name = meta.get('name_simple', f'Surah {surah_number}')

    user_message = f"""Generate the missing comprehension sections for Surah {surah_number} ({surah_name}).

{context}

Assign appropriate section numbers that fit into the existing sequence.
Respond with valid JSON only."""

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

    # Merge new sections into existing
    all_sections = existing.get("sections", []) + new_sections

    # Sort by first verse key
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

    # Renumber
    for i, sec in enumerate(all_sections):
        sec["section_number"] = i + 1

    existing["sections"] = all_sections

    # Save
    with open(files[0], "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  Saved — {len(all_sections)} total sections")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--surah", type=int, required=True, help="Surah number to fix")
    args = parser.parse_args()
    fix_surah(args.surah)
