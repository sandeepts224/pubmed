from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from backend.app.models.alert import Alert
from backend.app.models.extraction import Extraction
from backend.app.models.label import LabelDrugInteraction, LabelEvent, LabelVersion
from backend.app.models.paper import Paper
from backend.app.models.score import Score
from backend.app.services.label_rag import retrieve_label_for_alert


ALERT_THRESHOLD = 50.0


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_rwe(study_type: str | None) -> bool:
    st = _norm(study_type)
    return any(k in st for k in ["retrospective", "observational", "registry", "claims", "ehr", "real-world", "realworld"])


def _latest_label_version(session: Session, drug: str = "pembrolizumab") -> LabelVersion | None:
    return session.exec(
        select(LabelVersion).where(LabelVersion.drug == drug).order_by(LabelVersion.label_revision_date.desc())
    ).first()


def _label_terms(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelEvent.meddra_preferred_term).where(LabelEvent.label_version_id == label_version_id)
    ).all()
    return {_norm(r) for r in rows if r}


def _label_event_by_term(session: Session, label_version_id: int, term: str) -> LabelEvent | None:
    # Best-effort: case-insensitive match by normalized term.
    t = _norm(term)
    events = session.exec(
        select(LabelEvent).where(
            LabelEvent.label_version_id == label_version_id,
            LabelEvent.meddra_preferred_term.is_not(None),
        )
    ).all()
    for ev in events:
        if _norm(ev.meddra_preferred_term) == t:
            return ev
    return None


def _label_special_populations(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelEvent.special_populations_json).where(LabelEvent.label_version_id == label_version_id)
    ).all()
    out: set[str] = set()
    for r in rows:
        if not r:
            continue
        try:
            items = json.loads(r)
            for x in items or []:
                if isinstance(x, str) and x.strip():
                    out.add(_norm(x))
        except Exception:
            continue
    return out


def _label_interactions(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelDrugInteraction.description).where(LabelDrugInteraction.label_version_id == label_version_id)
    ).all()
    return {_norm(r) for r in rows if r}


def _calculate_rag_score(extraction: Extraction, paper: Paper | None = None) -> tuple[float, dict[str, object]]:
    """
    Calculate RAG-based score using semantic similarity to label chunks.
    
    Uses Pinecone to retrieve relevant label sections and calculates a score based on:
    - Semantic similarity (distance/similarity scores from Pinecone)
    - Number of relevant matches
    - Relevance of matched sections
    
    Returns:
        Tuple of (rag_score, details_dict)
    """
    rag_details: dict[str, object] = {}
    
    # Build query text from extraction
    query_parts = []
    if extraction.adverse_event:
        query_parts.append(extraction.adverse_event)
    if extraction.meddra_term and extraction.meddra_term != extraction.adverse_event:
        query_parts.append(extraction.meddra_term)
    if extraction.subgroup_risk:
        query_parts.append(f"subgroup: {extraction.subgroup_risk}")
    if extraction.combination:
        query_parts.append(f"combination: {extraction.combination}")
    
    if not query_parts:
        rag_details["skipped"] = True
        rag_details["reason"] = "no_extraction_data"
        return 0.0, rag_details
    
    query_text = " ".join(query_parts)
    
    # Retrieve relevant label chunks using RAG with reranking
    try:
        # Use reranking for improved relevance (default: True)
        matches = retrieve_label_for_alert(query_text, top_k=5, use_rerank=True)
        
        if not matches:
            rag_details["skipped"] = True
            rag_details["reason"] = "no_rag_matches"
            return 0.0, rag_details
        
        # Calculate RAG score based on reranked scores
        # Cohere Rerank returns relevance scores (higher = more relevant)
        # Scores are typically in 0-1 range, but can be higher
        rerank_scores = []
        match_types = []
        
        for match in matches:
            # Get reranked relevance score (Cohere Rerank score)
            score = getattr(match, 'score', 0.0)
            rerank_scores.append(score)
            
            # Track match types for analysis
            metadata = getattr(match, 'metadata', {}) or {}
            match_type = metadata.get('type', 'unknown')
            match_types.append(match_type)
        
        # Calculate RAG score based on reranked relevance:
        # - Cohere Rerank scores: higher = more relevant to query
        # - High relevance (> 0.8) = well-documented on label = low novelty = low score
        # - Medium relevance (0.5-0.8) = somewhat related = moderate score
        # - Low relevance (< 0.5) = not well-documented = high novelty = high score
        top_relevance = max(rerank_scores) if rerank_scores else 0.0
        
        # Convert rerank relevance to novelty score
        # Rerank scores are typically 0-1, but can be higher for very relevant matches
        # Normalize to 0-1 range for scoring logic
        normalized_relevance = min(1.0, top_relevance)
        
        if normalized_relevance < 0.3:
            # Very low relevance - not well-documented on label = high novelty
            rag_score = 40.0
        elif normalized_relevance < 0.5:
            # Low relevance - somewhat novel
            rag_score = 25.0
        elif normalized_relevance < 0.7:
            # Medium relevance - related but different
            rag_score = 10.0
        else:
            # High relevance - well-documented on label = low novelty
            rag_score = 0.0
        
        # Penalty for multiple high-relevance matches (indicates well-documented)
        high_relevance_matches = sum(1 for s in rerank_scores if s > 0.7)
        if high_relevance_matches >= 3:
            # Multiple strong matches suggest this is well-documented, reduce novelty
            rag_score = max(0.0, rag_score - 10.0)
        
        rag_details["top_rerank_score"] = top_relevance
        rag_details["normalized_relevance"] = normalized_relevance
        rag_details["num_matches"] = len(matches)
        rag_details["high_relevance_matches"] = high_relevance_matches
        rag_details["match_types"] = match_types
        rag_details["query_text"] = query_text
        rag_details["used_rerank"] = True
        
        return rag_score, rag_details
        
    except Exception as e:
        rag_details["error"] = str(e)
        rag_details["skipped"] = True
        return 0.0, rag_details


@dataclass(frozen=True)
class ScoreResult:
    score: Score
    alert_created: bool


def score_extraction(session: Session, extraction: Extraction, label_version_id: int) -> ScoreResult:
    details: dict[str, object] = {"checks": {}, "label_version_id": label_version_id}

    # Get paper for RAG scoring context
    paper = session.exec(select(Paper).where(Paper.id == extraction.paper_id)).first()

    term = extraction.meddra_term or extraction.adverse_event or ""
    on_label = _norm(term) in _label_terms(session, label_version_id)

    # Check 1: novelty
    novelty = 0.0
    if not on_label and term.strip():
        novelty = 25.0
        st = _norm(extraction.study_type)
        if extraction.authors_claim_novel and ("case" in st or (extraction.sample_size is not None and extraction.sample_size <= 10)):
            novelty = 35.0
    details["checks"]["novelty"] = {"on_label": on_label, "term": term, "score": novelty}

    # Check 2: incidence delta
    incidence_delta = 0.0
    if on_label and extraction.incidence_pct is not None:
        label_ev = _label_event_by_term(session, label_version_id, term)
        labeled = None
        if label_ev is not None:
            if label_ev.incidence_pct is not None:
                labeled = float(label_ev.incidence_pct)
            elif label_ev.incidence_note and "<" in label_ev.incidence_note:
                # Treat "<1%" as a conservative upper bound of 1.0
                labeled = 1.0
        if labeled and labeled > 0:
            ratio = float(extraction.incidence_pct) / labeled
            threshold = 2.5 if _is_rwe(extraction.study_type) else 2.0
            if ratio >= threshold:
                # Simple proportional score capped at 30
                incidence_delta = min(30.0, 10.0 * (ratio - threshold + 1.0))
            details["checks"]["incidence_delta"] = {
                "paper_incidence_pct": extraction.incidence_pct,
                "label_incidence_pct": labeled,
                "ratio": ratio,
                "threshold": threshold,
                "score": incidence_delta,
            }
        else:
            details["checks"]["incidence_delta"] = {"skipped": True, "reason": "no_labeled_baseline"}
    else:
        details["checks"]["incidence_delta"] = {"skipped": True, "reason": "not_on_label_or_no_paper_incidence"}

    # Check 3: subpopulation
    subpop = 0.0
    if extraction.subgroup_risk and extraction.subgroup_risk.strip():
        label_subpops = _label_special_populations(session, label_version_id)
        if _norm(extraction.subgroup_risk) not in label_subpops:
            subpop = 15.0
        details["checks"]["subpopulation"] = {
            "paper_subgroup_risk": extraction.subgroup_risk,
            "score": subpop,
        }
    else:
        details["checks"]["subpopulation"] = {"skipped": True}

    # Check 4: temporal
    temporal = 0.0
    if on_label and extraction.time_to_onset_days is not None:
        label_ev = _label_event_by_term(session, label_version_id, term)
        if label_ev and label_ev.median_onset_months:
            label_days = float(label_ev.median_onset_months) * 30.0
            if label_days > 0:
                ratio = float(extraction.time_to_onset_days) / label_days
                if ratio >= 1.5 or ratio <= (1.0 / 1.5):
                    temporal = 10.0
                details["checks"]["temporal"] = {
                    "paper_days": extraction.time_to_onset_days,
                    "label_days_est": label_days,
                    "ratio": ratio,
                    "score": temporal,
                }
        else:
            details["checks"]["temporal"] = {"skipped": True, "reason": "no_label_median_onset"}
    else:
        details["checks"]["temporal"] = {"skipped": True, "reason": "not_on_label_or_no_paper_onset"}

    # Check 5: combination
    combo_score = 0.0
    if extraction.combination and extraction.combination.strip():
        interactions = _label_interactions(session, label_version_id)
        # Best-effort: if any interaction string contains the combination text or vice versa.
        c = _norm(extraction.combination)
        found = any(c in x or x in c for x in interactions)
        if not found:
            combo_score = 10.0
        details["checks"]["combination"] = {"paper_combination": extraction.combination, "on_label": found, "score": combo_score}
    else:
        details["checks"]["combination"] = {"skipped": True}

    # Check 6: RAG-based semantic similarity score
    rag_score, rag_details = _calculate_rag_score(extraction, paper)
    details["checks"]["rag"] = rag_details

    # Evidence multiplier (simple v1)
    mult = 1.0
    st = _norm(extraction.study_type)
    if "retrospective" in st:
        mult *= 1.5
    elif "registry" in st:
        mult *= 1.4
    elif "case" in st:
        mult *= 1.0

    if extraction.sample_size is not None:
        if extraction.sample_size >= 2000:
            mult *= 1.3
        elif extraction.sample_size >= 500:
            mult *= 1.2

    # Combine DB query scores and RAG score
    # RAG score is already in the same scale (0-50), so we can add it directly
    base_sum = novelty + incidence_delta + subpop + temporal + combo_score + rag_score
    composite = base_sum * mult

    score = Score(
        extraction_id=extraction.id,
        novelty_score=novelty,
        incidence_delta_score=incidence_delta,
        subpopulation_score=subpop,
        temporal_score=temporal,
        combination_score=combo_score,
        rag_score=rag_score,
        evidence_multiplier=mult,
        composite_score=composite,
        scoring_version="v2",  # Updated to v2 with RAG scoring
        details_json=json.dumps(details),
    )
    session.add(score)
    session.commit()
    session.refresh(score)

    alert_created = False
    if composite >= ALERT_THRESHOLD:
        session.add(Alert(score_id=score.id, status="pending_review"))
        session.commit()
        alert_created = True

    return ScoreResult(score=score, alert_created=alert_created)


def score_all_unscored(session: Session, drug: str = "pembrolizumab") -> dict[str, int]:
    lv = _latest_label_version(session, drug=drug)
    if not lv:
        return {"scored": 0, "alerts_created": 0}

    # Find extractions that do not have a score yet
    extractions = session.exec(select(Extraction)).all()
    existing_scores = set(session.exec(select(Score.extraction_id)).all())

    scored = 0
    alerts = 0
    for ex in extractions:
        if ex.id in existing_scores:
            continue
        res = score_extraction(session=session, extraction=ex, label_version_id=lv.id)
        scored += 1
        alerts += 1 if res.alert_created else 0

    return {"scored": scored, "alerts_created": alerts}


