from __future__ import annotations

from typing import Any, Dict, List

from sqlmodel import Session, select

from backend.app.clients.vector import query_label_vectors, rerank_label_results, upsert_label_vectors
from backend.app.models.label import LabelEvent, LabelVersion, WarningPrecaution


def _latest_label_version(session: Session, drug: str = "pembrolizumab") -> LabelVersion | None:
    return session.exec(
        select(LabelVersion).where(LabelVersion.drug == drug).order_by(LabelVersion.label_revision_date.desc())
    ).first()


def _chunk_text_for_event(ev: LabelEvent, label_version: LabelVersion) -> str:
    parts: List[str] = []
    parts.append(f"Drug: {label_version.brand_name} ({label_version.drug})")
    if ev.meddra_preferred_term:
        parts.append(f"Adverse event (MedDRA PT): {ev.meddra_preferred_term}")
    parts.append(f"Label section: {ev.label_section or 'N/A'}")
    parts.append(f"Category: {ev.category}")
    parts.append(f"Incidence: {ev.incidence_pct if ev.incidence_pct is not None else ev.incidence_note or 'N/A'}")
    if ev.median_onset_months is not None:
        parts.append(f"Median time to onset (months): {ev.median_onset_months}")
    if ev.special_populations_json:
        parts.append(f"Special populations: {ev.special_populations_json}")
    if ev.combination_note:
        parts.append(f"Combination notes: {ev.combination_note}")
    return "\n".join(parts)


def _chunk_text_for_warning(w: WarningPrecaution, label_version: LabelVersion) -> str:
    return f"Drug: {label_version.brand_name} ({label_version.drug})\nSection {w.section}: {w.title}\n{w.summary}"


def index_label_into_pinecone(session: Session, drug: str = "pembrolizumab") -> Dict[str, Any]:
    lv = _latest_label_version(session, drug=drug)
    if not lv:
        return {"indexed": 0, "detail": "no_label_version"}

    events = session.exec(select(LabelEvent).where(LabelEvent.label_version_id == lv.id)).all()
    warnings = session.exec(select(WarningPrecaution).where(WarningPrecaution.label_version_id == lv.id)).all()

    vectors: List[Dict[str, Any]] = []

    for ev in events:
        text = _chunk_text_for_event(ev, lv)
        # With Pinecone integrated inference, pass text directly - Pinecone handles embedding
        vectors.append(
            {
                "id": f"label-event-{ev.id}",
                "values": text,  # Pass text directly - Pinecone will embed using configured model
                "metadata": {
                    "type": "event",
                    "label_version_id": lv.id,
                    "section": ev.label_section or "",
                    "meddra_pt": ev.meddra_preferred_term or "",
                    "category": ev.category,
                    "text": text,
                },
            }
        )

    for w in warnings:
        text = _chunk_text_for_warning(w, lv)
        # With Pinecone integrated inference, pass text directly - Pinecone handles embedding
        vectors.append(
            {
                "id": f"label-warning-{w.id}",
                "values": text,  # Pass text directly - Pinecone will embed using configured model
                "metadata": {
                    "type": "warning",
                    "label_version_id": lv.id,
                    "section": w.section,
                    "section_title": w.title,
                    "text": text,
                },
            }
        )

    if not vectors:
        return {"indexed": 0, "detail": "no_vectors"}

    upsert_label_vectors(vectors)
    return {"indexed": len(vectors), "label_version_id": lv.id}


def retrieve_label_for_alert(extraction_summary: str, top_k: int = 5, use_rerank: bool = True) -> List[Dict[str, Any]]:
    """
    Given a short text summarizing the alert (e.g. AE name + key details),
    return top-k label chunks from Pinecone with their metadata.
    
    Uses Pinecone's integrated inference - passes text directly, Pinecone handles embedding.
    Optionally uses Cohere Rerank v3.5 for improved relevance.
    
    Args:
        extraction_summary: Query text summarizing the alert
        top_k: Number of results to return
        use_rerank: Whether to use Cohere Rerank for improved relevance (default: True)
    
    Returns:
        List of matches with metadata and reranked scores
    """
    # First, retrieve more candidates than needed (for reranking)
    initial_k = top_k * 3 if use_rerank else top_k  # Get 3x candidates for reranking
    
    # Pass text directly - Pinecone will generate embedding using configured model
    res = query_label_vectors(extraction_summary, top_k=initial_k)
    matches = res.matches if hasattr(res, "matches") else []
    
    if not matches:
        return []
    
    # If not using rerank, return top_k results directly
    if not use_rerank:
        return matches[:top_k]
    
    # Extract document texts and metadata for reranking
    documents = []
    match_metadata = []
    for i, match in enumerate(matches):
        meta = getattr(match, 'metadata', {}) or {}
        doc_text = meta.get('text', '')
        if doc_text:
            documents.append(doc_text)
            match_metadata.append({
                'match': match,
                'metadata': meta,
                'original_index': i,  # Track original position
            })
    
    if not documents:
        return matches[:top_k]
    
    # Rerank using Cohere Rerank v3.5 through Pinecone
    reranked_results = rerank_label_results(extraction_summary, documents, top_n=top_k)
    
    # Map reranked results back to original matches with updated scores
    reranked_matches = []
    for reranked in reranked_results:
        doc_index = reranked.get('index')
        # Cohere Rerank returns the index in the original documents list
        if doc_index is not None and doc_index < len(match_metadata):
            # Get the original match and metadata
            original_data = match_metadata[doc_index]
            original_match = original_data['match']
            
            # Create a match-like object with reranked score
            # Use a simple class to mimic Pinecone's match structure
            class RerankedMatch:
                def __init__(self, score, metadata, id_val):
                    self.score = score
                    self.metadata = metadata
                    self.id = id_val
            
            reranked_match = RerankedMatch(
                score=reranked['score'],
                metadata=original_data['metadata'],
                id_val=getattr(original_match, 'id', None),
            )
            reranked_matches.append(reranked_match)
    
    # Return reranked matches, or fallback to original if reranking failed
    return reranked_matches if reranked_matches else matches[:top_k]


