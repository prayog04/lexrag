from lexrag.ingestion.chunker import chunk_sections
from lexrag.models import Section


def test_short_section_is_a_single_chunk():
    section = Section(
        act="IPC",
        section_no="1",
        section_title="Title",
        chapter_no="I",
        chapter_title="INTRODUCTION",
        text="1. Title.—Short text.",
    )
    chunks = chunk_sections([section])
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "section"
    assert chunks[0].id == "IPC:1"


def test_long_section_gets_clause_children_with_parent_link():
    long_text = "300. Murder.—" + ("x " * 2000) + "\nException 1.—first exception text.\nException 2.—second."
    section = Section(
        act="IPC",
        section_no="300",
        section_title="Murder",
        chapter_no="XVI",
        chapter_title="OF OFFENCES AFFECTING THE HUMAN BODY",
        text=long_text,
    )
    chunks = chunk_sections([section])
    parents = [c for c in chunks if c.chunk_type == "section"]
    clauses = [c for c in chunks if c.chunk_type == "clause"]
    assert len(parents) == 1
    assert len(clauses) >= 2
    assert all(c.parent_id == parents[0].id for c in clauses)


def test_duplicate_section_numbers_get_disambiguated():
    make = lambda text: Section(  # noqa: E731
        act="IPC", section_no="354E", section_title="", chapter_no="", chapter_title="", text=text
    )
    chunks = chunk_sections([make("first variant"), make("second variant")])
    ids = [c.id for c in chunks]
    assert ids == ["IPC:354E", "IPC:354E#2"]
