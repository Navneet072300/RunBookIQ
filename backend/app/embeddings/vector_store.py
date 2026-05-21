"""
pgvector store: upsert chunks and perform similarity search using HNSW index.
"""
import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.runbook_chunk import RunbookChunk

settings = get_settings()
log = get_logger(__name__)


async def upsert_chunks(
    session: AsyncSession,
    *,
    runbook_id: uuid.UUID,
    tenant_id: str,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> int:
    """
    Delete existing chunks for the runbook and insert fresh ones.
    Returns the number of chunks inserted.
    """
    # Remove old chunks for this runbook
    await session.execute(
        delete(RunbookChunk).where(RunbookChunk.runbook_id == runbook_id)
    )

    # Bulk insert new chunks
    new_chunks = []
    for chunk, embedding in zip(chunks, embeddings):
        new_chunks.append(
            RunbookChunk(
                tenant_id=tenant_id,
                runbook_id=runbook_id,
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                token_count=chunk["token_count"],
                embedding=embedding,
            )
        )

    session.add_all(new_chunks)
    await session.flush()

    log.info(
        "chunks_upserted",
        runbook_id=str(runbook_id),
        count=len(new_chunks),
    )
    return len(new_chunks)


async def similarity_search(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    tenant_id: str,
    top_k: int = 5,
    runbook_ids: list[uuid.UUID] | None = None,
) -> list[dict[str, Any]]:
    """
    Find the top_k most similar chunks using cosine distance.
    Returns list of dicts: {chunk_id, runbook_id, content, score, chunk_index}
    """
    # Use pgvector cosine distance operator <=>
    distance_expr = RunbookChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            RunbookChunk.id,
            RunbookChunk.runbook_id,
            RunbookChunk.chunk_index,
            RunbookChunk.content,
            RunbookChunk.token_count,
            distance_expr.label("distance"),
        )
        .where(RunbookChunk.tenant_id == tenant_id)
        .where(RunbookChunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    if runbook_ids:
        stmt = stmt.where(RunbookChunk.runbook_id.in_(runbook_ids))

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "chunk_id": str(row.id),
            "runbook_id": str(row.runbook_id),
            "chunk_index": row.chunk_index,
            "content": row.content,
            "token_count": row.token_count,
            "score": float(1.0 - row.distance),  # cosine similarity
        }
        for row in rows
    ]
