"""
Retriever: converts a NormalisedAlert into a semantic query and
performs similarity search against the runbook vector store.
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.embeddings.embedder import embed_single
from app.embeddings.vector_store import similarity_search
from app.ingestion.normaliser import NormalisedAlert

settings = get_settings()
log = get_logger(__name__)


def build_retrieval_query(alert: NormalisedAlert) -> str:
    """
    Build a dense retrieval query string from an alert.
    Includes alert name, severity, description, and key labels.
    """
    parts = [
        f"Alert: {alert.alert_name}",
        f"Severity: {alert.severity.value}",
        f"Source: {alert.source.value}",
    ]
    if alert.namespace:
        parts.append(f"Namespace: {alert.namespace}")
    if alert.cluster:
        parts.append(f"Cluster: {alert.cluster}")
    if alert.description:
        parts.append(f"Description: {alert.description}")

    # Include important label values
    important_keys = {"job", "service", "app", "component", "pod", "node", "host"}
    for k, v in alert.labels.items():
        if k in important_keys and v:
            parts.append(f"{k}: {v}")

    return " | ".join(parts)


async def retrieve_relevant_chunks(
    session: AsyncSession,
    alert: NormalisedAlert,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Embed the alert query and retrieve the most relevant runbook chunks.
    Returns top_k chunks with similarity scores.
    """
    k = top_k or settings.rag_top_k
    query = build_retrieval_query(alert)

    log.info(
        "retrieval_query",
        alert_name=alert.alert_name,
        query_preview=query[:100],
    )

    query_embedding = await embed_single(query)
    chunks = await similarity_search(
        session,
        query_embedding=query_embedding,
        tenant_id=alert.tenant_id,
        top_k=k,
    )

    log.info(
        "retrieval_results",
        alert_name=alert.alert_name,
        num_chunks=len(chunks),
        top_score=chunks[0]["score"] if chunks else 0.0,
    )
    return chunks
