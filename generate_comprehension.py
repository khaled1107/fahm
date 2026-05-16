#!/usr/bin/env python3
"""
generate_comprehension.py

Generates the contextual comprehension layer for Fahm.
For each surah: introduction, thematic sections with bridges,
revelation context, and cross-section connections.

Usage:
    python3 generate_comprehension.py --batch juz_amma
    python3 generate_comprehension.py --batch all
    python3 generate_comprehension.py --surah 112
    python3 generate_comprehension.py --range 40-60
"""

import os, json, time, argparse, re
from pathlib import Path
from collections import defaultdict
import anthropic

# --- Config ---
CORPUS_PATH = Path("corpus/full_corpus.json")
CHUNKS_PATH = Path("corpus/chunks.json")
META_PATH   = Path("corpus/meta")
OUTPUT_DIR  = Path("comprehension")
OUTPUT_DIR.mkdir(exist_ok=True)

JUZ_AMMA = list(range(78, 115))
BATCH_SIZE = 5  # max sections per API call for large surahs

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

chunks_by_surah = {}
for chunk in all_chunks:
    sn = chunk["surah_number"]
    if sn not in chunks_by_surah:
        chunks_by_surah[sn] = []
    chunks_by_surah[sn].append(chunk)

verses_by_surah = {}
for verse in corpus:
    sn = verse["surah_number"]
    if sn not in verses_by_surah:
        verses_by_surah[sn] = []
    verses_by_surah[sn].append(verse)

# --- Prompt ---
SYSTEM_PROMPT = """You are generating the comprehension layer for Fahm, a Quran reading app for Muslims who believe in Islam but have never deeply engaged with the Quran. Your content will be the first time many of them genuinely understand what they're reading.

THE READER: A Muslim in their 20s-30s. Intelligent but unfamiliar with Quranic themes, historical context, and scholarly terminology. They want to understand, not be impressed.

THE VOICE: All content must sound like the same person — a warm, knowledgeable friend who explains clearly without showing off. Apply this test to every sentence: would you actually say this to a friend sitting across from you? If it sounds like a stage performance or a documentary, rewrite it.

Never write like this:
- "one of the most arresting images in the Quran"
- "cosmic collapse" / "cosmic destruction"
- "the universe itself stops to witness"
- "devastating and chilling" / "stark and sobering" / "visceral and immediate"
- "the surah refuses to let anyone remain neutral"

Write like this instead:
- "This is a powerful moment — in the middle of everything falling apart, Allah ﷻ pauses to ask about a baby girl who was buried alive"
- "The world as they know it comes apart"
- "The description is direct and hard to ignore"

HONORIFICS:
- Allah is always followed by ﷻ — every single mention without exception
- Prophet Muhammad or Muhammad (referring to the Prophet) is always followed by ﷺ
- Other prophets (Musa, Ibrahim, Isa) — add (peace be upon him) on first mention in each block only

ISLAMIC TERMINOLOGY: Always explain on first use: "tawakkul — an awareness of God that shapes how you live" or "the Quraysh, the powerful tribe that controlled Makkah"

---

You must respond in valid JSON matching exactly this structure:
{
  "surah_number": <integer>,
  "surah_name": "<name in English transliteration>",
  "surah_name_arabic": "<Arabic name>",
  "revelation_type": "<Makki or Madani>",
  "introduction": "<3 paragraphs — see OVERVIEW rules below>",
  "sections": [
    {
      "section_number": <integer>,
      "title": "<short evocative title, 3-7 words>",
      "verse_range": "<e.g. 78:1-5>",
      "verse_keys": [<list of verse key strings>],
      "revelation_context": "<see HISTORICAL CONTEXT rules below>",
      "bridge": "<see BRIDGE rules below>"
    }
  ]
}

Note: there is NO connection field. Connections between sections are woven into the opening of the historical context block for sections 2 onwards.

---

OVERVIEW (the "introduction" field):
Purpose: Orient the reader. What is this surah about and why should I care?

Three paragraphs:
1. What is this surah about? The first sentence must include the surah's name and clearly state what the surah is about.
2. What happens in the surah? Walk through the main content concretely.
3. Leave the reader with something to carry — a realization, challenge, tension, or question.

Overview rules:
- Always use the surah name, never "this surah"
- ABSOLUTELY DO NOT mention when or where it was revealed
- Paragraph 3 must be about the reader's life today
- 150-250 words total

---

HISTORICAL CONTEXT (the "revelation_context" field):
Purpose: Set the scene. What was actually happening when these verses were revealed?

Rules:
- Draw all information from the tafsir sources. Never invent details.
- Include specific names when the tafsir mentions them
- Minimum 3-4 sentences
- Do NOT start with "These verses were revealed in..."
- Tone: conversational, warm, rich in specific detail

For section 1: Start directly with the historical situation.
For sections 2+: Open with 1-2 sentences bridging from the previous section.

---

BRIDGE (the "bridge" field):
Purpose: Explain what the reader just read. Post-verse reflection.

Rules:
- 3-5 sentences
- Be specific — reference what the verses actually say
- Do NOT repeat the historical context
- Vary openings

---

CRITICAL RULES:
- Sections must follow the tafsir groupings exactly
- Respond with valid JSON only — no preamble, no explanation outside the JSON
- Ensure all strings are properly escaped — no unescaped quotes within string values"""


def sanitize_text(text):
    """Remove characters that cause JSON generation failures."""
    if not text:
        return ""
    # Remove backslashes that cause unterminated string errors
    text = text.replace('\\', ' ')
    # Remove null bytes
    text = text.replace('\x00', '')
    # Normalize carriage returns
    text = text.replace('\r', ' ')
    # Normalize smart quotes to regular quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # Remove other problematic unicode control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def load_tafsir_index(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

print("Loading tafsir sources...")
TAFSIR_IBN_KATHIR = load_tafsir_index(Path("corpus/tafsir_ibn_kathir_propagated.json"))
TAFSIR_MAARIF     = load_tafsir_index(Path("corpus/tafsir_maarif_propagated.json"))
TAFSIR_TAZKIRUL   = load_tafsir_index(Path("corpus/tafsir_tazkirul_propagated.json"))
print(f"  Ibn Kathir: {len(TAFSIR_IBN_KATHIR)} verses")
print(f"  Ma'arif al-Qur'an: {len(TAFSIR_MAARIF)} verses")
print(f"  Tazkirul Quran: {len(TAFSIR_TAZKIRUL)} verses")
print()


def get_tafsir_for_group(verse_keys: list) -> dict:
    def collect_tafsir(tafsir_index, keys):
        for vk in keys:
            text = tafsir_index.get(vk, "").strip()
            if text:
                return text
        return ""

    return {
        "ibn_kathir": collect_tafsir(TAFSIR_IBN_KATHIR, verse_keys),
        "maarif":     collect_tafsir(TAFSIR_MAARIF,     verse_keys),
        "tazkirul":   collect_tafsir(TAFSIR_TAZKIRUL,   verse_keys),
    }


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


def build_surah_context(surah_number: int) -> str:
    chunks = chunks_by_surah.get(surah_number, [])
    verses = verses_by_surah.get(surah_number, [])
    meta   = chapter_meta.get(surah_number, {})

    # Scale truncation limits based on surah size
    num_chunks = len(chunks)
    if num_chunks > 80:
        trans_limit, ik_limit, maarif_limit, taz_limit = 500, 800, 600, 400
    elif num_chunks > 40:
        trans_limit, ik_limit, maarif_limit, taz_limit = 800, 1200, 900, 600
    elif num_chunks > 20:
        trans_limit, ik_limit, maarif_limit, taz_limit = 1000, 1500, 1200, 800
    else:
        trans_limit, ik_limit, maarif_limit, taz_limit = 1500, 2000, 1500, 1000

    lines = []
    lines.append(f"=== SURAH {surah_number} METADATA ===")
    if meta:
        lines.append(f"Name: {meta.get('name_simple', '')} / {meta.get('name_arabic', '')}")
        lines.append(f"Revelation type: {meta.get('revelation_place', '')}")
        lines.append(f"Verses: {meta.get('verses_count', '')}")
        translated_name = meta.get('translated_name', {})
        if isinstance(translated_name, dict):
            lines.append(f"Meaning of name: {translated_name.get('name', '')}")
        elif isinstance(translated_name, str):
            lines.append(f"Meaning of name: {translated_name}")
    lines.append("")

    intro_text = None
    for verse in verses:
        if verse.get('verse_number') == 1 and verse.get('chapter_intro'):
            intro_text = verse.get('chapter_intro', '')
            break
    if intro_text:
        lines.append("=== CHAPTER INTRODUCTION (from corpus) ===")
        lines.append(sanitize_text(intro_text[:2000]))
        lines.append("")

    lines.append("=== VERSE GROUPS WITH TAFSIR SOURCES ===")
    lines.append("Use these exact groupings as your sections. For each group, three tafsir sources are provided.")
    lines.append("")

    for i, chunk in enumerate(chunks):
        lines.append(f"--- GROUP {i+1}: {chunk['verse_range']} ---")
        lines.append(f"Verse keys: {', '.join(chunk['verse_keys'])}")
        lines.append("")

        translation = chunk.get('translation_abdel_haleem', '')
        if isinstance(translation, list):
            translation = ' '.join(translation)
        if translation:
            lines.append("Translation (Abdel Haleem):")
            lines.append(sanitize_text(translation[:trans_limit]))
            lines.append("")

        tafsirs = get_tafsir_for_group(chunk['verse_keys'])

        if tafsirs["ibn_kathir"]:
            lines.append("Source 1 — Ibn Kathir (use for historical context, specific events, names):")
            lines.append(sanitize_text(tafsirs["ibn_kathir"][:ik_limit]))
            lines.append("")

        if tafsirs["maarif"]:
            lines.append("Source 2 — Ma'arif al-Qur'an (use for bridges, thematic connections, practical meaning):")
            lines.append(sanitize_text(tafsirs["maarif"][:maarif_limit]))
            lines.append("")

        if tafsirs["tazkirul"]:
            lines.append("Source 3 — Tazkirul Quran (use for overviews, contemporary relevance, lived experience):")
            lines.append(sanitize_text(tafsirs["tazkirul"][:taz_limit]))
            lines.append("")

    return "\n".join(lines)


def build_surah_context_partial(surah_number: int, chunk_slice: list) -> str:
    """Build context for a subset of chunks (for batched generation)."""
    meta = chapter_meta.get(surah_number, {})

    num_chunks = len(chunk_slice)
    if num_chunks > 20:
        trans_limit, ik_limit, maarif_limit, taz_limit = 800, 1200, 900, 600
    else:
        trans_limit, ik_limit, maarif_limit, taz_limit = 1500, 2000, 1500, 1000

    lines = []
    lines.append(f"=== SURAH {surah_number} METADATA ===")
    if meta:
        lines.append(f"Name: {meta.get('name_simple', '')} / {meta.get('name_arabic', '')}")
        lines.append(f"Revelation type: {meta.get('revelation_place', '')}")
    lines.append("")
    lines.append("=== VERSE GROUPS WITH TAFSIR SOURCES ===")
    lines.append("Use these exact groupings as your sections.")
    lines.append("")

    for i, chunk in enumerate(chunk_slice):
        lines.append(f"--- GROUP {i+1}: {chunk['verse_range']} ---")
        lines.append(f"Verse keys: {', '.join(chunk['verse_keys'])}")
        lines.append("")
        translation = chunk.get('translation_abdel_haleem', '')
        if isinstance(translation, list):
            translation = ' '.join(translation)
        if translation:
            lines.append("Translation (Abdel Haleem):")
            lines.append(sanitize_text(translation[:trans_limit]))
            lines.append("")
        tafsirs = get_tafsir_for_group(chunk['verse_keys'])
        if tafsirs["ibn_kathir"]:
            lines.append("Source 1 — Ibn Kathir:")
            lines.append(sanitize_text(tafsirs["ibn_kathir"][:ik_limit]))
            lines.append("")
        if tafsirs["maarif"]:
            lines.append("Source 2 — Ma'arif al-Qur'an:")
            lines.append(sanitize_text(tafsirs["maarif"][:maarif_limit]))
            lines.append("")
        if tafsirs["tazkirul"]:
            lines.append("Source 3 — Tazkirul Quran:")
            lines.append(sanitize_text(tafsirs["tazkirul"][:taz_limit]))
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


def generate_surah_comprehension_batched(surah_number: int) -> dict:
    """Generate comprehension in batches for large surahs."""
    chunks    = chunks_by_surah.get(surah_number, [])
    meta      = chapter_meta.get(surah_number, {})
    surah_name = meta.get('name_simple', f'Surah {surah_number}')

    all_sections = []
    intro = None

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch       = chunks[batch_start:batch_start + BATCH_SIZE]
        batch_num   = batch_start // BATCH_SIZE + 1
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"             batch {batch_num}/{total_batches}...", end=" ", flush=True)

        context = build_surah_context_partial(surah_number, batch)
        is_first = batch_start == 0
        intro_instruction = "Include the 'introduction' field (3-paragraph overview)." if is_first else "Set 'introduction' to empty string ''."

        user_message = f"""Generate comprehension for Surah {surah_number} ({surah_name}), sections {batch_start+1} to {batch_start+len(batch)}.

{context}

{intro_instruction}
Section numbers must start from {batch_start+1}.
Respond with valid JSON only matching the standard structure."""

        for attempt in range(3):
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=12000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}]
            )
            try:
                data = parse_raw_json(response.content[0].text)
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


def generate_surah_comprehension(surah_number: int) -> dict:
    """Generate comprehension layer for a single surah."""
    chunks     = chunks_by_surah.get(surah_number, [])
    meta       = chapter_meta.get(surah_number, {})
    surah_name = meta.get('name_simple', f'Surah {surah_number}')

    # Use batched generation for large surahs
    if len(chunks) > BATCH_SIZE:
        return generate_surah_comprehension_batched(surah_number)

    context = build_surah_context(surah_number)

    num_sections = len(chunks)
    if num_sections > 80:
        max_tok = 16000
    elif num_sections > 40:
        max_tok = 12000
    elif num_sections > 20:
        max_tok = 9000
    else:
        max_tok = 6000

    user_message = f"""Please generate the comprehension layer for Surah {surah_number} ({surah_name}).

{context}

Remember:
- Use the exact verse groupings provided above as your sections
- Draw revelation context only from the tafsir text provided
- Respond with valid JSON only"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=max_tok,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return parse_raw_json(response.content[0].text)


def save_surah_output(surah_number: int, data: dict):
    name = data.get('surah_name', 'unknown').lower().replace(' ', '_').replace("'", '').replace('-', '_')
    filename = OUTPUT_DIR / f"{surah_number:03d}_{name}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filename


def already_generated(surah_number: int) -> bool:
    return any(OUTPUT_DIR.glob(f"{surah_number:03d}_*.json"))


def run_batch(surah_numbers: list):
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


# --- CLI ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Fahm comprehension layer")
    parser.add_argument("--batch", choices=["juz_amma", "all"], help="Generate a batch")
    parser.add_argument("--surah", type=int, help="Generate a single surah by number")
    parser.add_argument("--range", type=str, help="Generate a range, e.g. --range 40-60")
    args = parser.parse_args()

    if args.surah:
        print(f"Generating single surah: {args.surah}")
        meta = chapter_meta.get(args.surah, {})
        surah_name = meta.get('name_simple', f'Surah {args.surah}')
        print(f"Surah: {surah_name}")
        data = generate_surah_comprehension(args.surah)
        filepath = save_surah_output(args.surah, data)
        print(f"Saved to {filepath}")
        print(f"Sections: {len(data.get('sections', []))}")

    elif args.range:
        start, end = map(int, args.range.split('-'))
        surah_list = list(range(start, end + 1))
        print(f"Generating surahs {start}-{end} ({len(surah_list)} surahs)...")
        run_batch(surah_list)

    elif args.batch == "juz_amma":
        print("Generating Juz Amma (Surahs 78-114)...")
        run_batch(JUZ_AMMA)

    elif args.batch == "all":
        print("Generating all 114 surahs...")
        run_batch(list(range(1, 115)))

    else:
        parser.print_help()
