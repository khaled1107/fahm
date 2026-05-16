#!/usr/bin/env python3
"""
dedupe_comprehension_bn.py

Removes duplicate sections from Bangla comprehension JSON files.
Mirrors dedupe_comprehension.py exactly but targets comprehension_bn/.

Usage:
    python3 dedupe_comprehension_bn.py              # dry run
    python3 dedupe_comprehension_bn.py --apply      # apply changes
    python3 dedupe_comprehension_bn.py --surah 2    # single surah
"""

import json, argparse
from pathlib import Path

COMPREHENSION_BN_DIR = Path("comprehension_bn")

def section_quality(sec):
    return len(sec.get("revelation_context", "") or "") + len(sec.get("bridge", "") or "")

def dedupe_surah(data):
    sections = data.get("sections", [])
    if not sections:
        return data, 0

    seen = {}
    removed = 0

    for sec in sections:
        keys = frozenset(str(k) for k in sec.get("verse_keys", []))
        if not keys:
            continue
        if keys not in seen:
            seen[keys] = sec
        else:
            if section_quality(sec) > section_quality(seen[keys]):
                seen[keys] = sec
            removed += 1

    kept_keys = set()
    deduped = []
    for sec in sections:
        keys = frozenset(str(k) for k in sec.get("verse_keys", []))
        if not keys:
            deduped.append(sec)
            continue
        if keys not in kept_keys and seen.get(keys) is not None:
            if seen[keys] is sec or section_quality(sec) >= section_quality(seen[keys]):
                deduped.append(sec)
                kept_keys.add(keys)

    for i, sec in enumerate(deduped):
        sec["section_number"] = i + 1

    data["sections"] = deduped
    return data, removed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--surah", type=int)
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — use --apply to save changes.\n")

    surah_range = [args.surah] if args.surah else range(1, 115)
    total_removed = 0
    affected = []

    for surah_num in surah_range:
        files = list(COMPREHENSION_BN_DIR.glob(f"{surah_num:03d}_*.json"))
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
        print(f"{'Surah':<8} {'Before':<10} {'After':<10} Removed")
        print("-" * 40)
        for surah_num, before, after, removed in affected:
            print(f"  {surah_num:<6} {before:<10} {after:<10} {removed}")
        action = 'removed' if args.apply else 'found'
        print(f"\nTotal duplicates {action}: {total_removed}")
        if not args.apply:
            print("\nRun with --apply to save changes.")
    else:
        print("No duplicates found.")

if __name__ == "__main__":
    main()
