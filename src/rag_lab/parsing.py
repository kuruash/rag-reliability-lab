from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from pypdf import PdfReader


class PdfProcessingError(ValueError):
    """Base error for PDFs that cannot be converted to text."""


class EmptyPdfError(PdfProcessingError):
    """Raised when a PDF has no pages or no extractable text."""


class EncryptedPdfError(PdfProcessingError):
    """Raised when a PDF requires a password."""


class ImageOnlyPdfError(PdfProcessingError):
    """Raised when a PDF contains images but no extractable text."""


class MalformedPdfError(PdfProcessingError):
    """Raised when the PDF cannot be read or a page cannot be extracted."""


@dataclass(frozen=True, slots=True)
class ParsedPage:
    page_number: int
    text: str


def _normalize_page_text(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _page_has_image(page: object) -> bool:
    try:
        resources = page.get("/Resources")  # type: ignore[union-attr]
        if resources is None:
            return False
        xobjects = resources.get("/XObject")
        if xobjects is None:
            return False
        for reference in xobjects.values():
            xobject = reference.get_object()
            if xobject.get("/Subtype") == "/Image":
                return True
    except Exception:
        return False
    return False


def parse_pdf(source: bytes | BinaryIO) -> tuple[ParsedPage, ...]:
    """Extract deterministic, page-numbered text from PDF bytes or a binary stream."""
    if isinstance(source, bytes):
        source = BytesIO(source)

    try:
        reader = PdfReader(source)
    except Exception as exc:
        raise MalformedPdfError("the PDF could not be read") from exc

    if reader.is_encrypted:
        raise EncryptedPdfError("encrypted PDFs are not supported without a password")

    try:
        pages: list[ParsedPage] = []
        saw_image = False
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_page_text(page.extract_text())
            pages.append(ParsedPage(page_number=page_number, text=text))
            saw_image = saw_image or _page_has_image(page)
    except Exception as exc:
        raise MalformedPdfError("text extraction failed for the PDF") from exc

    if not pages or not any(page.text for page in pages):
        if saw_image:
            raise ImageOnlyPdfError("the PDF contains no extractable text; OCR is not enabled")
        raise EmptyPdfError("the PDF contains no extractable text")
    return tuple(pages)
