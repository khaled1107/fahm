"""
Fahm Chunking Pipeline
======================
Takes the extracted corpus and produces embedding-ready chunks.

Steps:
1. Group verses by shared tafsir (expert-curated groupings)
2. Clean tafsir text (strip HTML, normalize)
3. Analyze token sizes
4. (Future) Generate topic tags via LLM
5. Output chunks.json ready for embedding

Usage:
    python3 build_chunks.py
"""

import json
import re
import logging
from pathlib import Path
from collections import OrderedDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fahm-chunker")

CORPUS_PATH = Path("./corpus/full_corpus.json")
OUTPUT_PATH = Path("./corpus/chunks.json")
ANALYSIS_PATH = Path("./corpus/chunk_analysis.json")


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def strip_html(text: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#x27;', "'")
    text = text.replace('&nbsp;', ' ')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_tafsir(text: str) -> str:
    """Clean tafsir text: strip HTML, light cleanup of isnad noise."""
    if not text:
        return ""
    cleaned = strip_html(text)
    # Remove very long narrator chains (optional, conservative approach)
    # We keep them for now since they can contain context
    return cleaned


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~0.75 tokens per word for English."""
    if not text:
        return 0
    words = len(text.split())
    return int(words * 1.3)  # slightly conservative estimate


# ---------------------------------------------------------------------------
# Grouping logic
# ---------------------------------------------------------------------------

def group_verses_by_tafsir(verses: list) -> list:
    """
    Group verses that share the same tafsir text.
    Within each surah, consecutive verses with identical tafsir
    form a single chunk.
    """
    groups = []
    current_group = None

    for v in verses:
        surah = v["surah_number"]
        tafsir = v.get("tafsir_text", "")

        # Start a new group if:
        # - First verse
        # - Different surah
        # - Different tafsir (and current verse has its own tafsir)
        # - Current verse has tafsir but it differs from the group's tafsir
        start_new = False

        if current_group is None:
            start_new = True
        elif surah != current_group["surah_number"]:
            start_new = True
        elif tafsir and tafsir != current_group["tafsir_raw"]:
            # This verse has its own tafsir, different from the group
            start_new = True

        if start_new:
            if current_group is not None:
                groups.append(current_group)
            current_group = {
                "surah_number": surah,
                "surah_name": v["surah_name"],
                "surah_name_arabic": v["surah_name_arabic"],
                "revelation_type": v["revelation_type"],
                "verses": [v],
                "verse_keys": [v["verse_key"]],
                "first_verse": v["verse_number"],
                "last_verse": v["verse_number"],
                "tafsir_raw": tafsir if tafsir else "",
            }
        else:
            current_group["verses"].append(v)
            current_group["verse_keys"].append(v["verse_key"])
            current_group["last_verse"] = v["verse_number"]

    # Don't forget the last group
    if current_group is not None:
        groups.append(current_group)

    return groups


def build_chunk_from_group(group: dict, chunk_id: int) -> dict:
    """
    Build an embedding-ready chunk from a verse group.

    Embedded text = translations + cleaned tafsir
    Metadata = everything else (Arabic, verse keys, surah info, etc.)
    """
    # Combine Abdel Haleem translations for all verses
    haleem_parts = []
    sahih_parts = []
    arabic_parts = []

    for v in group["verses"]:
        vk = v["verse_key"]
        haleem = v.get("translation_abdel_haleem", "")
        sahih = v.get("translation_sahih_international", "")
        arabic = v.get("arabic_uthmani", "")

        if haleem:
            haleem_parts.append(f"[{vk}] {haleem}")
        if sahih:
            sahih_parts.append(f"[{vk}] {sahih}")
        if arabic:
            arabic_parts.append(f"[{vk}] {arabic}")

    combined_haleem = "\n".join(haleem_parts)
    combined_sahih = "\n".join(sahih_parts)
    combined_arabic = "\n".join(arabic_parts)
    cleaned_tafsir = clean_tafsir(group["tafsir_raw"])

    # Build the verse range string
    if group["first_verse"] == group["last_verse"]:
        verse_range = f"{group['surah_number']}:{group['first_verse']}"
    else:
        verse_range = f"{group['surah_number']}:{group['first_verse']}-{group['last_verse']}"

    # === TEXT FOR EMBEDDING ===
    # This is what gets converted into a vector
    embed_parts = [
        f"Surah {group['surah_name']} ({group['revelation_type'].title()}) — Verses {verse_range}",
        "",
        "Translation:",
        combined_haleem,
    ]

    if cleaned_tafsir:
        embed_parts.extend([
            "",
            "Tafsir (Context and Explanation):",
            cleaned_tafsir,
        ])

    embed_text = "\n".join(embed_parts)

    # === CHUNK RECORD ===
    chunk = {
        "chunk_id": chunk_id,
        "verse_range": verse_range,
        "verse_keys": group["verse_keys"],
        "surah_number": group["surah_number"],
        "surah_name": group["surah_name"],
        "surah_name_arabic": group["surah_name_arabic"],
        "revelation_type": group["revelation_type"],
        "num_verses": len(group["verses"]),

        # For embedding
        "embed_text": embed_text,
        "embed_token_estimate": estimate_tokens(embed_text),

        # For display (not embedded)
        "translation_abdel_haleem": combined_haleem,
        "translation_sahih_international": combined_sahih,
        "arabic_uthmani": combined_arabic,
        "tafsir_cleaned": cleaned_tafsir,

        # Topic tags placeholder (to be filled by LLM enrichment)
        "topic_tags": [],
    }

    return chunk


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Load corpus
    log.info("Loading corpus from %s ...", CORPUS_PATH)
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        verses = json.load(f)
    log.info("Loaded %d verses", len(verses))

    # Step 1: Group by tafsir
    log.info("=" * 60)
    log.info("STEP 1: Grouping verses by tafsir")
    log.info("=" * 60)
    groups = group_verses_by_tafsir(verses)
    log.info("Created %d verse groups from %d verses", len(groups), len(verses))

    # Step 2: Build chunks
    log.info("=" * 60)
    log.info("STEP 2: Building embedding-ready chunks")
    log.info("=" * 60)
    chunks = []
    for i, group in enumerate(groups):
        chunk = build_chunk_from_group(group, chunk_id=i + 1)
        chunks.append(chunk)

    log.info("Built %d chunks", len(chunks))

    # Step 3: Analyze
    log.info("=" * 60)
    log.info("STEP 3: Analyzing chunk sizes")
    log.info("=" * 60)

    token_counts = [c["embed_token_estimate"] for c in chunks]
    verse_counts = [c["num_verses"] for c in chunks]

    token_counts_sorted = sorted(token_counts)
    total_tokens = sum(token_counts)

    analysis = {
        "total_chunks": len(chunks),
        "total_verses_covered": sum(verse_counts),
        "total_estimated_tokens": total_tokens,
        "token_stats": {
            "min": min(token_counts),
            "max": max(token_counts),
            "mean": round(total_tokens / len(chunks)),
            "median": token_counts_sorted[len(token_counts_sorted) // 2],
            "p90": token_counts_sorted[int(len(token_counts_sorted) * 0.9)],
            "p95": token_counts_sorted[int(len(token_counts_sorted) * 0.95)],
            "p99": token_counts_sorted[int(len(token_counts_sorted) * 0.99)],
        },
        "verse_group_stats": {
            "min_verses": min(verse_counts),
            "max_verses": max(verse_counts),
            "mean_verses": round(sum(verse_counts) / len(verse_counts), 1),
            "single_verse_chunks": sum(1 for vc in verse_counts if vc == 1),
            "multi_verse_chunks": sum(1 for vc in verse_counts if vc > 1),
        },
        "over_8k_tokens": sum(1 for tc in token_counts if tc > 8000),
        "over_6k_tokens": sum(1 for tc in token_counts if tc > 6000),
        "over_4k_tokens": sum(1 for tc in token_counts if tc > 4000),
    }

    log.info("  Total chunks:       %d", analysis["total_chunks"])
    log.info("  Total verses:       %d", analysis["total_verses_covered"])
    log.info("  Token range:        %d - %d", analysis["token_stats"]["min"], analysis["token_stats"]["max"])
    log.info("  Mean tokens:        %d", analysis["token_stats"]["mean"])
    log.info("  Median tokens:      %d", analysis["token_stats"]["median"])
    log.info("  P90 tokens:         %d", analysis["token_stats"]["p90"])
    log.info("  P95 tokens:         %d", analysis["token_stats"]["p95"])
    log.info("  P99 tokens:         %d", analysis["token_stats"]["p99"])
    log.info("  Over 8K tokens:     %d chunks", analysis["over_8k_tokens"])
    log.info("  Over 6K tokens:     %d chunks", analysis["over_6k_tokens"])
    log.info("  Over 4K tokens:     %d chunks", analysis["over_4k_tokens"])
    log.info("  Single-verse chunks: %d", analysis["verse_group_stats"]["single_verse_chunks"])
    log.info("  Multi-verse chunks:  %d", analysis["verse_group_stats"]["multi_verse_chunks"])
    log.info("  Max verses in group: %d", analysis["verse_group_stats"]["max_verses"])

    # Show the largest chunks for review
    log.info("")
    log.info("  Top 5 largest chunks:")
    for c in sorted(chunks, key=lambda x: x["embed_token_estimate"], reverse=True)[:5]:
        log.info("    %s (%s) — %d tokens, %d verses",
                 c["verse_range"], c["surah_name"],
                 c["embed_token_estimate"], c["num_verses"])

    # Show a sample chunk
    log.info("")
    log.info("  Sample chunk (67:16-19):")
    for c in chunks:
        if c["verse_range"] == "67:16-19":
            log.info("    Verses: %s", c["verse_keys"])
            log.info("    Token estimate: %d", c["embed_token_estimate"])
            log.info("    Embed text preview:")
            log.info("    %s", c["embed_text"][:300])
            break

    # Save
    log.info("=" * 60)
    log.info("STEP 4: Saving outputs")
    log.info("=" * 60)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    log.info("  Saved %d chunks to %s", len(chunks), OUTPUT_PATH)

    with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    log.info("  Saved analysis to %s", ANALYSIS_PATH)

    log.info("=" * 60)
    log.info("CHUNKING COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
