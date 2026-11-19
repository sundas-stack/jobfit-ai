"""Every supported file type, including scanned documents read with OCR."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ingest import IngestError, extract_text

LINES = ["Data Operator", "Requirements", "• Basic Excel and Google Sheets skills", "• Stable internet connection"]


def _image() -> Image.Image:
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError:
        font = ImageFont.load_default(size=34)
    img = Image.new("RGB", (900, 360), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(LINES):
        draw.text((40, 30 + i * 75), line, fill="black", font=font)
    return img


def _bytes(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("name,fmt", [("job.png", "PNG"), ("job.jpg", "JPEG")])
def test_reads_text_from_images(name, fmt):
    text = extract_text(name, _bytes(_image(), fmt))
    assert "Excel" in text and "Requirements" in text


def test_reads_scanned_pdf_with_ocr():
    # a PDF that is only a picture, like a scanned job flyer
    text = extract_text("scan.pdf", _bytes(_image(), "PDF"))
    assert "Google Sheets" in text


def test_reads_docx():
    import docx

    d = docx.Document()
    for line in LINES:
        d.add_paragraph(line)
    table = d.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Salary", "Rs. 4000"
    buf = io.BytesIO()
    d.save(buf)
    text = extract_text("job.docx", buf.getvalue())
    assert "Excel" in text and "Rs. 4000" in text


def test_old_doc_format_gets_a_clear_message():
    with pytest.raises(IngestError, match="DOCX"):
        extract_text("cv.doc", b"anything")


def test_blank_image_is_rejected():
    with pytest.raises(IngestError, match="enough text"):
        extract_text("blank.png", _bytes(Image.new("RGB", (800, 600), "white"), "PNG"))
