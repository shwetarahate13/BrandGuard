"""Text extraction from PDF and DOCX files."""
import io
import logging
import mimetypes
import zipfile
from pathlib import Path
from fastapi import HTTPException

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_UPLOAD_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/html",
    "image/png",
    "image/jpeg",
    "image/svg+xml",
}

def max_file_size() -> int:
    return get_settings().MAX_UPLOAD_SIZE_MB * 1024 * 1024


def get_upload_mime_type(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type not in SUPPORTED_UPLOAD_MIMES:
        raise ValueError(f"Unsupported file type: {Path(filename).suffix.lower()}")
    return mime_type


def sanitize_upload_filename(filename: str | None) -> str:
    """Keep a short basename with safe printable characters for stored metadata."""
    basename = (filename or "uploaded_content").replace("\\", "/").rsplit("/", 1)[-1]
    safe = "".join(char if char.isalnum() or char in ".-_" else "_" for char in basename)
    safe = safe.strip("._")[:128]
    return safe or "uploaded_content"


def sniff_upload_mime_type(contents: bytes, filename: str) -> str:
    """Verify content signatures against the supported filename type."""
    expected = get_upload_mime_type(filename)
    valid = False
    if expected == "application/pdf":
        valid = contents.startswith(b"%PDF-")
    elif expected == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as document:
                entries = document.infolist()
                names = {entry.filename for entry in entries}
                total_uncompressed_size = sum(entry.file_size for entry in entries)
                valid = (
                    "[Content_Types].xml" in names
                    and "word/document.xml" in names
                    and len(entries) <= 500
                    and total_uncompressed_size <= 25 * 1024 * 1024
                )
        except (OSError, zipfile.BadZipFile):
            valid = False
    elif expected == "image/png":
        valid = contents.startswith(b"\x89PNG\r\n\x1a\n")
    elif expected == "image/jpeg":
        valid = contents.startswith(b"\xff\xd8\xff")
    elif expected == "image/svg+xml":
        try:
            from defusedxml import ElementTree

            root = ElementTree.fromstring(contents)
            valid = root.tag.rsplit("}", 1)[-1].lower() == "svg"
        except Exception:
            valid = False
    elif expected in {"text/plain", "text/markdown", "text/html"}:
        valid = b"\x00" not in contents
        if valid:
            try:
                contents.decode("utf-8")
            except UnicodeDecodeError:
                valid = False
    if not valid:
        raise ValueError(f"File contents do not match the declared {expected} file type")
    return expected


async def read_upload_contents(upload) -> bytes:
    """Read at most the configured upload limit and report client read errors."""
    limit = max_file_size()
    try:
        contents = await upload.read(limit + 1)
    except Exception as exc:
        logger.exception("Upload read failed")
        raise HTTPException(status_code=400, detail="Unable to read uploaded file") from exc
    if len(contents) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {get_settings().MAX_UPLOAD_SIZE_MB} MB limit",
        )
    return contents


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract PDF text in layout order using pdfminer.six."""
    return extract_pdf_text_with_layout(file_bytes)[0]


def _walk_pdf_text_lines(element):
    from pdfminer.layout import LTContainer, LTTextLine

    if isinstance(element, LTTextLine):
        yield element
    elif isinstance(element, LTContainer):
        for child in element:
            yield from _walk_pdf_text_lines(child)


def extract_pdf_text_with_layout(file_bytes: bytes) -> tuple[str, dict]:
    """Extract PDF text and a source offset/bounding box map for each text line."""
    if len(file_bytes) > max_file_size():
        raise ValueError(f"File size exceeds {get_settings().MAX_UPLOAD_SIZE_MB} MB limit")
    try:
        from pdfminer.high_level import extract_pages

        text_parts: list[str] = []
        page_layouts = []
        regions = []
        offset = 0
        for page_number, page in enumerate(extract_pages(io.BytesIO(file_bytes)), 1):
            if page_number > 1:
                text_parts.append("\n\n")
                offset += 2
            page_layouts.append({
                "page": page_number,
                "width": float(page.width),
                "height": float(page.height),
            })
            lines = sorted(
                _walk_pdf_text_lines(page),
                key=lambda line: (-line.y1, line.x0),
            )
            visible_lines = [line for line in lines if line.get_text().strip()]
            for line_index, line in enumerate(visible_lines):
                line_text = line.get_text().strip()
                start = offset
                text_parts.append(line_text)
                offset += len(line_text)
                regions.append({
                    "page": page_number,
                    "start": start,
                    "end": offset,
                    "bbox": [float(line.x0), float(line.y0), float(line.x1), float(line.y1)],
                })
                if line_index < len(visible_lines) - 1:
                    text_parts.append("\n")
                    offset += 1
        return "".join(text_parts), {"pages": page_layouts, "regions": regions}
    except Exception as e:
        logger.exception("PDF extraction failed")
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    if len(file_bytes) > max_file_size():
        raise ValueError(f"File size exceeds {get_settings().MAX_UPLOAD_SIZE_MB} MB limit")
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        raise ValueError(f"Failed to extract text from DOCX: {e}")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from a file based on its extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".docx",):
        return extract_text_from_docx(file_bytes)
    elif ext in (".txt", ".md", ".html"):
        return file_bytes.decode("utf-8", errors="replace")
    elif ext in (".png", ".jpg", ".jpeg", ".svg"):
        mime_type = get_upload_mime_type(filename)
        from backend.app.pipeline.content_handlers import get_content_handler

        handler = get_content_handler(mime_type)
        if handler is None:
            raise ValueError(f"No content handler registered for {mime_type}")
        return handler.extract_content(file_bytes)[0]
    else:
        raise ValueError(f"Unsupported file type: {ext}")
