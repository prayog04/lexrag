"""Parser for IPC-Codes.pdf — a single-column bare-act compilation.

Layout notes (verified against the actual file):
- Pages 0-12 are the "arrangement of sections" table of contents; the real
  Act text starts on the page containing the Preamble ("WHEREAS it is
  expedient...").
- Each page's body text is followed by a block of amendment footnotes,
  separated from the body by a line of 10+ spaces (see common.FOOTNOTE_RULE_RE).
- Section titles are inline: "302. Punishment for murder.—Whoever...".
- Amendment markers like "3[extend to the whole of India 4***]" are stripped
  on a best-effort basis (see common.clean_amendment_markers) — this is not a
  perfect restoration of the un-amended text, just noise reduction.

Known gap (verified, not a silent failure): Section 17 is rendered in the
source PDF as "1[17 "Government".—..." with no period after the number
(every other section has one), so it doesn't match SECTION_START_RE and its
text is folded into section 16. A couple of section numbers (e.g. 354E, 467)
legitimately repeat because the bare act includes state-amendment variants
under the same base number — that's the source document, not a bug. Run
`python -m lexrag.ingestion.ingest --dry-run` after any PDF update to reprint
this kind of diagnostic.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from lexrag.models import Section
from lexrag.parsing.common import (
    CHAPTER_RE,
    SECTION_START_RE,
    SECTION_TITLE_RE,
    clean_amendment_markers,
    strip_footnote_block,
)

_LEADING_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,4}\s*\n\s*\n")


def parse_ipc(pdf_path: str | Path) -> list[Section]:
    doc = fitz.open(str(pdf_path))

    body_start = next(
        (i for i, page in enumerate(doc) if "WHEREAS it is expedient" in page.get_text()),
        None,
    )
    if body_start is None:
        raise RuntimeError(
            "Could not locate the IPC preamble — has the source PDF changed structure?"
        )

    page_texts = []
    for page in doc[body_start:]:
        text = page.get_text()
        text = _LEADING_PAGE_NUMBER_RE.sub("", text)
        text = strip_footnote_block(text)
        page_texts.append(text)
    full_text = clean_amendment_markers("\n".join(page_texts))

    sections: list[Section] = []
    chapter_no = ""
    chapter_title = ""
    awaiting_chapter_title = False
    cur_no: str | None = None
    cur_lines: list[str] = []

    def flush() -> None:
        nonlocal cur_no, cur_lines
        if cur_no is not None:
            body = re.sub(r"[ \t]+", " ", "\n".join(cur_lines)).strip()
            title_m = SECTION_TITLE_RE.match(body)
            title = re.sub(r"\s+", " ", title_m.group(1)).rstrip(".") if title_m else ""
            sections.append(
                Section(
                    act="IPC",
                    section_no=cur_no,
                    section_title=title,
                    chapter_no=chapter_no,
                    chapter_title=chapter_title,
                    text=body,
                )
            )
        cur_no = None
        cur_lines = []

    for raw_line in full_text.split("\n"):
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
            continue

        if cur_no is not None:
            cur_lines.append(line)

    flush()
    return sections
