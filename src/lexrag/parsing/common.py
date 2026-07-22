"""Shared parsing helpers for the IPC and BNS bare-act PDFs.

Both documents are numbered-section penal codes, but they come from different
sources: IPC-Codes.pdf is a plain single-column "bare act" compilation with
per-page amendment footnotes; BNS-Codes.pdf is an actual two-column Gazette of
India notification with side-margin headnotes and repeating Hindi/English
running headers. The regexes and filters below are tuned to what's actually
in these two files (verified by inspecting real pages), not generic PDF
heuristics.
"""

from __future__ import annotations

import re

# A new section starts at the beginning of a line: "302.", "304A.", "29A.".
# Requires a following space + some content so we don't match footnote refs
# like "18601" (a number glued to a superscript marker, no period).
SECTION_START_RE = re.compile(r"^(\d{1,3}[A-Z]{0,2})\.\s*(?=\S)")

# Section title in IPC body text runs up to an em-dash, e.g.
# "302. Punishment for murder.—Whoever commits murder..." -> "Punishment for murder."
SECTION_TITLE_RE = re.compile(r"^\d{1,3}[A-Z]{0,2}\.\s+(.*?\.)\s*—", re.DOTALL)

# Chapter headers: "CHAPTER XVI" (IPC, spaced) or "CHAPTERVI" (BNS, PDF glues
# the number to the word because of tight kerning in the Gazette PDF).
CHAPTER_RE = re.compile(r"^CHAPTER\s*([IVXLCDM]+)\b", re.IGNORECASE)

# A line consisting mostly of runs of spaces marks the horizontal rule that
# separates IPC body text from that page's amendment footnotes.
FOOTNOTE_RULE_RE = re.compile(r"\n {10,}\n")

# Amendment-history markers inline in IPC text, e.g. "3[extend to ... 4***]".
# We strip the leading digit+bracket and the closing bracket/asterisks; this
# is a best-effort cleanup, not a perfect one — see README caveat.
_LEADING_MARKER_RE = re.compile(r"(?<!\w)\d{1,2}\[")
_DELETION_MARKER_RE = re.compile(r"\d{1,2}\*{2,3}")


def strip_footnote_block(page_text: str) -> str:
    """Cut off everything from the first footnote horizontal rule onward."""
    m = FOOTNOTE_RULE_RE.search(page_text)
    return page_text[: m.start()] if m else page_text


def clean_amendment_markers(text: str) -> str:
    text = _LEADING_MARKER_RE.sub("", text)
    text = text.replace("]", "")
    text = _DELETION_MARKER_RE.sub("", text)
    return text


def is_page_number_only(text: str) -> bool:
    return text.strip().isdigit() and len(text.strip()) <= 4


# Substrings that mark Gazette-of-India furniture (running headers, cover
# masthead) rather than actual Act text. Checked case-sensitively since some
# of these are all-caps by convention and lowercase hits would be coincidence.
_GAZETTE_NOISE_SUBSTRINGS = (
    "GAZETTE OF INDIA",
    "EXTRAORDINARY",
    "PUBLISHED BY AUTHORITY",
    "MINISTRY OF LAW",
    "REGISTERED NO",
    "PART II",
    "SEPARATE PAGING",
    "NEW DELHI,",
    "Price :",
)


def is_gazette_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if is_page_number_only(stripped):
        return True
    if any(marker in stripped for marker in _GAZETTE_NOISE_SUBSTRINGS):
        return True
    if re.match(r"^Sec\.\s*\d+\]", stripped):
        return True
    # Devanagari masthead text: if a large share of characters are non-ASCII,
    # treat the block as Hindi furniture rather than substantive English text.
    non_ascii = sum(1 for c in stripped if ord(c) > 127)
    if len(stripped) > 0 and non_ascii / len(stripped) > 0.2:
        return True
    return False


def roman_to_int(roman: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(roman.upper()):
        val = values.get(ch, 0)
        total = total - val if val < prev else total + val
        prev = max(prev, val)
    return total
