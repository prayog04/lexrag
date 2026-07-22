"""IPC <-> BNS section concordance.

Section-number mapping is exact, curated data — it must never be answered by
embedding similarity, because a wrong section number is exactly the kind of
confident-sounding hallucination an LLM will produce without grounding. This
module loads a plain CSV (ipc_section, bns_section, status, notes) and
serves it as a dict lookup.

The CSV is *not* a complete authoritative concordance out of the box. A
couple of rows are marked "verified" because we cross-checked the actual
section text in both PDFs while building this project (e.g. IPC 300/302 ->
BNS 101/103 for culpable-homicide-is-murder / punishment-for-murder). Most
rows, if you run `python -m lexrag.ingestion.suggest_mapping`, come out
marked "suggested" — a fuzzy title/headnote match a human should confirm
against the official MHA concordance table before trusting it in production.
Never present a "suggested" row to an end user as fact without that check.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "data" / "mapping" / "ipc_bns_mapping.csv"


@dataclass
class MappingEntry:
    ipc_section: str
    bns_section: str
    status: str  # "verified" | "suggested"
    notes: str = ""


class Concordance:
    def __init__(self, entries: list[MappingEntry]):
        self.entries = entries
        self._ipc_to_bns: dict[str, list[MappingEntry]] = {}
        self._bns_to_ipc: dict[str, list[MappingEntry]] = {}
        for e in entries:
            self._ipc_to_bns.setdefault(e.ipc_section, []).append(e)
            self._bns_to_ipc.setdefault(e.bns_section, []).append(e)

    def bns_for_ipc(self, ipc_section: str) -> list[MappingEntry]:
        return self._ipc_to_bns.get(ipc_section, [])

    def ipc_for_bns(self, bns_section: str) -> list[MappingEntry]:
        return self._bns_to_ipc.get(bns_section, [])


def load_mapping(path: str | Path = DEFAULT_MAPPING_PATH) -> Concordance:
    path = Path(path)
    if not path.exists():
        return Concordance([])
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        entries = [
            MappingEntry(
                ipc_section=row["ipc_section"].strip(),
                bns_section=row["bns_section"].strip(),
                status=row.get("status", "suggested").strip() or "suggested",
                notes=row.get("notes", "").strip(),
            )
            for row in reader
            if row.get("ipc_section") and row.get("bns_section")
        ]
    return Concordance(entries)
