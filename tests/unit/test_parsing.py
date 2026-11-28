from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from rag_lab.parsing import (
    EmptyPdfError,
    EncryptedPdfError,
    ImageOnlyPdfError,
    MalformedPdfError,
    parse_pdf,
)


def make_pdf(text: str | None = "hello") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text is not None:
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
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_parse_pdf_extracts_page_numbers_and_accepts_stream() -> None:
    parsed = parse_pdf(BytesIO(make_pdf("page one")))

    assert parsed[0].page_number == 1
    assert parsed[0].text == "page one"


def test_parse_pdf_rejects_empty_pdf() -> None:
    with pytest.raises(EmptyPdfError):
        parse_pdf(make_pdf(None))


def test_parse_pdf_rejects_malformed_pdf() -> None:
    with pytest.raises(MalformedPdfError):
        parse_pdf(b"not a PDF")


def test_parse_pdf_rejects_encrypted_pdf() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)

    with pytest.raises(EncryptedPdfError):
        parse_pdf(output.getvalue())


def test_parse_pdf_rejects_image_only_pdf() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=10, height=10)
    image = DecodedStreamObject()
    image.set_data(b"\x00")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceGray"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): image_ref})}
    )
    output = BytesIO()
    writer.write(output)

    with pytest.raises(ImageOnlyPdfError):
        parse_pdf(output.getvalue())
