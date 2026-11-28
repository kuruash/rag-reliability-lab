import pytest

from rag_lab.documents import UploadTooLargeError, UploadValidationError, validate_pdf_upload


def test_validate_pdf_upload_accepts_pdf_signature() -> None:
    validate_pdf_upload(b"%PDF-1.7\nbody\n%%EOF", "application/pdf")


def test_validate_pdf_upload_rejects_wrong_content_type() -> None:
    with pytest.raises(UploadValidationError, match="content type"):
        validate_pdf_upload(b"%PDF-1.7", "text/plain")


def test_validate_pdf_upload_rejects_invalid_signature() -> None:
    with pytest.raises(UploadValidationError, match="signature"):
        validate_pdf_upload(b"not a PDF", "application/pdf")


def test_validate_pdf_upload_rejects_oversized_content() -> None:
    with pytest.raises(UploadTooLargeError, match="10 bytes"):
        validate_pdf_upload(b"%PDF-1.7\nxxx", "application/pdf", max_size_bytes=10)
