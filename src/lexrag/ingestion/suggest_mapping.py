"""Bootstrap IPC <-> BNS section-number candidates by fuzzy-matching titles.

This does NOT produce an authoritative concordance. It compares each IPC
section's title against every BNS section's headnote/title with rapidfuzz
and keeps the best match above a score threshold, writing rows marked
"suggested" to data/mapping/ipc_bns_mapping.csv. A human must review these
against the official MHA concordance table before treating them as fact —
see the module docstring in lexrag.retrieval.mapping for why we refuse to
let embedding/fuzzy similarity stand in for exact legal section mapping at
query time.

Run: python -m lexrag.ingestion.suggest_mapping
"""

from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz, process

from lexrag.parsing.bns_parser import parse_bns
from lexrag.parsing.ipc_parser import parse_ipc
from lexrag.retrieval.mapping import DEFAULT_MAPPING_PATH

SCORE_THRESHOLD = 72
DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"


def main() -> None:
    ipc_sections = parse_ipc(DOCS_DIR / "IPC-Codes.pdf")
    bns_sections = parse_bns(DOCS_DIR / "BNS-Codes.pdf")

    existing_ipc_nos: set[str] = set()
    if DEFAULT_MAPPING_PATH.exists():
        with DEFAULT_MAPPING_PATH.open(newline="", encoding="utf-8") as f:
            existing_ipc_nos = {row["ipc_section"] for row in csv.DictReader(f)}

    bns_titles = {s.section_no: (s.headnote or "").strip() for s in bns_sections if s.headnote}
    choices = list(bns_titles.items())  # [(section_no, title), ...]

    new_rows = []
    for s in ipc_sections:
        if s.section_no in existing_ipc_nos or not s.section_title:
            continue
        match = process.extractOne(
            s.section_title,
            [t for _, t in choices],
            scorer=fuzz.token_sort_ratio,
        )
        if match is None or match[1] < SCORE_THRESHOLD:
            continue
        matched_title, score, idx = match
        bns_no = choices[idx][0]
        new_rows.append(
            {
                "ipc_section": s.section_no,
                "bns_section": bns_no,
                "status": "suggested",
                "notes": f"fuzzy title match ({score:.0f}/100): '{s.section_title}' ~ '{matched_title}' — please verify",
            }
        )

    file_exists = DEFAULT_MAPPING_PATH.exists()
    with DEFAULT_MAPPING_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ipc_section", "bns_section", "status", "notes"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)

    print(f"Appended {len(new_rows)} suggested mappings to {DEFAULT_MAPPING_PATH}")
    print("These are fuzzy-title guesses, not fact — review before trusting them.")


if __name__ == "__main__":
    main()
