#!/usr/bin/env python3
"""Fixes the upsert function in migrate_to_supabase.py to handle existing data."""

with open('migrate_to_supabase.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def upsert(table, rows):
    """Upsert rows into a Supabase table via REST API."""
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    # Send as list always
    data = rows if isinstance(rows, list) else [rows]
    r = requests.post(url, headers=HEADERS, json=data)
    if r.status_code not in (200, 201):
        raise Exception(f"Upsert to {table} failed: {r.status_code} {r.text[:200]}")'''

new = '''def upsert(table, rows):
    """Upsert rows into a Supabase table via REST API."""
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data = rows if isinstance(rows, list) else [rows]
    headers = dict(HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    r = requests.post(url, headers=headers, json=data)
    if r.status_code not in (200, 201):
        raise Exception(f"Upsert to {table} failed: {r.status_code} {r.text[:200]}")'''

if old in content:
    content = content.replace(old, new)
    with open('migrate_to_supabase.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed migrate_to_supabase.py")
else:
    # Try patching HEADERS directly
    old2 = '''HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}'''
    new2 = '''HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}'''
    if old2 in content:
        content = content.replace(old2, new2)
        with open('migrate_to_supabase.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed HEADERS in migrate_to_supabase.py")
    else:
        print("Could not find exact string to replace.")
        print("Manually change the Prefer header to: resolution=merge-duplicates,return=minimal")
