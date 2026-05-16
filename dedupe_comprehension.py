#!/usr/bin/env python3
"""
dedupe_comprehension.py

Removes duplicate sections (same verse_keys) from comprehension JSON files.
Keeps the section with more content (longer context + bridge combined).
Renumbers sections sequentially after deduplication.

Usage:
    python3 dedupe_comprehension.py              # dry run — shows what would change
    python3 dedupe_comprehension.py --apply      # applies changes
    python3 dedupe_comprehension.py --surah 2    # single surah
"""

import json, argparse
from pathlib import Path

COMPREHENSION_DIR = Path("comprehension")

def section_quality(sec):
    """Score a section by total content length — higher is better."""
    return len(sec.get("revelation_context", "") or "") + len(sec.get("bridge", "") or "")

def dedupe_surah(data):
    sections = data.get("sections", [])
    if not sections:
        return data, 0

    # Group sections by their frozenset of verse_keys
    seen = {}
    removed = 0

    for sec in sections:
        keys = frozenset(str(k) for k in sec.get("verse_keys", []))
        if not keys:
            continue
        if keys not in seen:
            seen[keys] = sec
        else:
            # Keep the one with more content
            existing = seen[keys]
            if section_quality(sec) > section_quality(existing):
                seen[keys] = sec
            removed += 1

    # Rebuild sections in original order, keeping winners only
    kept_keys = set()
    deduped = []
    for sec in sections:
        keys = frozenset(str(k) for k in sec.get("verse_keys", []))
        if not keys:
            deduped.append(sec)
            continue
        if keys not in kept_keys and seen.get(keys) is not None:
            # Only keep if this is the winner
            if seen[keys] is sec or section_quality(sec) >= section_quality(seen[keys]):
                deduped.append(sec)
                kept_keys.add(keys)
        # else skip — it's a duplicate

    # Renumber sections sequentially
    for i, sec in enumerate(deduped):
        sec["section_number"] = i + 1

    data["sections"] = deduped
    return data, removed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--surah", type=int, help="Process a single surah only")
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — no files will be modified. Use --apply to save changes.\n")

    surah_range = [args.surah] if args.surah else range(1, 115)
    total_removed = 0
    affected = []

    for surah_num in surah_range:
        files = list(COMPREHENSION_DIR.glob(f"{surah_num:03d}_*.json"))
        if not files:
            continue

        with open(files[0], encoding="utf-8") as f:
            data = json.load(f)

        original_count = len(data.get("sections", []))
        deduped_data, removed = dedupe_surah(data)

        if removed > 0:
            affected.append((surah_num, original_count, original_count - removed, removed))
            total_removed += removed

            if args.apply:
                with open(files[0], "w", encoding="utf-8") as f:
                    json.dump(deduped_data, f, ensure_ascii=False, indent=2)

    if affected:
        print(f"{'Surah':<8} {'Before':<10} {'After':<10} {'Removed'}")
        print("-" * 40)
        for surah_num, before, after, removed in affected:
            print(f"  {surah_num:<6} {before:<10} {after:<10} {removed}")
        print(f"\nTotal duplicates {'removed' if args.apply else 'found'}: {total_removed}")
        if not args.apply:
            print("\nRun with --apply to save changes.")
    else:
        print("No duplicates found.")

if __name__ == "__main__":
    main()
