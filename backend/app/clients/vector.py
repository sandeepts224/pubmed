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
    
    For text queries, generates embeddings first (Pinecone standard API requires vectors).
    If Pinecone integrated inference is available, it may support text directly.
    
    Args:
        query_text_or_vector: Text string or embedding vector (List[float])
        top_k: Number of results to return
        filter_meta: Optional metadata filter (e.g., {"type": "event"})
    
    Returns:
        QueryResponse with matches
    """
    index = get_pinecone_index()
    filter_dict = filter_meta if filter_meta else None
    
    # If it's a string, generate embedding first
    # Note: Pinecone standard API requires vectors, not text
    if isinstance(query_text_or_vector, str):
        # Try Pinecone integrated inference first (if supported)
        try:
            # Some Pinecone setups might support text queries directly
            # Try different parameter names
            try:
                return index.query(
                    data=query_text_or_vector,
                    top_k=top_k,
                    filter=filter_dict,
                    include_metadata=True
                )
            except (TypeError, AttributeError):
                # If 'data' doesn't work, try generating embedding
                from backend.app.clients.embeddings import embed_text
                query_vector = embed_text(query_text_or_vector)
                return index.query(
                    vector=query_vector,
                    top_k=top_k,
                    filter=filter_dict,
                    include_metadata=True
                )
        except ImportError:
            # If embeddings client not available, fall back to vector query
            raise RuntimeError("Cannot query with text: embeddings client not available")
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
        # Check if it's a permission error
        error_str = str(e)
        if "PERMISSION_DENIED" in error_str or "not authorized" in error_str.lower():
            # Permission denied - rerank model not available for this project
            # Fallback: use original order with similarity-based scores
            import logging
            logging.warning(
                "Cohere Rerank v3.5 not authorized for this Pinecone project. "
                "Using original order with default scores. "
                "To enable reranking, contact Pinecone support or check your project settings."
            )
            # Return documents in original order with default scores
            # This allows the system to work without reranking
            return [{"score": 0.5, "document": doc, "index": i} for i, doc in enumerate(documents[:top_n])]
        else:
            # Other error - log and fallback
            import logging
            logging.warning(f"Reranking failed: {e}. Using original order.")
            return [{"score": 0.5, "document": doc, "index": i} for i, doc in enumerate(documents[:top_n])]


