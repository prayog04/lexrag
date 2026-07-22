"""Streaming generation via Groq (fast, cheap, no GPU to manage for a POC).

Swapping providers later (OpenRouter, a self-hosted vLLM box, etc.) only
means changing this file — the retriever and API layer don't know or care
which LLM answers the question.
"""

from __future__ import annotations

from collections.abc import Iterator

from groq import Groq

from lexrag import config
from lexrag.retrieval.retriever import RetrievalResult

SYSTEM_PROMPT = """You are a legal research assistant for Indian criminal law, covering the \
Indian Penal Code (IPC, pre-2024) and the Bharatiya Nyaya Sanhita (BNS, its 2024 replacement).

Rules:
- Answer using ONLY the section text provided in the context below. Do not use outside knowledge \
of section numbers or punishments — this corpus is the source of truth for this conversation.
- Always cite the Act and section number for every claim, e.g. "IPC Section 302" or "BNS Section 103".
- When comparing an IPC section to its BNS counterpart, clearly separate: (1) what changed in the \
definition, (2) what changed in the punishment, (3) anything added or removed.
- If a retrieval note says a mapping is "suggested" or "not verified", tell the user explicitly to \
confirm it against the official MHA concordance table or gazette before relying on it — do not state \
it as settled fact.
- If the provided context doesn't contain enough to answer, say so plainly rather than guessing a \
section number or punishment.
- This is informational research assistance, not legal advice, and you are not a lawyer."""


def _get_client() -> Groq:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set — add it to your .env")
    return Groq(api_key=config.GROQ_API_KEY)


def build_context_block(result: RetrievalResult) -> str:
    parts = []
    for s in result.sections:
        parts.append(f"[{s.act} Section {s.section_no}] {s.section_title}\n{s.text}")
    if result.mapping_notes:
        parts.append("Retrieval notes:\n" + "\n".join(f"- {n}" for n in result.mapping_notes))
    return "\n\n---\n\n".join(parts) if parts else "(no matching sections found in the corpus)"


def stream_answer(query: str, result: RetrievalResult) -> Iterator[str]:
    client = _get_client()
    context = build_context_block(result)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
    stream = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=messages,
        stream=True,
        temperature=0.1,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
