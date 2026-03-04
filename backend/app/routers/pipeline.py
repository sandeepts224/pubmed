from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.app.db import get_session
from backend.app.jobs.pubmed_ingest import ingest_pubmed_last_7d_backfill
from backend.app.models.alert import Alert
from backend.app.models.extraction import Extraction
from backend.app.models.paper import Paper
from backend.app.models.score import Score
from backend.app.schemas.extraction import AlertDecision, ExtractionCreate
from backend.app.services.backdate_alerts import backdate_alerts_to_last_7_days
from backend.app.services.extraction_job import run_extraction_for_unprocessed_papers
from backend.app.services.label_rag import index_label_into_pinecone
from backend.app.services.scoring import score_all_unscored
from backend.app.services.second_opinion import get_second_opinion, get_second_opinion_for_score

router = APIRouter(tags=["pipeline"])


@router.post("/papers/{paper_id}/extractions")
def create_extraction(paper_id: int, payload: ExtractionCreate, session: Session = Depends(get_session)):
    paper = session.exec(select(Paper).where(Paper.id == paper_id)).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    ex = Extraction(paper_id=paper_id, **payload.model_dump())
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


@router.post("/jobs/score")
def run_scoring(session: Session = Depends(get_session)):
    return score_all_unscored(session=session)


@router.post("/jobs/extract")
def run_extraction(limit: int = Query(10, ge=1, le=30), session: Session = Depends(get_session)):
    """
    Run Claude-based structured extraction for up to `limit` papers that do not yet have extractions.

    Requires CLAUDE_API_KEY to be configured in env.local / environment.
    """
    return run_extraction_for_unprocessed_papers(session=session, limit=limit)


@router.post("/jobs/index_label")
def run_label_indexing(session: Session = Depends(get_session)):
    """
    (Re)index the latest Keytruda label into Pinecone for RAG.
    """
    return index_label_into_pinecone(session=session)


@router.post("/jobs/full_backfill_7d")
def run_full_backfill_7d(
    extraction_batch_size: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    """
    Convenience job to simulate the full pipeline running for the last 7 days:

    1) PubMed 7-day backfill (7 consecutive 24h edat windows)
    2) Claude extraction for all papers without extractions (batched)
    3) Deterministic scoring for all unscored extractions, creating alerts

    This is primarily for demo/bootstrapping so that the dashboard has a realistic
    set of alerts spread over the last 7 days.
    """
    # 1) PubMed backfill
    pubmed_summary = ingest_pubmed_last_7d_backfill(session=session, days=7)

    # 2) Extraction in batches until there is nothing left to extract
    extraction_runs: list[dict[str, int]] = []
    while True:
        extracted = run_extraction_for_unprocessed_papers(session=session, limit=extraction_batch_size)
        extraction_runs.append(extracted)
        # Our extraction job returns {"processed": N, "created": M, ...}; stop when no papers processed.
        if not extracted.get("processed"):
            break

    # 3) Scoring for all unscored extractions
    scoring_summary = score_all_unscored(session=session)

    return {
        "pubmed_backfill": pubmed_summary,
        "extraction_batches": extraction_runs,
        "scoring": scoring_summary,
    }


@router.post("/jobs/backdate_alerts")
def backdate_alerts(session: Session = Depends(get_session)):
    """
    Backdate all existing alerts (and related papers/extractions/scores) to have
    created_at timestamps spread over the last 7 days, maintaining chronological order.

    This makes the dashboard look like the system has been running continuously.
    """
    return backdate_alerts_to_last_7_days(session=session)


@router.get("/alerts/{alert_id}/second_opinion")
def alert_second_opinion(alert_id: int, session: Session = Depends(get_session)):
    """
    Get a Claude-based natural language second opinion for an alert, using RAG over the label.
    """
    try:
        return get_second_opinion(session=session, alert_id=alert_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores/{score_id}/second_opinion")
def score_second_opinion(score_id: int, session: Session = Depends(get_session)):
    """
    Get a Claude-based natural language second opinion for a scored paper,
    even if it did not become an alert.
    """
    try:
        return get_second_opinion_for_score(session=session, score_id=score_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
def list_alerts(limit: int = 50, session: Session = Depends(get_session)):
    limit = max(1, min(limit, 200))
    alerts = session.exec(select(Alert).order_by(Alert.created_at.desc()).limit(limit)).all()
    return alerts


@router.get("/pipeline/last7d")
def pipeline_last7d(session: Session = Depends(get_session)):
    """
    List all papers from the last 7 days with their extraction, score,
    optional alert, and (if scored) a second opinion.

    This is used to drive the "pipeline view" dashboard, which shows
    processed papers even if they did not cross the alert threshold.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=7)

    rows = session.exec(
        select(Paper, Extraction, Score, Alert)
        .join(Extraction, Extraction.paper_id == Paper.id, isouter=True)
        .join(Score, Score.extraction_id == Extraction.id, isouter=True)
        .join(Alert, Alert.score_id == Score.id, isouter=True)
        .where(Paper.created_at >= cutoff)
        .order_by(Paper.created_at.desc())
    ).all()

    result = []
    with_extraction = 0
    with_score = 0
    with_alert = 0

    for paper, extraction, score, alert in rows:
        if extraction is not None:
            with_extraction += 1
        if score is not None:
            with_score += 1
        if alert is not None:
            with_alert += 1

        result.append(
            {
                "paper": paper,
                "extraction": extraction,
                "score": score,
                "alert": alert,
                # second_opinion is fetched on-demand via /pipeline/scores/{score_id}/second_opinion
            }
        )

    return {
        "papers": result,
        "total": len(result),
        "with_extraction": with_extraction,
        "with_score": with_score,
        "with_alert": with_alert,
    }


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, session: Session = Depends(get_session)):
    alert = session.exec(select(Alert).where(Alert.id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    score = session.exec(select(Score).where(Score.id == alert.score_id)).first()
    extraction = session.exec(select(Extraction).where(Extraction.id == score.extraction_id)).first() if score else None
    paper = session.exec(select(Paper).where(Paper.id == extraction.paper_id)).first() if extraction else None

    return {"alert": alert, "score": score, "extraction": extraction, "paper": paper}


@router.post("/alerts/{alert_id}/decision")
def update_alert_decision(alert_id: int, body: AlertDecision, session: Session = Depends(get_session)):
    alert = session.exec(select(Alert).where(Alert.id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    status_norm = body.status.strip().lower()
    if status_norm not in {"confirmed", "watch_list", "dismissed"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    alert.status = status_norm
    alert.reviewer_note = body.reviewer_note
    # touch updated_at
    from datetime import datetime as _dt

    alert.updated_at = _dt.utcnow()
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


