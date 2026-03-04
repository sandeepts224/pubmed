from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Extraction(SQLModel, table=True):
    __tablename__ = "extractions"

    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="papers.id", index=True)

    adverse_event: Optional[str] = None
    meddra_term: Optional[str] = Field(default=None, index=True)

    incidence_pct: Optional[float] = None
    sample_size: Optional[int] = None
    population: Optional[str] = None
    subgroup_risk: Optional[str] = None

    study_type: Optional[str] = Field(default=None, index=True)  # case_report, retrospective_cohort, registry, ...
    data_source: Optional[str] = None

    severity: Optional[str] = None
    time_to_onset_days: Optional[float] = None
    combination: Optional[str] = None
    authors_claim_novel: Optional[bool] = None
    confidence: Optional[float] = None

    raw_llm_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


