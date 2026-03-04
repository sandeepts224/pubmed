from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    id: Optional[int] = Field(default=None, primary_key=True)

    pmid: str = Field(index=True, unique=True)
    query_type: str = Field(index=True)  # rare_ae, rwe

    title: Optional[str] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = Field(default=None, index=True)
    pub_date: Optional[str] = Field(default=None, index=True)  # keep raw for now

    mesh_terms_json: Optional[str] = None  # JSON string list[str]
    publication_types_json: Optional[str] = None  # JSON string list[str]

    raw_metadata_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


