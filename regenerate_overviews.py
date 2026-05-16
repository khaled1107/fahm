#!/usr/bin/env python3
"""
regenerate_overviews.py

Regenerates the introduction/overview text for all Juz Amma comprehension files.
Fixes repetitive AI-sounding openings and removes revelation timing info from overviews.
Updates files in-place in the comprehension/ directory.

Usage:
    python3 regenerate_overviews.py
"""

import os, json, time
from pathlib import Path
import anthropic

COMPREHENSION_DIR = Path("comprehension")
JUZ_AMMA = list(range(78, 115))

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are helping non-practicing Muslims understand the Quran for the first time. Your job is to write a 3-paragraph Overview for a surah that will appear at the top of a reading experience.

The target reader is a casually practicing Muslim in their 20s-30s. They believe in Islam but have never deeply engaged with the Quran. They need clarity before depth. They need to understand what a surah is about before they can appreciate it.

STRUCTURE — follow this exactly:

Paragraph 1 — What is this surah about?
Start with a clear, plain statement that orients the reader immediately. The very first sentence must answer "what is the topic of this surah?" in language anyone can understand. Always refer to the surah by name in the opening sentence — never "this surah." The structure can vary: "Surah An-Naba asks one big question..." or "In Surah Al-Fil, Allah recounts a story..." or "Surah Ad-Duhaa is a deeply personal moment..." Good examples:
- "Surah An-Naba is built around one question: is there really life after death?"
- "Surah Al-Fil tells the story of what happened when an army of elephants tried to destroy the Kaaba."
- "Surah Ad-Duhaa is a direct conversation between Allah and the Prophet during one of his lowest moments."
No atmospheric scene-setting. No poetic openings. No rhetorical questions as the first line. Orient first.

Paragraph 2 — What happens in the surah?
Walk through the main content briefly. What does Allah say? What argument is made? What story is told? Keep it conversational — like explaining to a friend. This paragraph can be more vivid since the reader now knows the topic.

Paragraph 3 — Why does this matter to me today?
Connect the surah's message to the reader's actual life. Honest about why this ancient text is still relevant. Not preachy, not lecturing. Personal and direct. This is where the overview earns its weight.

RULES:
- Do not repeat the same opening structure or phrasing within Juz Amma. Across different juz, occasional similarity is fine.
- Don't overuse any single phrase. If "one of the most striking" genuinely fits a surah, use it — but it should appear rarely, not as a default.
- Do NOT mention when or where the surah was revealed — that's shown elsewhere
- Use clear, plain language. Assume the reader is intelligent but encountering these ideas for the first time.
- Use short sentences. If a sentence exceeds 25 words, split it
- Avoid Islamic jargon without explanation. If you use "tawakkul," explain it: "tawakkul — trusting that God has a plan." If you use "shirk," explain it: "shirk — worshipping anything alongside God."
- Tone: knowledgeable friend explaining something important. Not a scholar lecturing. Not a poet performing.
- No bullet points, no headers. Flowing prose only.

Respond with ONLY the overview text — three paragraphs, plain prose, no labels or preamble."""

def regenerate_overview(surah_num, surah_name, surah_name_arabic, revelation_type, existing_sections, existing_intro):
    """Generate a fresh overview for a surah."""

    section_titles = [s.get("title", "") for s in existing_sections]
    section_bridges = [s.get("bridge", "")[:300] for s in existing_sections[:3]]
    verse_count = sum(len(s.get("verse_keys", [])) for s in existing_sections)

    user_message = f"""Write a 3-paragraph Overview for Surah {surah_num}: {surah_name} ({surah_name_arabic}).
{verse_count} verses, {len(existing_sections)} sections.

Section themes in this surah:
{chr(10).join(f"- {t}" for t in section_titles if t)}

Content from the sections (to help you understand what's in this surah):
{chr(10).join(section_bridges)}

Here is the existing overview (rewrite it completely following the new guidelines — don't preserve any of the phrasing):
{existing_intro[:500]}

Write 3 paragraphs following the structure exactly: (1) what is this surah about, (2) what happens in it, (3) why it matters today. Do not mention when or where it was revealed."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return response.content[0].text.strip()

print("Regenerating overviews for Juz Amma...")
print()

success = 0
errors = 0

for sn in JUZ_AMMA:
    files = list(COMPREHENSION_DIR.glob(f"{sn:03d}_*.json"))
    if not files:
        print(f"  {sn}: No file found, skipping")
        continue

    filepath = files[0]
    with open(filepath) as f:
        comp = json.load(f)

    surah_name = comp.get("surah_name", f"Surah {sn}")
    surah_name_arabic = comp.get("surah_name_arabic", "")
    revelation_type = comp.get("revelation_type", "")
    sections = comp.get("sections", [])

    print(f"  [{sn}] {surah_name}...", end=" ", flush=True)

    try:
        new_overview = regenerate_overview(sn, surah_name, surah_name_arabic, revelation_type, sections, comp.get("introduction", ""))
        comp["introduction"] = new_overview
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(comp, f, ensure_ascii=False, indent=2)
        print(f"✓ ({len(new_overview.split())} words)")
        success += 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        errors += 1
        if errors > 3:
            print("Too many errors — stopping.")
            break

    time.sleep(0.5)

print(f"\nDone. Updated: {success}, Errors: {errors}")
print("\nRun python3 build_beta.py to rebuild fahm_beta.html with new overviews.")
