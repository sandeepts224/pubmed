from __future__ import annotations

from typing import Any, Dict, List, Optional

from pinecone import Pinecone

from backend.app.core.settings import settings


def get_pinecone_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("pinecone_api_key is not configured")
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index)


def pseudo_embedding(text: str, dim: int = 1024) -> List[float]:
    """
    Deterministic stand-in for real embeddings.

    For production, replace this with a proper embedding model
    (e.g. Claude or OpenAI embeddings) and keep dim consistent
    with the Pinecone index.
    """
    import hashlib

    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = []
    for i in range(dim):
        b = h[i % len(h)]
        # Map byte 0-255 to -1.0..1.0
        vals.append((b / 127.5) - 1.0)
    return vals


def upsert_label_vectors(vectors: List[Dict[str, Any]]) -> None:
    index = get_pinecone_index()
    index.upsert(vectors=vectors)


def query_label_vectors(query_vector: List[float], top_k: int = 5, filter_meta: Optional[Dict[str, Any]] = None):
    index = get_pinecone_index()
    return index.query(vector=query_vector, top_k=top_k, filter=filter_meta or {}, include_metadata=True)


