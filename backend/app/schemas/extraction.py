from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AlertDecision(BaseModel):
    status: str  # confirmed, watch_list, dismissed
    reviewer_note: str | None = None


class ExtractionCreate(BaseModel):
    adverse_event: Optional[str] = None
    meddra_term: Optional[str] = None
    incidence_pct: Optional[float] = None
    sample_size: Optional[int] = None
    population: Optional[str] = None
    subgroup_risk: Optional[str] = None
    study_type: Optional[str] = None
    data_source: Optional[str] = None
    severity: Optional[str] = None
    time_to_onset_days: Optional[float] = None
    combination: Optional[str] = None
    authors_claim_novel: Optional[bool] = None
    confidence: Optional[float] = None


