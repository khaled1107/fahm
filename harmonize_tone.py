#!/usr/bin/env python3
"""
harmonize_tone.py

Regenerates overviews, bridges, and historical context blocks across all 37
Juz Amma surahs with a unified, consistent tone.

Target voice: warm, knowledgeable friend explaining the Quran over coffee.
Clear first, then interesting. Never academic, never preachy, never performing.

Usage:
    python3 harmonize_tone.py
"""

import os, json, time
from pathlib import Path
import anthropic

COMPREHENSION_DIR = Path("comprehension")
JUZ_AMMA = list(range(78, 115))

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

VOICE_GUIDE = """
TARGET VOICE: A warm, knowledgeable friend explaining the Quran over coffee.
- Clear enough that a first-time reader is never confused
- Vivid enough that the content feels alive, not like a Wikipedia summary
- Conversational, not academic. Human, not performing.
- Use concrete details where they serve understanding
- Short sentences. Split anything over 25 words.
- Never preachy, never lecturing, never dramatic for drama's sake
- Reduce grand declarations. Replace "systematically dismantle" with "take apart, one by one"
- Reduce dramatic phrasing like "devastating judgment" or "stark and sobering" — simpler is stronger
- Keep emotional weight. Don't flatten. Just sound like a person talking.
"""

OVERVIEW_SYSTEM = f"""You are helping non-practicing Muslims understand the Quran for the first time.
Write a 3-paragraph Overview for a surah.

{VOICE_GUIDE}

STRUCTURE:
Paragraph 1 — What is this surah about?
Clear, plain opening sentence that orients the reader immediately. Always use the surah's name, never "this surah." The name must appear in the first sentence. Examples:
- "Surah An-Naba is built around one question: is there really life after death?"
- "Surah Al-Fil tells the story of what happened when an army of elephants tried to destroy the Kaaba."
- "Surah Ad-Duhaa is a direct conversation between Allah and the Prophet during one of his lowest moments."
After the clear opening, allow yourself to be descriptive and engaging. Use concrete details where they serve understanding. The overview should feel like it was written by the same voice as the rest of the reading experience — warm, textured, human. Be clear first, then be interesting.

Paragraph 2 — What happens in the surah?
Walk through the main content. What does Allah say? What argument is made? What story is told? Conversational, like explaining to a friend.

Paragraph 3 — Why does this matter today?
Connect to the reader's actual life. Honest, direct, personal. Not preachy.

RULES:
- Never repeat the same opening structure across different surahs in this juz
- Don't overuse any phrase. "One of the most striking" can appear if it genuinely fits, but rarely
- Do NOT mention when or where the surah was revealed
- Avoid jargon without explanation: "tawakkul — trusting that God has a plan"
- No bullet points, no headers. Prose only.

Respond with ONLY the three paragraphs — no labels, no preamble."""

SECTION_SYSTEM = f"""You are rewriting content for a Quran reading app. You will receive existing bridge text and historical context text for a section, and rewrite both with a unified tone.

{VOICE_GUIDE}

BRIDGE TEXT ("Understanding these verses"):
This appears AFTER the reader has read the verses. It helps them understand what they just read.
- Explain what Allah is doing or saying in these verses
- What argument is being made? What story is told? What emotion is addressed?
- Sound like a person unpacking meaning, not a writer crafting prose
- Keep it 2-3 sentences

HISTORICAL CONTEXT:
This gives the reader the historical background before they read the verses.
- What was happening when these verses came? What question prompted them? What event preceded them?
- Make it feel like a story, not a textbook entry
- Instead of: "Revealed during the period when the idolators were openly questioning..."
- Say: "The people of Makkah were openly mocking the idea of resurrection. They'd debate it in their gatherings, dismissing it as absurd. These verses came as a direct response."
- Factual, grounded in tafsir — but delivered like a person talking
- Draw ONLY from what is in the existing content — don't invent events
- Keep it 1-2 sentences

Respond with valid JSON only:
{{"bridge": "rewritten bridge text", "context": "rewritten historical context"}}"""


def regenerate_overview(surah_num, surah_name, section_titles, section_bridges, existing_intro):
    user_message = f"""Write a 3-paragraph Overview for Surah {surah_num}: {surah_name}.

Section themes:
{chr(10).join(f"- {t}" for t in section_titles if t)}

Content from sections (to understand the surah's message):
{chr(10).join(section_bridges[:2])}

Existing overview to completely rewrite (don't preserve phrasing):
{existing_intro[:400]}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=OVERVIEW_SYSTEM,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text.strip()


def rewrite_section_content(surah_name, section_title, verse_range, existing_bridge, existing_context):
    user_message = f"""Rewrite the bridge and historical context for this section of Surah {surah_name}.

Section: "{section_title}" ({verse_range})

Existing bridge text:
{existing_bridge}

Existing historical context:
{existing_context}

Rewrite both with the unified conversational tone. Keep the same information. Change the delivery.
Respond with JSON only: {{"bridge": "...", "context": "..."}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=SECTION_SYSTEM,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


print("Harmonizing tone across all 37 Juz Amma surahs...")
print("This will take 5-8 minutes.\n")

total_sections = 0
success_surahs = 0
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
    sections = comp.get("sections", [])
    section_titles = [s.get("title", "") for s in sections]
    section_bridges = [s.get("bridge", "")[:300] for s in sections]

    print(f"  [{sn}] {surah_name} ({len(sections)} sections)")

    try:
        # 1. Regenerate overview
        new_overview = regenerate_overview(
            sn, surah_name, section_titles, section_bridges,
            comp.get("introduction", "")
        )
        comp["introduction"] = new_overview
        time.sleep(0.3)

        # 2. Rewrite each section's bridge and context
        for i, sec in enumerate(sections):
            try:
                result = rewrite_section_content(
                    surah_name,
                    sec.get("title", ""),
                    sec.get("verse_range", ""),
                    sec.get("bridge", ""),
                    sec.get("revelation_context", "")
                )
                comp["sections"][i]["bridge"] = result.get("bridge", sec.get("bridge", ""))
                comp["sections"][i]["revelation_context"] = result.get("context", sec.get("revelation_context", ""))
                total_sections += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"    Section {i+1} error: {e}")

        # Save updated file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(comp, f, ensure_ascii=False, indent=2)

        print(f"    ✓ Overview + {len(sections)} sections rewritten")
        success_surahs += 1

    except Exception as e:
        print(f"    ✗ ERROR: {e}")
        errors += 1
        if errors > 3:
            print("Too many errors — stopping.")
            break

    time.sleep(0.5)

print(f"\nDone.")
print(f"Surahs updated: {success_surahs}/37")
print(f"Sections rewritten: {total_sections}")
print(f"Errors: {errors}")
print("\nRun: python3 build_beta.py")
