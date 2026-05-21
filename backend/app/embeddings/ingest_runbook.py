"""
CLI entrypoint for indexing a runbook file or URL.

Usage:
  python -m app.embeddings.ingest_runbook --file path/to/runbook.md --name "My Runbook"
  python -m app.embeddings.ingest_runbook --url https://... --name "Remote Runbook"
"""
import asyncio
import sys
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging, get_logger
from app.embeddings.chunker import chunk_text, extract_text
from app.embeddings.embedder import embed_texts
from app.embeddings.vector_store import upsert_chunks
from app.models.runbook import Runbook

settings = get_settings()
configure_logging()
log = get_logger(__name__)


async def ingest_file(
    *,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    name: str,
    tenant_id: str = settings.default_tenant_id,
    description: Optional[str] = None,
) -> uuid.UUID:
    """Ingest a runbook from a file path or URL into pgvector."""
    if not file_path and not url:
        raise ValueError("Either file_path or url must be provided")

    # Fetch content
    if file_path:
        path = Path(file_path)
        file_bytes = path.read_bytes()
        content_type = _guess_content_type(path.suffix)
        source_url = None
        storage_path = str(path.absolute())
    else:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            file_bytes = resp.content
            content_type = resp.headers.get("content-type", "text/plain")
            source_url = url
            storage_path = None

    raw_text = extract_text(file_bytes, content_type, file_path or url or "")
    if not raw_text.strip():
        raise ValueError("No text content extracted from runbook")

    chunks = chunk_text(raw_text, source_name=name)
    if not chunks:
        raise ValueError("Chunking produced no chunks")

    chunk_texts = [c["content"] for c in chunks]
    log.info("embedding_runbook", name=name, num_chunks=len(chunks))
    embeddings = await embed_texts(chunk_texts)

    async with AsyncSessionLocal() as session:
        # Upsert Runbook metadata
        existing = await session.execute(
            select(Runbook).where(
                Runbook.tenant_id == tenant_id,
                Runbook.name == name,
            )
        )
        runbook = existing.scalar_one_or_none()

        if runbook is None:
            runbook = Runbook(
                tenant_id=tenant_id,
                name=name,
                description=description,
                source_url=source_url,
                file_path=storage_path,
                content_type=content_type.split(";")[0].strip(),
            )
            session.add(runbook)
            await session.flush()
        else:
            runbook.source_url = source_url
            runbook.file_path = storage_path

        count = await upsert_chunks(
            session,
            runbook_id=runbook.id,
            tenant_id=tenant_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        runbook.chunk_count = count
        runbook.last_indexed_at = datetime.now(tz=timezone.utc)
        await session.commit()

    log.info("runbook_indexed", runbook_id=str(runbook.id), chunks=count, name=name)
    return runbook.id


def _guess_content_type(suffix: str) -> str:
    mapping = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    return mapping.get(suffix.lower(), "text/plain")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest a runbook into RunbookIQ")
    parser.add_argument("--file", help="Path to local runbook file")
    parser.add_argument("--url", help="URL of remote runbook")
    parser.add_argument("--name", required=True, help="Runbook name")
    parser.add_argument("--description", help="Optional description")
    parser.add_argument(
        "--tenant-id",
        default=settings.default_tenant_id,
        help="Tenant ID",
    )
    args = parser.parse_args()

    runbook_id = asyncio.run(
        ingest_file(
            file_path=args.file,
            url=args.url,
            name=args.name,
            tenant_id=args.tenant_id,
            description=args.description,
        )
    )
    print(f"Runbook indexed: {runbook_id}")
