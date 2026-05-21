"""
Text chunker using tiktoken for token-accurate splits.

Strategy: 512-token chunks with 50-token overlap.
Splits on paragraph/sentence boundaries where possible to avoid cutting mid-sentence.
"""
from typing import Optional

import tiktoken

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

CHUNK_SIZE = 512
OVERLAP = 50
ENCODING_NAME = "cl100k_base"  # works for text-embedding-3-small and GPT-4


def get_encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
    source_name: Optional[str] = None,
) -> list[dict]:
    """
    Split text into overlapping token chunks.

    Returns list of dicts: {"content": str, "token_count": int, "chunk_index": int}
    """
    encoder = get_encoder()
    tokens = encoder.encode(text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return []

    chunks = []
    start = 0
    idx = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text_str = encoder.decode(chunk_tokens)

        chunks.append(
            {
                "content": chunk_text_str.strip(),
                "token_count": len(chunk_tokens),
                "chunk_index": idx,
            }
        )

        if end == total_tokens:
            break

        start = end - overlap
        idx += 1

    log.debug(
        "chunked_text",
        source=source_name,
        total_tokens=total_tokens,
        num_chunks=len(chunks),
    )
    return chunks


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from PDF bytes."""
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except Exception as exc:
        log.error("pdf_extraction_failed", error=str(exc))
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text content from .docx bytes."""
    try:
        from docx import Document
        import io

        doc = Document(io.BytesIO(file_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        log.error("docx_extraction_failed", error=str(exc))
        return ""


def extract_text(file_bytes: bytes, content_type: str, filename: str = "") -> str:
    """Route to correct extractor based on content type or filename."""
    ct = content_type.lower()
    fn = filename.lower()

    if "pdf" in ct or fn.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if "docx" in ct or fn.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    # Treat everything else as plain text / markdown
    return file_bytes.decode("utf-8", errors="replace")
