#!/usr/bin/env python3
"""
regenerate_overviews_only.py

Regenerates ONLY the introduction field for all Juz Amma comprehension files.
Leaves all section content (revelation_context, bridge, verse_keys etc.) untouched.

Usage:
    python3 regenerate_overviews_only.py
"""

import os, json, time
from pathlib import Path
import anthropic

COMPREHENSION_DIR = Path("comprehension")
JUZ_AMMA = list(range(78, 115))

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Import the system prompt from generate_comprehension.py
import importlib.util, sys
spec = importlib.util.spec_from_file_location("gen", "generate_comprehension.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

SYSTEM_PROMPT = gen.SYSTEM_PROMPT

def regenerate_overview(surah_num, surah_name, sections, existing_intro):
    section_titles = [s.get("title", "") for s in sections]
    section_bridges = [s.get("bridge", "")[:300] for s in sections[:2]]

    user_message = f"""Write ONLY the introduction (3 paragraphs) for Surah {surah_num}: {surah_name}.

Section themes:
{chr(10).join(f"- {t}" for t in section_titles if t)}

Content from sections:
{chr(10).join(section_bridges)}

Existing introduction (rewrite completely — do not preserve phrasing):
{existing_intro[:400]}

Return a JSON object with ONLY the introduction field:
{{"introduction": "paragraph 1\\n\\nparagraph 2\\n\\nparagraph 3"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Try to parse as JSON with just introduction field
    try:
        data = json.loads(raw)
        return data.get("introduction", "")
    except json.JSONDecodeError:
        # Model may have returned full surah JSON — extract introduction
        data = json.loads(raw)
        return data.get("introduction", "")


print("Regenerating overview (introduction) for all 37 Juz Amma surahs...")
print("Section content will NOT be changed.\n")

success = 0
errors = 0

for sn in JUZ_AMMA:
    files = list(COMPREHENSION_DIR.glob(f"{sn:03d}_*.json"))
    if not files:
        print(f"  [{sn}] No file found, skipping")
        continue

    filepath = files[0]
    with open(filepath, encoding="utf-8") as f:
        comp = json.load(f)

    surah_name = comp.get("surah_name", f"Surah {sn}")
    sections = comp.get("sections", [])
    existing_intro = comp.get("introduction", "")

    print(f"  [{sn}] {surah_name}...", end=" ", flush=True)

    try:
        new_intro = regenerate_overview(sn, surah_name, sections, existing_intro)
        if new_intro:
            comp["introduction"] = new_intro
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(comp, f, ensure_ascii=False, indent=2)
            print(f"✓")
            success += 1
        else:
            print(f"✗ Empty response")
            errors += 1
    except Exception as e:
        print(f"✗ {e}")
        errors += 1

    time.sleep(0.5)

print(f"\nDone. Updated: {success}, Errors: {errors}")
print("Run: python3 build_beta.py")