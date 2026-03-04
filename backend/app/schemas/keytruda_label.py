from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class ImmuneMediatedAdverseEvent(BaseModel):
    adverse_event: str
    meddra_preferred_term: str
    meddra_hlt: Optional[str] = None

    incidence_pct: Optional[float] = None
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

    special_populations: List[str] = Field(default_factory=list)
    adjuvant_nsclc_incidence_pct: Optional[float] = None

    combination_note: Optional[str] = None
    label_section: Optional[str] = None
    on_label: bool = True


class RareAdverseEvent(BaseModel):
    adverse_event: str
    meddra_preferred_term: str

    incidence_pct: Optional[float] = None
    incidence_note: Optional[str] = None
    source_trials: Optional[str] = None
    on_label: bool = True
    label_section: Optional[str] = None


class AdverseReactionDiscontinuation(BaseModel):
    event: str
    pct: float


class WarningPrecaution(BaseModel):
    section: str
    title: str
    summary: str


class DrugInteractions(BaseModel):
    noted_combinations_on_label: List[str] = Field(default_factory=list)
    contraindicated_combinations: List[str] = Field(default_factory=list)


class LabelMetadata(BaseModel):
    data_extracted_date: Optional[date] = None
    sources: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class KeytrudaLabel(BaseModel):
    drug: str
    brand_name: str
    manufacturer: str
    label_revision_date: date
    label_source: str
    baseline_population: Optional[str] = None

    immune_mediated_adverse_events: List[ImmuneMediatedAdverseEvent] = Field(default_factory=list)
    rare_adverse_events_less_than_1pct: List[RareAdverseEvent] = Field(default_factory=list)

    common_adverse_reactions_ge_20pct_monotherapy: List[str] = Field(default_factory=list)
    adverse_reactions_leading_to_discontinuation: List[AdverseReactionDiscontinuation] = Field(default_factory=list)

    warnings_and_precautions: List[WarningPrecaution] = Field(default_factory=list)
    drug_interactions: DrugInteractions = Field(default_factory=DrugInteractions)

    metadata: LabelMetadata = Field(default_factory=LabelMetadata)


