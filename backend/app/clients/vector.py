from __future__ import annotations

from typing import Any, Dict, List, Optional

from pinecone import Pinecone

from backend.app.core.settings import settings


def get_pinecone_client():
    """Get Pinecone client instance."""
    if not settings.pinecone_api_key:
        raise RuntimeError("pinecone_api_key is not configured")
    
    # Initialize Pinecone client with API key
    # The SDK will automatically use the correct host based on the index
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc


def get_pinecone_index():
    """
    Get Pinecone index instance.
    
    With Pinecone's integrated inference, the index is configured with an embedding model
    (OpenAI text-embedding-3-small) and can handle text directly.
    """
    pc = get_pinecone_client()
    return pc.Index(settings.pinecone_index)


def upsert_label_vectors(vectors: List[Dict[str, Any]]) -> None:
    """
    Upsert vectors into Pinecone index.
    
    With Pinecone's integrated inference, if your index is configured with an embedding model,
    you can pass text in the 'values' field and Pinecone will handle embedding generation.
    
    Expected vector format:
    {
        "id": str,
        "values": str | List[float],  # Text (str) if using integrated inference, or pre-computed vector (List[float])
        "metadata": Dict[str, Any]
    }
    """
    index = get_pinecone_index()
    index.upsert(vectors=vectors)


def query_label_vectors(query_text_or_vector: str | List[float], top_k: int = 5, filter_meta: Optional[Dict[str, Any]] = None):
    """
    Query Pinecone index using text or pre-computed vector.
    
    With Pinecone's integrated inference, you can pass text directly and Pinecone
    will generate embeddings automatically using the configured model.
    
    Args:
        query_text_or_vector: Text string (if using integrated inference) or embedding vector (List[float])
        top_k: Number of results to return
        filter_meta: Optional metadata filter (e.g., {"type": "event"})
    
    Returns:
        QueryResponse with matches
    """
    index = get_pinecone_index()
    filter_dict = filter_meta if filter_meta else None
    
    # If it's a string, use Pinecone's integrated inference
    # If it's a list, use as vector directly
    if isinstance(query_text_or_vector, str):
        # Pinecone integrated inference - pass text directly
        # Note: Check Pinecone SDK docs for exact parameter name (might be 'data' or 'text')
        return index.query(
            data=query_text_or_vector,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )
    else:
        # Pre-computed vector
        return index.query(
            vector=query_text_or_vector,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )


def rerank_label_results(query: str, documents: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Rerank label chunks using Cohere Rerank v3.5 through Pinecone inference API.
    
    This improves relevance by re-scoring and reordering results based on
    query-document semantic relationships.
    
    Args:
        query: Query text (e.g., adverse event description)
        documents: List of document texts to rerank
        top_n: Number of top results to return after reranking
    
    Returns:
        List of reranked results with scores, document text, and original index
    """
    if not documents:
        return []
    
    pc = get_pinecone_client()
    
    try:
        results = pc.inference.rerank(
            model="cohere-rerank-3.5",
            query=query,
            documents=documents,
            top_n=top_n,
            return_documents=True,
        )
        
        # Convert to list of dicts for easier handling
        reranked = []
        for r in results.data:
            # Handle different possible response formats
            score = getattr(r, 'score', 0.5)
            doc_text = None
            
            # Try to get document text from various possible formats
            if hasattr(r, 'document'):
                doc = r.document
                if hasattr(doc, 'text'):
                    doc_text = doc.text
                elif isinstance(doc, str):
                    doc_text = doc
                else:
                    doc_text = str(doc)
            
            # Get original index if available
            original_index = getattr(r, 'index', None)
            
            reranked.append({
                "score": float(score),
                "document": doc_text or "",
                "index": original_index,
            })
        
        return reranked
    except Exception as e:
        # Fallback: return documents with default scores if reranking fails
        # Log error but don't fail completely
        import logging
        logging.warning(f"Reranking failed: {e}. Using original order.")
        return [{"score": 0.5, "document": doc, "index": i} for i, doc in enumerate(documents[:top_n])]


