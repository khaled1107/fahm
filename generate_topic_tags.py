#!/usr/bin/env python3
"""
generate_topic_tags.py
Generates topic tags for each chunk using GPT-4o-mini.
Reads corpus/chunks.json, writes tags back in place.
Supports resuming — skips chunks that already have tags.
"""

import os, json, time
from pathlib import Path
from openai import OpenAI

CHUNKS_PATH = Path("corpus/chunks.json")
MODEL = "gpt-4o-mini"
BATCH_SIZE = 20  # Save progress every N chunks

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """You are an expert in Islamic studies and Quranic sciences.
Your task is to generate topic tags for a passage from the Quran with its tafsir (commentary).
Output ONLY a comma-separated list of lowercase keywords and short phrases — nothing else.
No preamble, no explanation, no punctuation other than commas.

Focus on:
- Core topics and themes (e.g. prayer, patience, forgiveness, hellfire, paradise)
- Islamic terminology with common synonyms (e.g. riba, interest, usury)
- People and groups mentioned (e.g. bani israel, prophets, believers, hypocrites)
- Concepts a non-practicing Muslim might search for in plain English
- Emotions and life situations the passage speaks to (e.g. grief, anxiety, gratitude)

Example output:
prayer, salah, worship, remembrance of allah, dhikr, night prayer, tahajjud, supplication, dua"""

def generate_tags(chunk: dict) -> str:
    """Call GPT-4o-mini to generate tags for a single chunk."""
    # Use a trimmed version of embed_text to save tokens
    embed_text = chunk.get("embed_text", "")
    # Cap at ~2000 chars — enough context for tagging
    trimmed = embed_text[:2000] + ("..." if len(embed_text) > 2000 else "")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": trimmed}
        ],
        max_tokens=150,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# --- Main ---
print("Loading chunks...")
with open(CHUNKS_PATH) as f:
    chunks = json.load(f)

total = len(chunks)
already_tagged = sum(1 for c in chunks if c.get("topic_tags") and c["topic_tags"] != [])
print(f"Total chunks: {total}")
print(f"Already tagged: {already_tagged}")
print(f"To process: {total - already_tagged}")
print()

processed = 0
errors = 0

for i, chunk in enumerate(chunks):
    # Skip if already tagged
    if chunk.get("topic_tags") and chunk["topic_tags"] != []:
        continue

    try:
        tags_str = generate_tags(chunk)
        # Store as both a raw string and a list
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        chunk["topic_tags"] = tag_list
        chunk["topic_tags_raw"] = tags_str
        processed += 1

        if processed % 10 == 0:
            print(f"  [{processed}/{total - already_tagged}] chunk {chunk['chunk_id']} — {len(tag_list)} tags")

        # Save progress every BATCH_SIZE chunks
        if processed % BATCH_SIZE == 0:
            with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            print(f"  >>> Progress saved ({processed} chunks tagged)")

        # Rate limiting — gpt-4o-mini allows ~500 RPM, be conservative
        time.sleep(0.15)

    except Exception as e:
        errors += 1
        print(f"  ERROR on chunk {chunk['chunk_id']}: {e}")
        if errors > 10:
            print("Too many errors — saving progress and exiting.")
            break
        time.sleep(2)

# Final save
print(f"\nSaving final output...")
with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print(f"Done. Tagged {processed} new chunks. Errors: {errors}")

# Spot check — print tags for 5 random chunks
import random
print("\n--- Spot check (5 random chunks) ---")
sample = random.sample([c for c in chunks if c.get("topic_tags")], min(5, total))
for c in sample:
    print(f"\n{c['chunk_id']} ({c['verse_range']}):")
    print(f"  {c['topic_tags_raw']}")
