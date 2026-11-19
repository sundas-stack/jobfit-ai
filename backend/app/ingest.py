"""Read uploaded files, split them into chunks, embed and store them."""

import io
import re

from pypdf import PdfReader
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Chunk, Document
from .embeddings import get_embedder


class IngestError(ValueError):
    pass


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
ACCEPTED = "PDF, Word (DOCX), image (PNG, JPG, WEBP) or TXT"
MAX_PDF_PAGES = 15


def ocr_image(img) -> str:
    """Read the text in an image with Tesseract OCR."""
    import pytesseract
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img).convert("L")
    if img.width < 1400:  # small images: upscale so the letters are big enough to read
        scale = 1400 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, config="--psm 3")


def _pdf_text(data: bytes) -> str:
    """Text from each page; pages without a text layer (scans) are read with OCR."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES]]
    except Exception as exc:  # pypdf raises many types
        raise IngestError("Could not open this PDF. Is it password-protected or damaged?") from exc

    if all(len(t.strip()) >= 40 for t in pages):
        return "\n".join(pages)

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    out = []
    for i, text in enumerate(pages):
        if len(text.strip()) >= 40:
            out.append(text)
        else:
            image = pdf[i].render(scale=3).to_pil()  # ~216 dpi
            out.append(ocr_image(image))
    pdf.close()
    return "\n".join(out)


def _docx_text(data: bytes) -> str:
    import docx

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise IngestError("Could not open this Word file. Try saving it again as DOCX or PDF.") from exc
    lines = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells if c.text.strip()))
    return "\n".join(lines)


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        text = _pdf_text(data)
    elif name.endswith(".docx"):
        text = _docx_text(data)
    elif name.endswith(IMAGE_EXT):
        from PIL import Image, UnidentifiedImageError

        try:
            text = ocr_image(Image.open(io.BytesIO(data)))
        except UnidentifiedImageError as exc:
            raise IngestError("Could not open this image.") from exc
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".doc"):
        raise IngestError("Old .doc files are not supported. In Word, use Save As and choose DOCX or PDF.")
    else:
        raise IngestError(f"This file type is not supported. Upload a {ACCEPTED}.")
    text = clean_text(text)
    if len(text) < 40:
        raise IngestError(
            "Could not read enough text from this file. If it is a photo, make sure the text is sharp and "
            "well lit, or paste the text instead."
        )
    return text


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n").replace("•", "\n• ").replace("\t", " ")
    text = re.sub(r"[  ]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    # OCR reads bullet points as stray characters (e, ¢, «, ©): turn them back into bullets
    text = re.sub(r"(?m)^[ ]*[e¢«©°*o·»>-][ ]+(?=[A-Z0-9])", "• ", text)
    return text.strip()


def chunk_text(text: str, size: int | None = None) -> list[str]:
    """Pack lines into chunks of about `size` characters, never splitting a line.

    Resumes and job ads are line-oriented (bullets, headings), so line packing keeps
    each bullet whole, which makes citations readable.
    """
    size = size or get_settings().chunk_size
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        # very long lines (pasted paragraphs) get split on sentences
        pieces = re.split(r"(?<=[.!?])\s+", line) if len(line) > size else [line]
        for piece in pieces:
            if current and length + len(piece) > size:
                chunks.append("\n".join(current))
                current, length = [], 0
            current.append(piece)
            length += len(piece) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def guess_title(kind: str, text: str, filename: str | None) -> str:
    first = next((ln.strip() for ln in text.split("\n") if ln.strip()), "")
    if kind == "job" and 3 < len(first) < 90:
        return first
    if filename:
        return re.sub(r"\.(pdf|txt|md)$", "", filename, flags=re.I)[:120]
    return (first[:80] or ("Resume" if kind == "resume" else "Job ad")).strip()


def create_document(
    session: Session, *, kind: str, text: str, title: str | None = None, filename: str | None = None
) -> Document:
    if kind not in ("resume", "job"):
        raise IngestError("kind must be 'resume' or 'job'")
    text = clean_text(text)
    if len(text) < 40:
        raise IngestError("Please provide at least a few lines of text.")

    doc = Document(kind=kind, title=(title or guess_title(kind, text, filename))[:200], filename=filename, text=text)
    pieces = chunk_text(text)
    vectors = get_embedder().embed(pieces)
    prefix = "R" if kind == "resume" else "J"
    doc.chunks = [
        Chunk(idx=i, label=f"{prefix}{i + 1}", text=piece, embedding=vec)
        for i, (piece, vec) in enumerate(zip(pieces, vectors, strict=True))
    ]
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc
