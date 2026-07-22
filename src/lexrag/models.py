from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    """One section of a penal code (IPC or BNS) — the atomic legal unit."""

    act: str  # "IPC" or "BNS"
    section_no: str  # e.g. "302", "304A"
    section_title: str
    chapter_no: str
    chapter_title: str
    text: str  # full section body, headnote-clean, footnote-clean
    headnote: str = ""  # BNS margin note / IPC inline title, when available


@dataclass
class Chunk:
    """A retrievable unit derived from a Section. Most sections are one chunk;
    long sections are split into parent + child chunks so retrieval can match
    a specific clause while the LLM still gets the full section as context."""

    id: str
    act: str
    section_no: str
    section_title: str
    chapter_no: str
    chapter_title: str
    chunk_type: str  # "section" (parent, full text) or "clause" (child, partial)
    text: str
    parent_id: str | None = None
    metadata: dict = field(default_factory=dict)
