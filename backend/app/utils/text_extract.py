"""Text extraction from PDF and DOCX files."""
import io
import logging
from pathlib import Path
from fastapi import HTTPException

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

def max_file_size() -> int:
    return get_settings().MAX_UPLOAD_SIZE_MB * 1024 * 1024


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
    """Extract text from PDF bytes using pdfplumber."""
    if len(file_bytes) > max_file_size():
        raise ValueError(f"File size exceeds {get_settings().MAX_UPLOAD_SIZE_MB} MB limit")
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
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
    else:
        raise ValueError(f"Unsupported file type: {ext}")
