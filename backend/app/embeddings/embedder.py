"""
Embedder: calls Google Gemini text-embedding-004 via the native REST API.
(The OpenAI-compat endpoint does not support embedding models.)

Native batch endpoint:
  POST https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key=KEY
"""
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:batchEmbedContents"
)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using text-embedding-004 (768 dims).
    Uses the native Gemini batchEmbedContents endpoint.
    """
    if not texts:
        return []

    url = _EMBED_URL.format(model=settings.embedding_model)
    batch_size = settings.embedding_batch_size
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            requests_payload = [
                {
                    "model": f"models/{settings.embedding_model}",
                    "content": {"parts": [{"text": t.replace("\n", " ")}]},
                }
                for t in batch
            ]

            log.debug("embedding_batch", batch_num=i // batch_size, size=len(batch))
            resp = await client.post(
                url,
                params={"key": settings.gemini_api_key},
                json={"requests": requests_payload},
            )
            resp.raise_for_status()
            data = resp.json()
            batch_embeddings = [e["values"] for e in data["embeddings"]]
            all_embeddings.extend(batch_embeddings)

    return all_embeddings


async def embed_single(text: str) -> list[float]:
    embeddings = await embed_texts([text])
    return embeddings[0] if embeddings else []
