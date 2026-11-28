import uuid
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rag_lab.chunking import chunk_pages
from rag_lab.parsing import parse_pdf

pytestmark = pytest.mark.integration


@pytest.fixture()
def sample_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (integration sample) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_parse_and_chunk_small_pdf_fixture(sample_pdf) -> None:
    pages = parse_pdf(sample_pdf)
    chunks = chunk_pages(
        pages,
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        version=1,
        chunk_size=11,
        overlap=2,
    )

    assert pages[0].page_number == 1
    assert pages[0].text == "integration sample"
    assert [chunk.text for chunk in chunks] == ["integration", "on sample"]
    assert all(
        chunk.document_id == uuid.UUID("00000000-0000-0000-0000-000000000001") for chunk in chunks
    )
