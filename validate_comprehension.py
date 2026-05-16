#!/usr/bin/env python3
"""
validate_comprehension.py

Comprehensive validation of generated comprehension content against corpus chunks.
Checks:
1. Which surahs are missing entirely
2. Which surahs have fewer sections than expected
3. Which specific verse keys are missing within each surah
4. Duplicate verse keys within a surah
5. JSON parse errors in any file

Usage:
    python3 validate_comprehension.py
    python3 validate_comprehension.py --fix    # also writes a rerun script
"""

import json, os, argparse
from pathlib import Path
from collections import defaultdict

COMPREHENSION_DIR = Path("comprehension")
CHUNKS_PATH       = Path("corpus/chunks.json")

def load_chunks_by_surah():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    by_surah = defaultdict(list)
    for chunk in chunks:
        by_surah[chunk["surah_number"]].append(chunk)
    return by_surah

def get_expected_verse_keys(chunks):
    keys = []
    for chunk in chunks:
        keys.extend(chunk["verse_keys"])
    return keys

def normalize_key(k):
    if isinstance(k, int):
        s = str(k)
        if len(s) <= 3:
            return s
        verse = int(s[-3:])
        surah = int(s[:-3])
        return f"{surah}:{verse}"
    return str(k)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Write a rerun script for all issues")
    parser.add_argument("--surah", type=int, help="Validate a single surah only")
    args = parser.parse_args()

    print("Loading corpus chunks...")
    chunks_by_surah = load_chunks_by_surah()

    surah_range = [args.surah] if args.surah else range(1, 115)

    # ── Results ──────────────────────────────────────────────
    missing_surahs      = []
    json_errors         = []
    low_section_surahs  = []   # generated but sections < expected
    missing_keys        = {}   # surah_num -> list of missing verse keys
    duplicate_keys      = {}   # surah_num -> list of duplicate verse keys

    print(f"\nValidating {len(list(surah_range))} surahs...\n")

    for surah_num in surah_range:
        expected_chunks = chunks_by_surah.get(surah_num, [])
        expected_keys   = set(normalize_key(k) for c in expected_chunks for k in c["verse_keys"])
        expected_count  = len(expected_chunks)

        # Find the file
        files = list(COMPREHENSION_DIR.glob(f"{surah_num:03d}_*.json"))

        if not files:
            missing_surahs.append(surah_num)
            continue

        # Try to parse
        try:
            with open(files[0], encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            json_errors.append((surah_num, str(e)))
            continue

        sections = data.get("sections", [])
        actual_count = len(sections)

        # Collect all verse keys in generated content
        generated_keys = set()
        dup_check = defaultdict(int)
        for sec in sections:
            for k in sec.get("verse_keys", []):
                nk = normalize_key(k)
                dup_check[nk] += 1
                generated_keys.add(nk)

        # Missing keys
        missing = sorted(expected_keys - generated_keys,
                        key=lambda k: (int(k.split(":")[0]), int(k.split(":")[1])) if ":" in k else (0, 0))
        if missing:
            missing_keys[surah_num] = missing

        # Duplicates
        dups = [k for k, count in dup_check.items() if count > 1]
        if dups:
            duplicate_keys[surah_num] = dups

        # Low section count (more than 2 missing)
        if actual_count < expected_count - 2:
            low_section_surahs.append((surah_num, actual_count, expected_count))

    # ── Report ───────────────────────────────────────────────
    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)

    total_issues = len(missing_surahs) + len(json_errors) + len(missing_keys) + len(duplicate_keys)

    print(f"\n✓ Surahs present and valid: {114 - len(missing_surahs) - len(json_errors)}")
    print(f"✗ Total issues found: {total_issues}")

    if missing_surahs:
        print(f"\n── MISSING SURAHS ({len(missing_surahs)}) ──────────────────────────")
        for s in missing_surahs:
            chunks = chunks_by_surah.get(s, [])
            print(f"  Surah {s:3d} — {len(chunks)} sections expected, file not found")

    if json_errors:
        print(f"\n── JSON ERRORS ({len(json_errors)}) ──────────────────────────────")
        for s, err in json_errors:
            print(f"  Surah {s:3d} — {err[:80]}")

    if low_section_surahs:
        print(f"\n── LOW SECTION COUNT ({len(low_section_surahs)}) ──────────────────────")
        for s, actual, expected in sorted(low_section_surahs):
            diff = expected - actual
            print(f"  Surah {s:3d} — {actual}/{expected} sections ({diff} missing)")

    if missing_keys:
        print(f"\n── MISSING VERSE KEYS ({len(missing_keys)} surahs affected) ──────────")
        for s in sorted(missing_keys.keys()):
            keys = missing_keys[s]
            print(f"  Surah {s:3d} — {len(keys)} verse keys missing: {keys[:8]}{'...' if len(keys) > 8 else ''}")

    if duplicate_keys:
        print(f"\n── DUPLICATE VERSE KEYS ({len(duplicate_keys)} surahs affected) ────────")
        for s in sorted(duplicate_keys.keys()):
            keys = duplicate_keys[s]
            print(f"  Surah {s:3d} — {len(keys)} duplicate keys: {keys[:5]}{'...' if len(keys) > 5 else ''}")

    print("\n" + "=" * 60)

    # ── Write fix script ─────────────────────────────────────
    if args.fix:
        fix_surahs = set(missing_surahs)
        fix_surahs.update(s for s, _ in json_errors)
        fix_surahs.update(s for s, _, _ in low_section_surahs if (_ < __ - 5) for _, __ in [(_, _)])
        # Also add surahs with many missing keys
        for s, keys in missing_keys.items():
            if len(keys) > 3:
                fix_surahs.add(s)

        # Simpler: just include all surahs with missing keys > 3 or missing entirely
        fix_surahs = set(missing_surahs)
        fix_surahs.update(s for s, _ in json_errors)
        for s, keys in missing_keys.items():
            if len(keys) > 3:
                fix_surahs.add(s)

        fix_script = "#!/bin/bash\n# Auto-generated fix script\n# Run: bash fix_comprehension.sh\n\n"
        for s in sorted(fix_surahs):
            fix_script += f"echo 'Regenerating surah {s}...'\n"
            fix_script += f"python3 generate_comprehension.py --surah {s}\n\n"

        with open("fix_comprehension.sh", "w") as f:
            f.write(fix_script)

        print(f"\nFix script written to fix_comprehension.sh")
        print(f"Surahs to rerun: {sorted(fix_surahs)}")
        print(f"\nRun with: bash fix_comprehension.sh")

    if total_issues == 0:
        print("\n✓ All surahs look good!")

if __name__ == "__main__":
    main()
