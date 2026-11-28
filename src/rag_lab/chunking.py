import re
import uuid
from dataclasses import dataclass

from rag_lab.parsing import ParsedPage


class ChunkingConfigurationError(ValueError):
    """Raised when chunk size or overlap configuration is invalid."""


@dataclass(frozen=True, slots=True)
class TextChunk:
    document_id: uuid.UUID
    version: int
    page_number: int
    chunk_index: int
    text: str


def _normalize_chunk_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_pages(
    pages: tuple[ParsedPage, ...] | list[ParsedPage],
    *,
    document_id: uuid.UUID,
    version: int,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> tuple[TextChunk, ...]:
    """Split page text into deterministic character-count chunks.

    Chunks are generated page by page in page order. ``chunk_index`` is a
    document-wide zero-based index, and overlap is repeated Unicode characters
    between adjacent chunks on the same page.
    """
    if chunk_size <= 0:
        raise ChunkingConfigurationError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ChunkingConfigurationError("overlap must be at least zero and less than chunk_size")
    if version < 1:
        raise ChunkingConfigurationError("version must be at least one")

    chunks: list[TextChunk] = []
    for page in pages:
        text = _normalize_chunk_text(page.text)
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(
                TextChunk(
                    document_id=document_id,
                    version=version,
                    page_number=page.page_number,
                    chunk_index=len(chunks),
                    text=text[start:end],
                )
            )
            if end == len(text):
                break
            start = end - overlap
    return tuple(chunks)
