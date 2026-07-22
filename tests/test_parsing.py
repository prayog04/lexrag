"""Regression tests against the real source PDFs.

These are intentionally light — the goal is to catch a parser regression
(e.g. a change to common.py silently dropping sections) before it reaches
ingestion, not to exhaustively validate every section.
"""

from lexrag import config
from lexrag.parsing.bns_parser import parse_bns
from lexrag.parsing.ipc_parser import parse_ipc


def test_ipc_parses_known_sections():
    sections = {s.section_no: s for s in parse_ipc(config.IPC_PDF_PATH)}
    assert len(sections) > 500
    assert sections["302"].section_title == "Punishment for murder"
    assert sections["302"].chapter_no == "XVI"
    assert "death" in sections["302"].text.lower()


def test_bns_parses_known_sections_and_has_no_gaps():
    sections_list = parse_bns(config.BNS_PDF_PATH)
    sections = {s.section_no: s for s in sections_list}
    assert len(sections) == 358
    assert sections["101"].headnote == "Murder."
    assert "murder" in sections["101"].text.lower()

    numeric = {int(no.rstrip("ABCDEFGH")) for no in sections}
    assert numeric == set(range(1, 359))
