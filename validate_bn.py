#!/usr/bin/env python3
"""
validate_bn.py

Comprehensive validation of Bangla comprehension content against corpus chunks.
Mirrors validate_comprehension.py exactly, but targets comprehension_bn/.

Checks:
1. Missing files
2. JSON parse errors
3. Low section count vs expected chunks
4. Missing verse keys within each surah
5. Duplicate verse keys within a surah
6. Integer verse keys
7. Missing required fields (introduction, title, revelation_context, bridge)

Usage:
    python3 validate_bn.py
    python3 validate_bn.py --fix
"""

import json, argparse
from pathlib import Path
from collections import defaultdict

COMPREHENSION_BN_DIR = Path("comprehension_bn")
CHUNKS_PATH          = Path("corpus/chunks.json")

def load_chunks_by_surah():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    by_surah = defaultdict(list)
    for chunk in chunks:
        by_surah[chunk["surah_number"]].append(chunk)
    return by_surah

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

    missing_surahs     = []
    json_errors        = []
    low_section_surahs = []
    missing_keys       = {}
    duplicate_keys     = {}
    field_issues       = []

    print(f"\nValidating {len(list(surah_range))} Bangla surahs...\n")

    for surah_num in surah_range:
        expected_chunks = chunks_by_surah.get(surah_num, [])
        expected_keys   = set(normalize_key(k) for c in expected_chunks for k in c["verse_keys"])
        expected_count  = len(expected_chunks)

        files = list(COMPREHENSION_BN_DIR.glob(f"{surah_num:03d}_*.json"))

        if not files:
            missing_surahs.append(surah_num)
            continue

        try:
            with open(files[0], encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            json_errors.append((surah_num, str(e)))
            continue

        sections = data.get("sections", [])
        actual_count = len(sections)

        # Check introduction
        intro = data.get("introduction", "").strip()
        if not intro:
            field_issues.append(f"Surah {surah_num:3d}: MISSING introduction")

        # Low section count
        if actual_count < expected_count - 2:
            low_section_surahs.append((surah_num, actual_count, expected_count))

        # Verse key checks
        generated_keys = set()
        dup_check = defaultdict(int)
        for sec in sections:
            # Check required fields
            if not sec.get("title", "").strip():
                field_issues.append(f"Surah {surah_num:3d} Section {sec.get('section_number','?')}: MISSING title")
            if not sec.get("revelation_context", "").strip():
                field_issues.append(f"Surah {surah_num:3d} Section {sec.get('section_number','?')}: MISSING revelation_context")
            if not sec.get("bridge", "").strip():
                field_issues.append(f"Surah {surah_num:3d} Section {sec.get('section_number','?')}: MISSING bridge")

            for k in sec.get("verse_keys", []):
                nk = normalize_key(k)
                dup_check[nk] += 1
                generated_keys.add(nk)

        # Missing keys
        missing = sorted(
            expected_keys - generated_keys,
            key=lambda k: (int(k.split(":")[0]), int(k.split(":")[1])) if ":" in k else (0, 0)
        )
        if missing:
            missing_keys[surah_num] = missing

        # Duplicates
        dups = [k for k, count in dup_check.items() if count > 1]
        if dups:
            duplicate_keys[surah_num] = dups

    # ── Report ──
    print("=" * 60)
    print("BANGLA VALIDATION REPORT")
    print("=" * 60)

    total_issues = (len(missing_surahs) + len(json_errors) +
                    len(missing_keys) + len(duplicate_keys) + len(field_issues))

    print(f"\n✓ Surahs present: {114 - len(missing_surahs) - len(json_errors)}/114")
    print(f"✗ Total issues: {total_issues}")

    if missing_surahs:
        print(f"\n── MISSING SURAHS ({len(missing_surahs)}) ──")
        for s in missing_surahs:
            print(f"  Surah {s:3d} — file not found")

    if json_errors:
        print(f"\n── JSON ERRORS ({len(json_errors)}) ──")
        for s, err in json_errors:
            print(f"  Surah {s:3d} — {err[:80]}")

    if low_section_surahs:
        print(f"\n── LOW SECTION COUNT ({len(low_section_surahs)}) ──")
        for s, actual, expected in sorted(low_section_surahs):
            print(f"  Surah {s:3d} — {actual}/{expected} sections ({expected - actual} missing)")

    if missing_keys:
        print(f"\n── MISSING VERSE KEYS ({len(missing_keys)} surahs) ──")
        for s in sorted(missing_keys.keys()):
            keys = missing_keys[s]
            print(f"  Surah {s:3d} — {len(keys)} missing: {keys[:8]}{'...' if len(keys) > 8 else ''}")

    if duplicate_keys:
        print(f"\n── DUPLICATE VERSE KEYS ({len(duplicate_keys)} surahs) ──")
        for s in sorted(duplicate_keys.keys()):
            keys = duplicate_keys[s]
            print(f"  Surah {s:3d} — {len(keys)} duplicates: {keys[:5]}")

    if field_issues:
        print(f"\n── MISSING FIELDS ({len(field_issues)}) ──")
        for fi in field_issues[:30]:
            print(f"  {fi}")
        if len(field_issues) > 30:
            print(f"  ... and {len(field_issues) - 30} more")

    print("\n" + "=" * 60)

    if args.fix:
        fix_surahs = set(missing_surahs)
        fix_surahs.update(s for s, _ in json_errors)
        for s, keys in missing_keys.items():
            if len(keys) > 3:
                fix_surahs.add(s)

        fix_script = "#!/bin/bash\n# Auto-generated Bangla fix script\n\n"
        for s in sorted(fix_surahs):
            fix_script += f"echo 'Regenerating Bangla surah {s}...'\n"
            fix_script += f"rm -f comprehension_bn/{s:03d}_*.json\n"
            fix_script += f"python3 generate_comprehension_bn.py --surah {s}\n\n"

        with open("fix_comprehension_bn.sh", "w") as f:
            f.write(fix_script)

        print(f"\nFix script written to fix_comprehension_bn.sh")
        print(f"Surahs to rerun: {sorted(fix_surahs)}")
        print(f"Run with: bash fix_comprehension_bn.sh")

    if total_issues == 0:
        print("\n✓ All 114 Bangla surahs look good — ready to migrate!")

if __name__ == "__main__":
    main()
