"""Retrieval for the chat endpoint.

Three retrieval modes, chosen by what the query looks like:

1. Exact section lookup — the query names a section number ("Section 302",
   "IPC 420"). We fetch that section by payload filter, not vector search.
   Embeddings are bad at exact numeric identifiers; a filter is exact.
2. IPC<->BNS comparison — the query asks for an equivalent/mapping between
   the two acts. We resolve the section via the curated concordance
   (lexrag.retrieval.mapping) and fetch both sides' full section text.
3. Semantic search — anything else. Dense vector search over section-level
   chunks (falling back to clause-level chunks resolved back up to their
   parent section — "small-to-big" retrieval, see lexrag.ingestion.chunker).

This intentionally does NOT let step 3 answer step 1/2-shaped questions:
letting an embedding model guess a section number is how you get a
confidently wrong citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from lexrag import config
from lexrag.ingestion.embed import embed_query
from lexrag.retrieval.mapping import Concordance, load_mapping

#  Binds an act name to a section number when they're adjacent ("IPC 420",
#  "IPC Section 420", "Section 420 of the BNS"), rather than just noticing
#  that both an act and a number appear somewhere in the sentence — a query
#  like "BNS equivalent of IPC Section 302" mentions BNS first but the
#  number 302 belongs to IPC, not BNS.
_SECTION_MENTION_RE = re.compile(
    r"\b(?P<actA>IPC|BNS)\s*(?:section|sec\.?|s\.)?\s*(?P<numA>\d{1,3}[A-Z]{0,2})\b"
    r"|"
    r"\b(?:section|sec\.?|s\.)\s*(?P<numB>\d{1,3}[A-Z]{0,2})\b"
    r"(?:\s+(?:of\s+(?:the\s+)?)?(?P<actB>IPC|BNS))?",
    re.IGNORECASE,
)
_MAPPING_INTENT_RE = re.compile(
    r"\bequivalent\b|\bmap(?:s|ping|ped)?\b|\bcorrespond\w*\b|\bversus\b|\bcompare\w*\b|\bvs\.?\b",
    re.IGNORECASE,
)
_ACT_MENTION_RE = re.compile(r"\b(IPC|BNS)\b", re.IGNORECASE)


@dataclass
class RetrievedSection:
    act: str
    section_no: str
    section_title: str
    chapter_no: str
    chapter_title: str
    text: str
    score: float | None = None


@dataclass
class RetrievalResult:
    mode: str  # "exact" | "mapping" | "semantic"
    sections: list[RetrievedSection] = field(default_factory=list)
    mapping_notes: list[str] = field(default_factory=list)


class Retriever:
    def __init__(self, client: QdrantClient | None = None, concordance: Concordance | None = None):
        self.client = client or QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
        self.concordance = concordance or load_mapping()

    def _payload_to_section(self, payload: dict, score: float | None = None) -> RetrievedSection:
        return RetrievedSection(
            act=payload["act"],
            section_no=payload["section_no"],
            section_title=payload.get("section_title", ""),
            chapter_no=payload.get("chapter_no", ""),
            chapter_title=payload.get("chapter_title", ""),
            text=payload["text"],
            score=score,
        )

    def get_section(self, act: str, section_no: str) -> RetrievedSection | None:
        results, _ = self.client.scroll(
            collection_name=config.QDRANT_COLLECTION,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(key="act", match=qmodels.MatchValue(value=act.upper())),
                    qmodels.FieldCondition(key="section_no", match=qmodels.MatchValue(value=section_no)),
                    qmodels.FieldCondition(key="chunk_type", match=qmodels.MatchValue(value="section")),
                ]
            ),
            limit=1,
        )
        if not results:
            return None
        return self._payload_to_section(results[0].payload)

    def semantic_search(self, query: str, act: str | None = None, top_k: int = config.TOP_K) -> list[RetrievedSection]:
        vector = embed_query(query)
        must = []
        if act:
            must.append(qmodels.FieldCondition(key="act", match=qmodels.MatchValue(value=act.upper())))
        query_filter = qmodels.Filter(must=must) if must else None

        hits = self.client.query_points(
            collection_name=config.QDRANT_COLLECTION,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
        ).points

        sections: list[RetrievedSection] = []
        seen_parents: set[str] = set()
        for hit in hits:
            payload = hit.payload
            if payload["chunk_type"] == "clause":
                # Small-to-big: the clause matched, but the LLM gets the
                # full parent section for complete context.
                parent = self.get_section(payload["act"], payload["section_no"])
                key = f"{payload['act']}:{payload['section_no']}"
                if parent and key not in seen_parents:
                    seen_parents.add(key)
                    parent.score = hit.score
                    sections.append(parent)
            else:
                key = f"{payload['act']}:{payload['section_no']}"
                if key not in seen_parents:
                    seen_parents.add(key)
                    sections.append(self._payload_to_section(payload, hit.score))
        return sections

    def compare(self, act: str, section_no: str) -> RetrievalResult:
        notes: list[str] = []
        sections: list[RetrievedSection] = []

        primary = self.get_section(act, section_no)
        if primary:
            sections.append(primary)
        else:
            notes.append(f"Could not find {act} Section {section_no} in the indexed corpus.")

        if act.upper() == "IPC":
            entries = self.concordance.bns_for_ipc(section_no)
        else:
            entries = self.concordance.ipc_for_bns(section_no)

        if not entries:
            notes.append(
                f"No concordance entry for {act} Section {section_no} yet — "
                "run suggest_mapping and/or add it to data/mapping/ipc_bns_mapping.csv."
            )
        for entry in entries:
            other_act, other_no = ("BNS", entry.bns_section) if act.upper() == "IPC" else ("IPC", entry.ipc_section)
            other = self.get_section(other_act, other_no)
            if other:
                sections.append(other)
            if entry.status != "verified":
                notes.append(
                    f"Mapping {act.upper()} {section_no} -> {other_act} {other_no} is a "
                    f"'{entry.status}' suggestion, not a verified fact — {entry.notes}"
                )

        return RetrievalResult(mode="mapping", sections=sections, mapping_notes=notes)

    def retrieve(self, query: str) -> RetrievalResult:
        section_candidates: list[tuple[str | None, str]] = []
        for m in _SECTION_MENTION_RE.finditer(query):
            act = m.group("actA") or m.group("actB")
            num = m.group("numA") or m.group("numB")
            if num:
                section_candidates.append((act.upper() if act else None, num))

        if not section_candidates:
            act_mentions = {m.upper() for m in _ACT_MENTION_RE.findall(query)}
            act_filter = act_mentions.pop() if len(act_mentions) == 1 else None
            return RetrievalResult(mode="semantic", sections=self.semantic_search(query, act=act_filter))

        is_mapping_query = bool(_MAPPING_INTENT_RE.search(query))
        # Only used when a candidate has no act bound directly to its number
        # (a bare "Section 302" with an act named elsewhere in the sentence).
        act_mentions = [m.upper() for m in _ACT_MENTION_RE.findall(query)]
        fallback_act = act_mentions[0] if act_mentions else "IPC"

        if is_mapping_query:
            act, no = section_candidates[0]
            return self.compare(act or fallback_act, no)

        result = RetrievalResult(mode="exact")
        for act, no in section_candidates:
            section = self.get_section(act or fallback_act, no)
            if section:
                result.sections.append(section)
            else:
                result.mapping_notes.append(f"Could not find {(act or fallback_act)} Section {no}.")
        return result
