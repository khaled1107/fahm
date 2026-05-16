#!/usr/bin/env python3
"""
generation.py
Generation pipeline for Fahm.
Takes a user query + retrieved chunks, returns a structured answer
with summary, full answer, and citations.
"""

import os, json
from openai import OpenAI
from retrieval import retrieve

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """You are Fahm — a warm, knowledgeable friend who helps people understand Islam through the Quran.

Your answers should feel like a thoughtful friend explaining something over coffee — not a lecture, not a fatwa, not a khutbah. You are grounded in the Quran and tafsir, but you speak in plain, modern English.

## Your audience
Culturally Muslim people who believe in Islam but haven't engaged deeply with it. They fast in Ramadan, pray occasionally, and carry low-level curiosity or guilt. They want real answers, not judgment. They're not scholars and don't want to be talked down to.

## Answer format
You must respond in valid JSON with exactly this structure:
{
  "summary": "One short paragraph (2-3 sentences). Direct answer to the question. No fluff.",
  "answer": "Up to three paragraphs. Warm, conversational, grounded in the sources provided. Use citation markers like [1], [2], [3] inline where you reference a verse or tafsir. Never more than three paragraphs.",
  "citations": [
    {
      "index": 1,
      "surah_name": "...",
      "verse_range": "...",
      "verse_keys": ["..."],
      "translation": "..."
    }
  ],
  "disclaimer": "Only include this field if the question involves a fiqh ruling or scholarly disagreement. One sentence max. Otherwise omit this field entirely."
}

## Tone rules
- Warm, direct, never preachy
- Never say "as a Muslim you should..." or "it is obligatory upon you..."
- Never lecture about what the person is doing wrong
- Use "the Quran says" or "according to the tafsir" naturally, not stiffly
- If the Quran doesn't directly address something, say so honestly and explain what it does say that's relevant
- Acknowledge when scholars disagree rather than presenting one view as absolute truth
- End with something that feels like closure, not a cliffhanger

## Citation rules
- Only cite sources that were actually provided to you in the context
- Use [1], [2], [3] etc. inline in the answer text where relevant
- List every cited source in the citations array with the verse translation
- Do NOT make up verse references or translations
- If none of the provided sources are relevant enough to cite, say so honestly rather than forcing citations

## What NOT to do
- Do not start with "Great question!" or any filler opener
- Do not repeat the question back to the user
- Do not use bullet points or headers in the answer
- Do not be excessively long — clarity over comprehensiveness
- Do not make the person feel guilty for not knowing this already"""

def format_context(chunks: list) -> str:
    """Format retrieved chunks into context for the prompt."""
    lines = ["Here are the relevant Quran passages and their tafsir (commentary):"]
    lines.append("")
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] {chunk['surah_name']} — {chunk['verse_range']}")
        # Include translation
        translation = chunk.get("translation_abdel_haleem", "")
        if isinstance(translation, list):
            translation = " ".join(translation)
        if translation:
            lines.append(f"Translation: {translation}")
        # Include tafsir (trimmed to keep context manageable)
        tafsir = chunk.get("tafsir_cleaned", "")
        if tafsir:
            # Cap tafsir at 800 chars per chunk to keep total context reasonable
            trimmed = tafsir[:800] + ("..." if len(tafsir) > 800 else "")
            lines.append(f"Commentary: {trimmed}")
        lines.append("")
    return "\n".join(lines)

def generate_answer(query: str, chunks: list) -> dict:
    """Generate a structured answer given a query and retrieved chunks."""
    context = format_context(chunks)

    user_message = f"""Question: {query}

{context}

Please answer the question based on the passages above. Remember to respond in the JSON format specified."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1200,
        temperature=0.4,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)

def ask(query: str) -> dict:
    """
    Main entry point. Takes a user question, returns structured answer dict.
    """
    # Retrieve relevant chunks
    chunks, expanded_query = retrieve(query)

    # Generate answer
    answer = generate_answer(query, chunks)

    # Attach chunk metadata for UI use
    answer["_chunks"] = chunks
    answer["_expanded_query"] = expanded_query

    return answer

def format_answer_for_display(answer: dict) -> str:
    """Pretty-print an answer dict for terminal display."""
    lines = []

    lines.append("SUMMARY")
    lines.append("─" * 60)
    lines.append(answer.get("summary", ""))
    lines.append("")

    lines.append("ANSWER")
    lines.append("─" * 60)
    lines.append(answer.get("answer", ""))
    lines.append("")

    citations = answer.get("citations", [])
    if citations:
        lines.append("CITATIONS")
        lines.append("─" * 60)
        for c in citations:
            lines.append(f"[{c['index']}] {c['surah_name']} {c['verse_range']}")
            lines.append(f"    \"{c.get('translation', '')}\"")
            lines.append("")

    disclaimer = answer.get("disclaimer")
    if disclaimer:
        lines.append("─" * 60)
        lines.append(f"Note: {disclaimer}")

    return "\n".join(lines)

# --- Test harness ---
if __name__ == "__main__":
    test_queries = [
        "what does Islam say about anxiety and worry",
        "is music haram",
        "what happens after we die",
    ]

    for query in test_queries:
        print(f"\nQ: {query}")
        print("=" * 60)
        try:
            answer = ask(query)
            print(format_answer_for_display(answer))
        except Exception as e:
            print(f"ERROR: {e}")
        print()
