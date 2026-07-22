"""Section -> Chunk(s).

Every section becomes exactly one "section" chunk holding its full text —
that's the unit that retains the most context (definition + exceptions +
punishment together), and it's what gets sent to the LLM.

Sections long enough that embedding the whole thing would blur its
semantics (a 400-word section about murder's five exceptions embeds as a
mushy average) are *additionally* split into "clause" chunks — one per
Illustration/Exception/Explanation block — so a query like "does self-defence
count as murder" can match the specific exception. Clause chunks carry
`parent_id` pointing back at the section chunk; retrieval matches on clauses
but expands to the parent section before handing text to the LLM (small-to-
big retrieval), so the model still sees the complete section.
"""

from __future__ import annotations

import re

from lexrag.models import Chunk, Section

MAX_CHARS_BEFORE_SPLIT = 3000

_CLAUSE_MARKER_RE = re.compile(r"(?m)^(Illustrations?\.|Exception\s+\d+\.|Explanation\s*\d*\.)")


def _split_clauses(text: str) -> list[str]:
    indices = [m.start() for m in _CLAUSE_MARKER_RE.finditer(text)]
    if not indices:
        return []
    bounds = sorted({0, *indices, len(text)})
    return [text[a:b].strip() for a, b in zip(bounds, bounds[1:]) if text[a:b].strip()]


def chunk_section(section: Section, dedupe_suffix: str = "") -> list[Chunk]:
    parent_id = f"{section.act}:{section.section_no}{dedupe_suffix}"
    base_metadata = {
        "headnote": getattr(section, "headnote", ""),
    }

    chunks = [
        Chunk(
            id=parent_id,
            act=section.act,
            section_no=section.section_no,
            section_title=section.section_title,
            chapter_no=section.chapter_no,
            chapter_title=section.chapter_title,
            chunk_type="section",
            text=section.text,
            parent_id=None,
            metadata=base_metadata,
        )
    ]

    if len(section.text) > MAX_CHARS_BEFORE_SPLIT:
        for i, clause_text in enumerate(_split_clauses(section.text)):
            chunks.append(
                Chunk(
                    id=f"{parent_id}:clause{i}",
                    act=section.act,
                    section_no=section.section_no,
                    section_title=section.section_title,
                    chapter_no=section.chapter_no,
                    chapter_title=section.chapter_title,
                    chunk_type="clause",
                    text=clause_text,
                    parent_id=parent_id,
                    metadata=base_metadata,
                )
            )

    return chunks


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    """Chunk a full list of sections, disambiguating any section numbers
    that legitimately repeat (e.g. state-amendment variants in the IPC)."""
    seen_counts: dict[tuple[str, str], int] = {}
    all_chunks: list[Chunk] = []
    for section in sections:
        key = (section.act, section.section_no)
        seen_counts[key] = seen_counts.get(key, 0) + 1
        suffix = f"#{seen_counts[key]}" if seen_counts[key] > 1 else ""
        all_chunks.extend(chunk_section(section, dedupe_suffix=suffix))
    return all_chunks
