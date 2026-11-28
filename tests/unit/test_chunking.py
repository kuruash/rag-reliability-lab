import uuid

import pytest
from pydantic import ValidationError

from rag_lab.chunking import ChunkingConfigurationError, chunk_pages
from rag_lab.config import Settings
from rag_lab.parsing import ParsedPage

DOCUMENT_ID = uuid.UUID("00000000-0000-4000-8000-000000000123")


def test_chunk_pages_applies_character_boundaries_and_overlap() -> None:
    chunks = chunk_pages(
        (ParsedPage(page_number=2, text="abcdefghij"),),
        document_id=DOCUMENT_ID,
        version=3,
        chunk_size=6,
        overlap=2,
    )

    assert [chunk.text for chunk in chunks] == ["abcdef", "efghij"]
    assert [(chunk.page_number, chunk.chunk_index) for chunk in chunks] == [(2, 0), (2, 1)]
    assert all(chunk.document_id == DOCUMENT_ID and chunk.version == 3 for chunk in chunks)


def test_chunk_pages_skips_empty_pages_but_preserves_source_pages() -> None:
    chunks = chunk_pages(
        (
            ParsedPage(page_number=1, text="  first\npage  "),
            ParsedPage(page_number=2, text=""),
            ParsedPage(page_number=3, text="third"),
        ),
        document_id=DOCUMENT_ID,
        version=1,
        chunk_size=20,
        overlap=0,
    )

    assert [chunk.text for chunk in chunks] == ["first page", "third"]
    assert [chunk.page_number for chunk in chunks] == [1, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_chunk_pages_is_deterministic() -> None:
    pages = (ParsedPage(page_number=1, text="same input"),)

    assert chunk_pages(pages, document_id=DOCUMENT_ID, version=1) == chunk_pages(
        pages, document_id=DOCUMENT_ID, version=1
    )


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (-1, 0), (10, -1), (10, 10)],
)
def test_chunk_pages_rejects_invalid_configuration(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ChunkingConfigurationError):
        chunk_pages(
            (ParsedPage(page_number=1, text="text"),),
            document_id=DOCUMENT_ID,
            version=1,
            chunk_size=chunk_size,
            overlap=overlap,
        )


def test_settings_reject_invalid_chunking_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(chunk_size=10, chunk_overlap=10)
