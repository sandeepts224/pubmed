from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Score(SQLModel, table=True):
    __tablename__ = "scores"

    id: Optional[int] = Field(default=None, primary_key=True)
    extraction_id: int = Field(foreign_key="extractions.id", index=True)

    novelty_score: float = 0.0
    incidence_delta_score: float = 0.0
    subpopulation_score: float = 0.0
    temporal_score: float = 0.0
    combination_score: float = 0.0
    rag_score: float = 0.0  # RAG-based semantic similarity score

    evidence_multiplier: float = 1.0
    composite_score: float = Field(default=0.0, index=True)

    scoring_version: str = Field(default="v2", index=True)  # Updated to v2 with RAG
    details_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


