from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LabelVersion(SQLModel, table=True):
    __tablename__ = "label_versions"

    id: Optional[int] = Field(default=None, primary_key=True)

    drug: str = Field(index=True)
    brand_name: str = Field(index=True)
    manufacturer: str

    label_revision_date: date = Field(index=True)
    label_source: str
    baseline_population: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class LabelEvent(SQLModel, table=True):
    __tablename__ = "label_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    label_version_id: int = Field(foreign_key="label_versions.id", index=True)

    category: str = Field(index=True)  # immune_mediated, rare_lt_1pct, common_ge_20pct, discontinuation
    adverse_event: str = Field(index=True)
    meddra_preferred_term: Optional[str] = Field(default=None, index=True)
    meddra_hlt: Optional[str] = None

    incidence_pct: Optional[float] = None
    incidence_note: Optional[str] = None
    n_cases: Optional[int] = None
    n_total: Optional[int] = None

    fatal_pct: Optional[float] = None
    grade4_pct: Optional[float] = None
    grade3_pct: Optional[float] = None
    grade2_pct: Optional[float] = None

    median_onset_months: Optional[float] = None
    onset_range: Optional[str] = None

    required_systemic_corticosteroids_pct: Optional[float] = None
    led_to_discontinuation_pct: Optional[float] = None
    resolved_pct: Optional[float] = None
    recurrence_after_rechallenge_pct: Optional[float] = None

    special_populations_json: Optional[str] = None  # JSON string of list[str] for SQLite simplicity
    combination_note: Optional[str] = None

    label_section: Optional[str] = None
    on_label: bool = True


class WarningPrecaution(SQLModel, table=True):
    __tablename__ = "warnings_precautions"

    id: Optional[int] = Field(default=None, primary_key=True)
    label_version_id: int = Field(foreign_key="label_versions.id", index=True)

    section: str = Field(index=True)
    title: str
    summary: str


class LabelDrugInteraction(SQLModel, table=True):
    __tablename__ = "label_drug_interactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    label_version_id: int = Field(foreign_key="label_versions.id", index=True)

    interaction_type: str = Field(index=True)  # noted, contraindicated
    description: str = Field(index=True)


