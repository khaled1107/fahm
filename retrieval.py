#!/usr/bin/env python3
"""
retrieval.py
Hybrid retrieval pipeline for Fahm.
Combines vector search + keyword search using Reciprocal Rank Fusion (RRF).
Includes query expansion to enrich plain-English queries with Islamic terminology.
"""

import os, requests
from openai import OpenAI

# --- Config ---
EMBED_MODEL = "text-embedding-3-large"
DIMENSIONS = 1536
TOP_K = 20        # candidates from each search method
FINAL_K = 7       # chunks returned to generator
RRF_K = 60        # RRF constant (standard value)
MIN_SIMILARITY = 0.35  # filter out low-confidence vector results

# --- Clients ---
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

EXPANSION_SYSTEM_PROMPT = """You are an expert in Islamic studies and Quranic sciences.
Expand the user's question into specific search terms for finding relevant Quran verses.

Rules:
- Output 10-15 terms maximum — quality over quantity
- Be SPECIFIC to the question — avoid generic terms like "believers, taqwa, guidance, allah, quran, islam"
- Include Arabic terminology with English equivalents
- Focus on the emotional, situational, or legal core of the question
- Include specific Quranic concepts, named people, or events if relevant

Output ONLY comma-separated terms. No explanation.

Examples:
Input: what does Islam say about anxiety and worry
Output: anxiety, worry, grief, huzn, distress, ghamm, sakina, tranquility, ease after hardship, tawakkul, reliance on allah, peace of heart, fear, inner peace, relief

Input: is music haram
Output: music, singing, instruments, lahw al-hadith, idle talk, frivolity, entertainment, prohibited, permissible, luqman, distraction

Input: how do I deal with a difficult family member
Output: family conflict, silat al-rahim, kinship ties, forgiveness, anger, reconciliation, rights of family, patience with family, cutting ties, maintaining bonds"""

def expand_query(query: str) -> str:
    """
    Expand a user query with Islamic terminology and related concepts.
    Returns enriched search string for better embedding + keyword matching.
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EXPANSION_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        max_tokens=1600,
        temperature=0.2
    )
    expanded = response.choices[0].message.content.strip()
    # Combine original query + expanded terms
    return f"{query}. {expanded}"

def embed_query(query: str) -> list:
    """Embed a (potentially expanded) user query."""
    response = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=[query],
        dimensions=DIMENSIONS
    )
    return response.data[0].embedding

def vector_search(query_embedding: list, top_k: int = TOP_K) -> list:
    """Find top_k chunks by vector similarity, filtered by minimum threshold."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_chunks_vector",
        headers=SUPABASE_HEADERS,
        json={"query_embedding": query_embedding, "match_count": top_k}
    )
    r.raise_for_status()
    results = r.json()
    # Filter out low-confidence results
    return [r for r in results if r.get("similarity", 0) >= MIN_SIMILARITY]

def keyword_search(query: str, top_k: int = TOP_K) -> list:
    """Find top_k chunks by full-text keyword search."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_chunks_keyword",
        headers=SUPABASE_HEADERS,
        json={"query_text": query, "match_count": top_k}
    )
    r.raise_for_status()
    results = r.json()
    if isinstance(results, dict) and "message" in results:
        return []
    return results if isinstance(results, list) else []

def reciprocal_rank_fusion(
    vector_results: list,
    keyword_results: list,
    k: int = RRF_K
) -> list:
    """
    Merge and re-rank two result lists using Reciprocal Rank Fusion.
    RRF score = sum of 1/(k + rank) across all lists.
    Higher score = more relevant.
    """
    scores = {}
    chunk_data = {}

    for rank, chunk in enumerate(vector_results):
        chunk_id = chunk["id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
        chunk_data[chunk_id] = chunk

    for rank, chunk in enumerate(keyword_results):
        chunk_id = chunk["id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
        chunk_data[chunk_id] = chunk

    ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    results = []
    for chunk_id in ranked_ids:
        chunk = chunk_data[chunk_id].copy()
        chunk["rrf_score"] = round(scores[chunk_id], 6)
        results.append(chunk)

    return results

def retrieve(query: str, final_k: int = FINAL_K, expand: bool = True) -> tuple:
    """
    Main retrieval function.
    Takes a user query, returns (top final_k chunks, expanded_query string).
    expand=True enables query expansion (recommended for production).
    expand=False for debugging to see raw retrieval quality.
    """
    # 1. Expand query
    if expand:
        expanded_query = expand_query(query)
    else:
        expanded_query = query

    # 2. Embed expanded query
    query_embedding = embed_query(expanded_query)

    # 3. Run both searches
    vector_results = vector_search(query_embedding)
    keyword_results = keyword_search(expanded_query)

    # 4. Fuse with RRF
    fused = reciprocal_rank_fusion(vector_results, keyword_results)

    # 5. Return top final_k
    return fused[:final_k], expanded_query

def format_results_for_display(chunks: list, expanded_query: str = None) -> str:
    """Format retrieved chunks for readable display."""
    lines = []
    if expanded_query:
        lines.append(f"Expanded query: {expanded_query[:120]}...")
        lines.append("")
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] {chunk['surah_name']} {chunk['verse_range']} "
                     f"(RRF: {chunk.get('rrf_score', 'n/a')})")
        lines.append(f"     Tags: {', '.join(chunk.get('topic_tags', [])[:8])}")
        lines.append("")
    return "\n".join(lines)

# --- Test harness ---
if __name__ == "__main__":
    test_queries = [
        "what does Islam say about anxiety and worry",
        "riba and interest in business",
        "how to be patient during hardship",
        "what happens after death",
        "is music haram",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        print("-" * 60)
        results, expanded = retrieve(query)
        print(format_results_for_display(results, expanded))
        print("=" * 60)
        print()
