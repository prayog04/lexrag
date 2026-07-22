"""Parser for BNS-Codes.pdf — an actual two-column Gazette of India notification.

Layout notes (verified against the actual file, page-by-page block inspection):
- Every page repeats Hindi/English running headers ("Sec. 1] THE GAZETTE OF
  INDIA EXTRAORDINARY 31", "[PART II-SEC. 1]", etc.) and the first page has a
  bilingual masthead. These are filtered out by common.is_gazette_noise.
- The body text lives in a main column (x0 roughly 100-480pt). A side margin
  column carries one-line "headnotes" for each section (e.g. "Culpable
  homicide." next to section 100) — on odd/even pages this column sits on
  the left (x0 < 100) or right (x0 > 480) respectively.
- PyMuPDF's block segmentation is *not* one-block-per-section: when a short
  section immediately follows the end of another with no extra vertical gap
  (e.g. section 12, a single paragraph, right after section 11's lettered
  list), both land in the same block. So section boundaries are detected at
  the *line* level within the main column's text stream, the same way the
  IPC parser does it — not by assuming a block always starts a new section.
- There is no separate table-of-contents like IPC's; the Act text starts on
  page 0.

Headnote attachment is a heuristic: on any given page we zip that page's
margin notes to that page's newly-started sections, in top-to-bottom order,
*only* when the counts match exactly. This is correct on the large majority
of pages (verified by spot-check) but silently skips headnotes on pages
where a section spans a page break in a way that breaks the 1:1 count — the
full section text is unaffected either way, only the short `headnote` field
is left blank. Treat `headnote` as a nice-to-have, not authoritative.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from lexrag.models import Section
from lexrag.parsing.common import (
    CHAPTER_RE,
    SECTION_START_RE,
    is_gazette_noise,
)

_MAIN_COL_X_MIN = 100
_MAIN_COL_X_MAX = 480


def parse_bns(pdf_path: str | Path) -> list[Section]:
    doc = fitz.open(str(pdf_path))

    main_lines_by_page: list[list[str]] = []
    margin_blocks_by_page: list[list[str]] = []

    for page in doc:
        raw_blocks = page.get_text("blocks")
        main, margin = [], []
        for x0, y0, _x1, _y1, text, *_ in raw_blocks:
            stripped = text.strip()
            if not stripped or is_gazette_noise(stripped):
                continue
            if x0 < _MAIN_COL_X_MIN or x0 > _MAIN_COL_X_MAX:
                margin.append((y0, stripped))
            else:
                main.append((y0, text))
        main.sort(key=lambda t: t[0])
        margin.sort(key=lambda t: t[0])

        # Flatten blocks to lines: a block can contain more than one section
        # (see module docstring), so section boundaries must be found within
        # each block's text, not just at its start.
        page_lines: list[str] = []
        for _, block_text in main:
            page_lines.extend(block_text.split("\n"))
        main_lines_by_page.append(page_lines)
        margin_blocks_by_page.append([t for _, t in margin])

    sections: list[Section] = []
    section_starts_by_page: list[list[str]] = [[] for _ in doc]
    chapter_no = ""
    chapter_title = ""
    awaiting_chapter_title = False
    cur_no: str | None = None
    cur_lines: list[str] = []

    def flush() -> None:
        nonlocal cur_no, cur_lines
        if cur_no is not None:
            body = re.sub(r"[ \t]+", " ", "\n".join(cur_lines)).strip()
            # BNS body text has no inline "Title.—" convention like IPC does;
            # the authoritative short title is the side-margin headnote,
            # attached in a second pass below once it's been collected.
            sections.append(
                Section(
                    act="BNS",
                    section_no=cur_no,
                    section_title="",
                    chapter_no=chapter_no,
                    chapter_title=chapter_title,
                    text=body,
                )
            )
        cur_no = None
        cur_lines = []

    for page_idx, lines in enumerate(main_lines_by_page):
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            chap_m = CHAPTER_RE.match(line)
            if chap_m:
                flush()
                chapter_no = chap_m.group(1)
                awaiting_chapter_title = True
                continue

            if awaiting_chapter_title:
                chapter_title = line
                awaiting_chapter_title = False
                continue

            sec_m = SECTION_START_RE.match(line)
            if sec_m:
                flush()
                cur_no = sec_m.group(1)
                cur_lines = [line]
                section_starts_by_page[page_idx].append(cur_no)
                continue

            if cur_no is not None:
                cur_lines.append(line)

    flush()

    # Best-effort headnote attachment: zip margin notes to section starts on
    # the same page, only when the counts line up exactly.
    headnote_map: dict[str, str] = {}
    for page_idx, margin_notes in enumerate(margin_blocks_by_page):
        starts = section_starts_by_page[page_idx]
        if margin_notes and starts and len(margin_notes) == len(starts):
            for note, sec_no in zip(margin_notes, starts):
                headnote_map[sec_no] = note.replace("\n", " ").strip()

    for s in sections:
        note = headnote_map.get(s.section_no, "")
        s.headnote = note
        s.section_title = note.rstrip(".")

    return sections
