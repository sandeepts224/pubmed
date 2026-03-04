from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from backend.app.models.label import LabelDrugInteraction, LabelEvent, LabelVersion, WarningPrecaution
from backend.app.schemas.keytruda_label import KeytrudaLabel


def import_keytruda_label(session: Session, payload: KeytrudaLabel) -> dict[str, Any]:
    """
    Imports a Keytruda label JSON payload into relational tables.

    Idempotency: treats (drug, label_revision_date, label_source) as a unique version key.
    """
    existing = session.exec(
        select(LabelVersion).where(
            LabelVersion.drug == payload.drug,
            LabelVersion.label_revision_date == payload.label_revision_date,
            LabelVersion.label_source == payload.label_source,
        )
    ).first()
    if existing:
        return {"created": False, "label_version_id": existing.id, "detail": "already_imported"}

    lv = LabelVersion(
        drug=payload.drug,
        brand_name=payload.brand_name,
        manufacturer=payload.manufacturer,
        label_revision_date=payload.label_revision_date,
        label_source=payload.label_source,
        baseline_population=payload.baseline_population,
    )
    session.add(lv)
    session.commit()
    session.refresh(lv)

    # Immune-mediated AEs
    for ae in payload.immune_mediated_adverse_events:
        session.add(
            LabelEvent(
                label_version_id=lv.id,
                category="immune_mediated",
                adverse_event=ae.adverse_event,
                meddra_preferred_term=ae.meddra_preferred_term,
                meddra_hlt=ae.meddra_hlt,
                incidence_pct=ae.incidence_pct,
                n_cases=ae.n_cases,
                n_total=ae.n_total,
                fatal_pct=ae.fatal_pct,
                grade4_pct=ae.grade4_pct,
                grade3_pct=ae.grade3_pct,
                grade2_pct=ae.grade2_pct,
                median_onset_months=ae.median_onset_months,
                onset_range=ae.onset_range,
                required_systemic_corticosteroids_pct=ae.required_systemic_corticosteroids_pct,
                led_to_discontinuation_pct=ae.led_to_discontinuation_pct,
                resolved_pct=ae.resolved_pct,
                recurrence_after_rechallenge_pct=ae.recurrence_after_rechallenge_pct,
                special_populations_json=json.dumps(ae.special_populations),
                combination_note=ae.combination_note,
                label_section=ae.label_section,
                on_label=ae.on_label,
            )
        )

    # Rare AEs (<1%)
    for ae in payload.rare_adverse_events_less_than_1pct:
        session.add(
            LabelEvent(
                label_version_id=lv.id,
                category="rare_lt_1pct",
                adverse_event=ae.adverse_event,
                meddra_preferred_term=ae.meddra_preferred_term,
                incidence_pct=ae.incidence_pct,
                incidence_note=ae.incidence_note,
                label_section=ae.label_section,
                on_label=ae.on_label,
            )
        )

    # Common >=20%: store as label events with best-effort PT = raw string for now
    for item in payload.common_adverse_reactions_ge_20pct_monotherapy:
        session.add(
            LabelEvent(
                label_version_id=lv.id,
                category="common_ge_20pct",
                adverse_event=item,
                meddra_preferred_term=item,
                on_label=True,
            )
        )

    # Discontinuation events
    for item in payload.adverse_reactions_leading_to_discontinuation:
        session.add(
            LabelEvent(
                label_version_id=lv.id,
                category="discontinuation",
                adverse_event=item.event,
                meddra_preferred_term=item.event,
                incidence_pct=item.pct,
                on_label=True,
            )
        )

    # Warnings & precautions
    for w in payload.warnings_and_precautions:
        session.add(
            WarningPrecaution(
                label_version_id=lv.id,
                section=w.section,
                title=w.title,
                summary=w.summary,
            )
        )

    # Drug interactions
    for combo in payload.drug_interactions.noted_combinations_on_label:
        session.add(LabelDrugInteraction(label_version_id=lv.id, interaction_type="noted", description=combo))
    for combo in payload.drug_interactions.contraindicated_combinations:
        session.add(
            LabelDrugInteraction(
                label_version_id=lv.id, interaction_type="contraindicated", description=combo
            )
        )

    session.commit()

    return {
        "created": True,
        "label_version_id": lv.id,
        "imported": {
            "immune_mediated_adverse_events": len(payload.immune_mediated_adverse_events),
            "rare_adverse_events_less_than_1pct": len(payload.rare_adverse_events_less_than_1pct),
            "common_adverse_reactions_ge_20pct_monotherapy": len(payload.common_adverse_reactions_ge_20pct_monotherapy),
            "adverse_reactions_leading_to_discontinuation": len(payload.adverse_reactions_leading_to_discontinuation),
            "warnings_and_precautions": len(payload.warnings_and_precautions),
            "drug_interactions": len(payload.drug_interactions.noted_combinations_on_label)
            + len(payload.drug_interactions.contraindicated_combinations),
        },
    }


