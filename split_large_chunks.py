#!/usr/bin/env python3
"""
split_large_chunks.py
Splits chunks over 8,191 tokens at paragraph boundaries into two sub-chunks.
Reads corpus/chunks.json, outputs updated corpus/chunks.json and chunk_analysis.json.
"""

import json, re, copy
from pathlib import Path

TOKEN_LIMIT = 8000
CHUNKS_PATH = Path("corpus/chunks.json")
ANALYSIS_PATH = Path("corpus/chunk_analysis.json")

def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4."""
    return len(text) // 4

def split_tafsir_at_midpoint(tafsir: str) -> tuple[str, str]:
    """
    Split tafsir text into two halves at a paragraph boundary closest to the midpoint.
    Falls back to sentence boundary, then hard split if needed.
    """
    mid = len(tafsir) // 2

    # Try paragraph boundary first
    paragraphs = tafsir.split("\n\n")
    if len(paragraphs) > 1:
        best_split = 0
        best_dist = float("inf")
        cumulative = 0
        for i, p in enumerate(paragraphs[:-1]):
            cumulative += len(p) + 2  # +2 for the \n\n
            dist = abs(cumulative - mid)
            if dist < best_dist:
                best_dist = dist
                best_split = i + 1
        part1 = "\n\n".join(paragraphs[:best_split])
        part2 = "\n\n".join(paragraphs[best_split:])
        if part1.strip() and part2.strip():
            return part1.strip(), part2.strip()

    # Fall back to sentence boundary
    sentences = re.split(r'(?<=[.!?])\s+', tafsir)
    if len(sentences) > 1:
        best_split = 0
        best_dist = float("inf")
        cumulative = 0
        for i, s in enumerate(sentences[:-1]):
            cumulative += len(s) + 1
            dist = abs(cumulative - mid)
            if dist < best_dist:
                best_dist = dist
                best_split = i + 1
        part1 = " ".join(sentences[:best_split])
        part2 = " ".join(sentences[best_split:])
        if part1.strip() and part2.strip():
            return part1.strip(), part2.strip()

    # Hard split at midpoint
    return tafsir[:mid].strip(), tafsir[mid:].strip()

def build_embed_text(chunk: dict, tafsir_override: str) -> str:
    """Rebuild embed_text with a different tafsir section."""
    lines = []
    lines.append(f"Surah {chunk['surah_name']} ({chunk['revelation_type']}) — Verses {chunk['verse_range']}")
    lines.append("")
    lines.append("Translation:")
    for key, text in zip(chunk['verse_keys'], chunk['translation_abdel_haleem']):
        lines.append(f"[{key}] {text}")
    lines.append("")
    if tafsir_override.strip():
        lines.append("Tafsir (Context and Explanation):")
        lines.append(tafsir_override)
    return "\n".join(lines)

def split_chunk(chunk: dict) -> list[dict]:
    """Split a chunk into two sub-chunks. Returns list of 1 or 2 chunks."""
    tafsir = chunk.get("tafsir_cleaned", "")
    if not tafsir.strip():
        # No tafsir to split — can't do much, return as-is with a warning
        print(f"  WARNING: {chunk['chunk_id']} has no tafsir to split — keeping as-is")
        return [chunk]

    part1_tafsir, part2_tafsir = split_tafsir_at_midpoint(tafsir)

    results = []
    for i, tafsir_part in enumerate([part1_tafsir, part2_tafsir], 1):
        c = copy.deepcopy(chunk)
        c["chunk_id"] = f"{chunk['chunk_id']}_part{i}"
        c["tafsir_cleaned"] = tafsir_part
        c["embed_text"] = build_embed_text(chunk, tafsir_part)
        c["embed_token_estimate"] = estimate_tokens(c["embed_text"])
        results.append(c)

    return results

def compute_analysis(chunks: list[dict]) -> dict:
    tokens = [c["embed_token_estimate"] for c in chunks]
    tokens_sorted = sorted(tokens)
    n = len(tokens_sorted)

    def percentile(p):
        idx = int(n * p / 100)
        return tokens_sorted[min(idx, n - 1)]

    verse_counts = [c["num_verses"] for c in chunks]

    return {
        "total_chunks": n,
        "total_verses_covered": sum(c["num_verses"] for c in chunks),
        "total_estimated_tokens": sum(tokens),
        "token_stats": {
            "min": min(tokens),
            "max": max(tokens),
            "mean": round(sum(tokens) / n),
            "median": percentile(50),
            "p90": percentile(90),
            "p95": percentile(95),
            "p99": percentile(99),
        },
        "verse_group_stats": {
            "min_verses": min(verse_counts),
            "max_verses": max(verse_counts),
            "mean_verses": round(sum(verse_counts) / n, 1),
            "single_verse_chunks": sum(1 for v in verse_counts if v == 1),
            "multi_verse_chunks": sum(1 for v in verse_counts if v > 1),
        },
        "over_8k_tokens": sum(1 for t in tokens if t > 8000),
        "over_6k_tokens": sum(1 for t in tokens if t > 6000),
        "over_4k_tokens": sum(1 for t in tokens if t > 4000),
    }

# --- Main ---
print("Loading chunks...")
with open(CHUNKS_PATH) as f:
    chunks = json.load(f)

over_limit = [c for c in chunks if c["embed_token_estimate"] > TOKEN_LIMIT]
under_limit = [c for c in chunks if c["embed_token_estimate"] <= TOKEN_LIMIT]

print(f"Total chunks: {len(chunks)}")
print(f"Over {TOKEN_LIMIT} tokens: {len(over_limit)}")
print()

new_chunks = list(under_limit)

for chunk in over_limit:
    print(f"Splitting: {chunk['chunk_id']} — {chunk['embed_token_estimate']} tokens")
    parts = split_chunk(chunk)
    for p in parts:
        print(f"  → {p['chunk_id']} — {p['embed_token_estimate']} tokens")
    new_chunks.extend(parts)

# Sort by surah + verse order
new_chunks.sort(key=lambda c: (c["surah_number"], c["verse_keys"][0]))

print(f"\nNew total chunks: {len(new_chunks)}")

# Check if any are still over limit
still_over = [c for c in new_chunks if c["embed_token_estimate"] > TOKEN_LIMIT]
if still_over:
    print(f"WARNING: {len(still_over)} chunks still over {TOKEN_LIMIT} tokens:")
    for c in still_over:
        print(f"  {c['chunk_id']} — {c['embed_token_estimate']} tokens")
else:
    print("All chunks are within the token limit.")

print("\nSaving updated chunks.json...")
with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
    json.dump(new_chunks, f, ensure_ascii=False, indent=2)

analysis = compute_analysis(new_chunks)
print("Saving updated chunk_analysis.json...")
with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
    json.dump(analysis, f, ensure_ascii=False, indent=2)

print("\nDone. Final stats:")
print(json.dumps(analysis, indent=2))
