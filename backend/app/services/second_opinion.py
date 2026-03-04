from __future__ import annotations

from typing import Any, Dict, List

from sqlmodel import Session, select

from backend.app.clients.llm import ClaudeClient
from backend.app.core.settings import settings
from backend.app.models.alert import Alert
from backend.app.models.extraction import Extraction
from backend.app.models.paper import Paper
from backend.app.models.score import Score
from backend.app.services.label_rag import retrieve_label_for_alert


def _build_second_opinion_prompt(paper: Paper, extraction: Extraction, label_chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    parts.append("You are a regulatory pharmacovigilance expert.")
    parts.append(
        "Given an abstract about pembrolizumab (Keytruda), an extracted adverse event summary, "
        "and snippets from the FDA label, explain whether the paper reports something "
        "new, contradictory, or within what the label already describes."
    )

    parts.append("\nABSTRACT:")
    if paper.title:
        parts.append(f"Title: {paper.title}")
    if paper.journal:
        parts.append(f"Journal: {paper.journal}")
    if paper.abstract:
        parts.append(paper.abstract)

    parts.append("\nEXTRACTED SUMMARY:")
    parts.append(
        f"Adverse event: {extraction.adverse_event or extraction.meddra_term}\n"
        f"Incidence: {extraction.incidence_pct}\n"
        f"Sample size: {extraction.sample_size}\n"
        f"Study type: {extraction.study_type}\n"
        f"Subgroup risk: {extraction.subgroup_risk}\n"
        f"Combination: {extraction.combination}\n"
    )

    parts.append("\nRELEVANT LABEL SECTIONS:")
    for i, m in enumerate(label_chunks, start=1):
        meta = m.get("metadata", {})
        text = meta.get("text") or ""
        section = meta.get("section") or meta.get("section_title") or ""
        parts.append(f"[Label chunk {i} - {section}]\n{text}\n")

    parts.append(
        "\nTASK:\n"
        "1. In 3-4 sentences, say whether the paper reports a finding that is NEW, "
        "EXTENDS the label, CONTRADICTS the label, or is WITHIN the label.\n"
        "2. Briefly justify your judgment using both the abstract and label snippets.\n"
        "3. At the end, output a single word classification in all caps on its own line: "
        "NEW / EXTENDS / CONTRADICTS / WITHIN.\n"
    )
    return "\n".join(parts)


def _second_opinion_for_score(session: Session, score: Score) -> Dict[str, Any]:
    """
    Internal helper: given a Score, load its Extraction + Paper, retrieve
    relevant label chunks, and call Claude for a second opinion.
    """
    extraction = session.exec(select(Extraction).where(Extraction.id == score.extraction_id)).first()
    if not extraction:
        raise ValueError("Extraction not found for score")

    paper = session.exec(select(Paper).where(Paper.id == extraction.paper_id)).first()
    if not paper:
        raise ValueError("Paper not found for score")

    summary = f"{extraction.adverse_event or extraction.meddra_term} in {paper.journal} (PMID {paper.pmid})"
    matches = retrieve_label_for_alert(summary, top_k=4)

    client = ClaudeClient()
    prompt = _build_second_opinion_prompt(paper, extraction, matches)
    resp = client.create_message(
        model=settings.claude_reasoning_model,
        system="You are a careful pharmacovigilance reviewer.",
        user=prompt,
        max_tokens=600,
    )
    text = ClaudeClient.message_text_content(resp)

    return {
        "label_chunks": [m.get("metadata", {}) for m in matches],
        "claude_explanation": text,
    }


def get_second_opinion(session: Session, alert_id: int) -> Dict[str, Any]:
    """
    Compute a second opinion on demand for a given alert.
    """
    alert = session.exec(select(Alert).where(Alert.id == alert_id)).first()
    if not alert:
        raise ValueError("Alert not found")

    score = session.exec(select(Score).where(Score.id == alert.score_id)).first()
    if not score:
        raise ValueError("Score not found for alert")

    return _second_opinion_for_score(session=session, score=score)


def get_second_opinion_for_score(session: Session, score_id: int) -> Dict[str, Any]:
    """
    Compute a second opinion for a given score (used for scored papers
    that did not necessarily become alerts).
    """
    score = session.exec(select(Score).where(Score.id == score_id)).first()
    if not score:
        raise ValueError("Score not found")

    return _second_opinion_for_score(session=session, score=score)


