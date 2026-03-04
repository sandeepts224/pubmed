from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="scores.id", index=True)

    status: str = Field(default="pending_review", index=True)  # pending_review, confirmed, watch_list, dismissed
    reviewer_note: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


