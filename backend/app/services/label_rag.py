from __future__ import annotations

from typing import Any, Dict, List

from sqlmodel import Session, select

from backend.app.clients.vector import pseudo_embedding, query_label_vectors, upsert_label_vectors
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
        vec = pseudo_embedding(text)
        vectors.append(
            {
                "id": f"label-event-{ev.id}",
                "values": vec,
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
        vec = pseudo_embedding(text)
        vectors.append(
            {
                "id": f"label-warning-{w.id}",
                "values": vec,
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


def retrieve_label_for_alert(extraction_summary: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Given a short text summarizing the alert (e.g. AE name + key details),
    return top-k label chunks from Pinecone with their metadata.
    """
    q_vec = pseudo_embedding(extraction_summary)
    res = query_label_vectors(q_vec, top_k=top_k)
    return res.matches if hasattr(res, "matches") else []


