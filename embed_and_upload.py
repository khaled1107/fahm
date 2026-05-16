#!/usr/bin/env python3
"""
embed_and_upload.py
Generates embeddings for all chunks using text-embedding-3-large (1536 dims)
and uploads them to Supabase via REST API.
Supports resuming — skips chunks already in the database.
"""

import os, json, time, requests, tiktoken
from pathlib import Path
from openai import OpenAI

CHUNKS_PATH = Path("corpus/chunks.json")
MODEL = "text-embedding-3-large"
DIMENSIONS = 1536
BATCH_SIZE = 100   # Upload to Supabase in batches
EMBED_BATCH = 20   # Embed N chunks per OpenAI API call
TOKENIZER = tiktoken.encoding_for_model("text-embedding-3-large")
MAX_TOKENS = 8191

# --- Clients ---
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

def get_existing_ids() -> set:
    """Fetch all chunk IDs already in the database."""
    existing = set()
    offset = 0
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/quran_chunks",
            headers={**SUPABASE_HEADERS, "Range": f"{offset}-{offset+999}"},
            params={"select": "id"}
        )
        data = r.json()
        if not data or not isinstance(data, list):
            break
        for row in data:
            existing.add(row["id"])
        if len(data) < 1000:
            break
        offset += 1000
    return existing

def truncate_to_limit(text: str) -> str:
    tokens = TOKENIZER.encode(text)
    if len(tokens) <= MAX_TOKENS:
        return text
    return TOKENIZER.decode(tokens[:MAX_TOKENS])

def embed_texts(texts: list) -> list:
    truncated = [truncate_to_limit(t) for t in texts]
    response = openai_client.embeddings.create(
        model=MODEL,
        input=truncated,
        dimensions=DIMENSIONS
    )
    return [item.embedding for item in response.data]

def chunk_to_row(chunk: dict, embedding: list) -> dict:
    """Convert a chunk dict + embedding to a Supabase row."""
    return {
        "id": chunk["chunk_id"],
        "surah_number": chunk["surah_number"],
        "surah_name": chunk["surah_name"],
        "revelation_type": chunk.get("revelation_type", ""),
        "verse_range": chunk.get("verse_range", ""),
        "verse_keys": chunk.get("verse_keys", []),
        "num_verses": chunk.get("num_verses", 0),
        "embed_text": chunk.get("embed_text", ""),
        "tafsir_cleaned": chunk.get("tafsir_cleaned", ""),
        "translation_abdel_haleem": [chunk["translation_abdel_haleem"]] if chunk.get("translation_abdel_haleem") else [],
        "translation_sahih_international": [chunk["translation_sahih_international"]] if chunk.get("translation_sahih_international") else [],
        "arabic_uthmani": [chunk["arabic_uthmani"]] if chunk.get("arabic_uthmani") else [],
        "topic_tags": chunk.get("topic_tags", []),
        "embedding": embedding,
    }

def upload_batch(rows: list):
    """Upload a batch of rows to Supabase via REST API."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/quran_chunks",
        headers=SUPABASE_HEADERS,
        json=rows
    )
    if r.status_code not in (200, 201):
        raise Exception(f"Upload failed: {r.status_code} {r.text[:200]}")

# --- Main ---
print("Loading chunks...")
with open(CHUNKS_PATH) as f:
    chunks = json.load(f)

print(f"Total chunks: {len(chunks)}")

print("Checking existing records in Supabase...")
existing_ids = get_existing_ids()
print(f"Already uploaded: {len(existing_ids)}")

to_process = [c for c in chunks if c["chunk_id"] not in existing_ids]
print(f"To embed and upload: {len(to_process)}")

if not to_process:
    print("Nothing to do — all chunks already uploaded.")
    exit(0)

print()

total = len(to_process)
uploaded = 0
errors = 0
upload_buffer = []

for i in range(0, total, EMBED_BATCH):
    batch = to_process[i:i + EMBED_BATCH]

    try:
        texts = [c["embed_text"] for c in batch]
        embeddings = embed_texts(texts)

        for chunk, embedding in zip(batch, embeddings):
            row = chunk_to_row(chunk, embedding)
            upload_buffer.append(row)

        if len(upload_buffer) >= BATCH_SIZE:
            upload_batch(upload_buffer)
            uploaded += len(upload_buffer)
            upload_buffer = []
            print(f"  [{uploaded}/{total}] uploaded...")

        time.sleep(0.1)

    except Exception as e:
        errors += 1
        print(f"  ERROR on batch starting at index {i}: {e}")
        if errors > 5:
            print("Too many errors — saving progress and exiting.")
            break
        time.sleep(3)

# Upload remaining rows
if upload_buffer:
    upload_batch(upload_buffer)
    uploaded += len(upload_buffer)

print(f"\nDone. Uploaded {uploaded} chunks. Errors: {errors}")
print(f"Total in database: {len(existing_ids) + uploaded}")
