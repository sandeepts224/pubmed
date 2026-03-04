from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.app.db import get_session
from backend.app.jobs.pubmed_ingest import ingest_pubmed_last_24h, ingest_pubmed_last_7d_backfill
from backend.app.models.paper import Paper

router = APIRouter(tags=["pubmed"])


@router.post("/jobs/pubmed/ingest_last24h")
def run_pubmed_ingest(session: Session = Depends(get_session)):
    """
    Live ingestion: fetch PubMed papers from the last 24 hours only.
    """
    return ingest_pubmed_last_24h(session=session)


@router.post("/jobs/pubmed/ingest_last7d")
def run_pubmed_ingest_last7d(session: Session = Depends(get_session)):
    """
    Backfill ingestion: simulate 7 days of activity by running 7 consecutive
    24-hour edat windows in the past.
    """
    return ingest_pubmed_last_7d_backfill(session=session, days=7)


@router.get("/papers")
def list_papers(limit: int = 50, session: Session = Depends(get_session)):
    limit = max(1, min(limit, 200))
    papers = session.exec(select(Paper).order_by(Paper.created_at.desc()).limit(limit)).all()
    return papers


