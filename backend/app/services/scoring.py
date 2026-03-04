from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from backend.app.models.alert import Alert
from backend.app.models.extraction import Extraction
from backend.app.models.label import LabelDrugInteraction, LabelEvent, LabelVersion
from backend.app.models.score import Score


ALERT_THRESHOLD = 50.0


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_rwe(study_type: str | None) -> bool:
    st = _norm(study_type)
    return any(k in st for k in ["retrospective", "observational", "registry", "claims", "ehr", "real-world", "realworld"])


def _latest_label_version(session: Session, drug: str = "pembrolizumab") -> LabelVersion | None:
    return session.exec(
        select(LabelVersion).where(LabelVersion.drug == drug).order_by(LabelVersion.label_revision_date.desc())
    ).first()


def _label_terms(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelEvent.meddra_preferred_term).where(LabelEvent.label_version_id == label_version_id)
    ).all()
    return {_norm(r) for r in rows if r}


def _label_event_by_term(session: Session, label_version_id: int, term: str) -> LabelEvent | None:
    # Best-effort: case-insensitive match by normalized term.
    t = _norm(term)
    events = session.exec(
        select(LabelEvent).where(
            LabelEvent.label_version_id == label_version_id,
            LabelEvent.meddra_preferred_term.is_not(None),
        )
    ).all()
    for ev in events:
        if _norm(ev.meddra_preferred_term) == t:
            return ev
    return None


def _label_special_populations(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelEvent.special_populations_json).where(LabelEvent.label_version_id == label_version_id)
    ).all()
    out: set[str] = set()
    for r in rows:
        if not r:
            continue
        try:
            items = json.loads(r)
            for x in items or []:
                if isinstance(x, str) and x.strip():
                    out.add(_norm(x))
        except Exception:
            continue
    return out


def _label_interactions(session: Session, label_version_id: int) -> set[str]:
    rows = session.exec(
        select(LabelDrugInteraction.description).where(LabelDrugInteraction.label_version_id == label_version_id)
    ).all()
    return {_norm(r) for r in rows if r}


@dataclass(frozen=True)
class ScoreResult:
    score: Score
    alert_created: bool


def score_extraction(session: Session, extraction: Extraction, label_version_id: int) -> ScoreResult:
    details: dict[str, object] = {"checks": {}, "label_version_id": label_version_id}

    term = extraction.meddra_term or extraction.adverse_event or ""
    on_label = _norm(term) in _label_terms(session, label_version_id)

    # Check 1: novelty
    novelty = 0.0
    if not on_label and term.strip():
        novelty = 25.0
        st = _norm(extraction.study_type)
        if extraction.authors_claim_novel and ("case" in st or (extraction.sample_size is not None and extraction.sample_size <= 10)):
            novelty = 35.0
    details["checks"]["novelty"] = {"on_label": on_label, "term": term, "score": novelty}

    # Check 2: incidence delta
    incidence_delta = 0.0
    if on_label and extraction.incidence_pct is not None:
        label_ev = _label_event_by_term(session, label_version_id, term)
        labeled = None
        if label_ev is not None:
            if label_ev.incidence_pct is not None:
                labeled = float(label_ev.incidence_pct)
            elif label_ev.incidence_note and "<" in label_ev.incidence_note:
                # Treat "<1%" as a conservative upper bound of 1.0
                labeled = 1.0
        if labeled and labeled > 0:
            ratio = float(extraction.incidence_pct) / labeled
            threshold = 2.5 if _is_rwe(extraction.study_type) else 2.0
            if ratio >= threshold:
                # Simple proportional score capped at 30
                incidence_delta = min(30.0, 10.0 * (ratio - threshold + 1.0))
            details["checks"]["incidence_delta"] = {
                "paper_incidence_pct": extraction.incidence_pct,
                "label_incidence_pct": labeled,
                "ratio": ratio,
                "threshold": threshold,
                "score": incidence_delta,
            }
        else:
            details["checks"]["incidence_delta"] = {"skipped": True, "reason": "no_labeled_baseline"}
    else:
        details["checks"]["incidence_delta"] = {"skipped": True, "reason": "not_on_label_or_no_paper_incidence"}

    # Check 3: subpopulation
    subpop = 0.0
    if extraction.subgroup_risk and extraction.subgroup_risk.strip():
        label_subpops = _label_special_populations(session, label_version_id)
        if _norm(extraction.subgroup_risk) not in label_subpops:
            subpop = 15.0
        details["checks"]["subpopulation"] = {
            "paper_subgroup_risk": extraction.subgroup_risk,
            "score": subpop,
        }
    else:
        details["checks"]["subpopulation"] = {"skipped": True}

    # Check 4: temporal
    temporal = 0.0
    if on_label and extraction.time_to_onset_days is not None:
        label_ev = _label_event_by_term(session, label_version_id, term)
        if label_ev and label_ev.median_onset_months:
            label_days = float(label_ev.median_onset_months) * 30.0
            if label_days > 0:
                ratio = float(extraction.time_to_onset_days) / label_days
                if ratio >= 1.5 or ratio <= (1.0 / 1.5):
                    temporal = 10.0
                details["checks"]["temporal"] = {
                    "paper_days": extraction.time_to_onset_days,
                    "label_days_est": label_days,
                    "ratio": ratio,
                    "score": temporal,
                }
        else:
            details["checks"]["temporal"] = {"skipped": True, "reason": "no_label_median_onset"}
    else:
        details["checks"]["temporal"] = {"skipped": True, "reason": "not_on_label_or_no_paper_onset"}

    # Check 5: combination
    combo_score = 0.0
    if extraction.combination and extraction.combination.strip():
        interactions = _label_interactions(session, label_version_id)
        # Best-effort: if any interaction string contains the combination text or vice versa.
        c = _norm(extraction.combination)
        found = any(c in x or x in c for x in interactions)
        if not found:
            combo_score = 10.0
        details["checks"]["combination"] = {"paper_combination": extraction.combination, "on_label": found, "score": combo_score}
    else:
        details["checks"]["combination"] = {"skipped": True}

    # Evidence multiplier (simple v1)
    mult = 1.0
    st = _norm(extraction.study_type)
    if "retrospective" in st:
        mult *= 1.5
    elif "registry" in st:
        mult *= 1.4
    elif "case" in st:
        mult *= 1.0

    if extraction.sample_size is not None:
        if extraction.sample_size >= 2000:
            mult *= 1.3
        elif extraction.sample_size >= 500:
            mult *= 1.2

    base_sum = novelty + incidence_delta + subpop + temporal + combo_score
    composite = base_sum * mult

    score = Score(
        extraction_id=extraction.id,
        novelty_score=novelty,
        incidence_delta_score=incidence_delta,
        subpopulation_score=subpop,
        temporal_score=temporal,
        combination_score=combo_score,
        evidence_multiplier=mult,
        composite_score=composite,
        scoring_version="v1",
        details_json=json.dumps(details),
    )
    session.add(score)
    session.commit()
    session.refresh(score)

    alert_created = False
    if composite >= ALERT_THRESHOLD:
        session.add(Alert(score_id=score.id, status="pending_review"))
        session.commit()
        alert_created = True

    return ScoreResult(score=score, alert_created=alert_created)


def score_all_unscored(session: Session, drug: str = "pembrolizumab") -> dict[str, int]:
    lv = _latest_label_version(session, drug=drug)
    if not lv:
        return {"scored": 0, "alerts_created": 0}

    # Find extractions that do not have a score yet
    extractions = session.exec(select(Extraction)).all()
    existing_scores = set(session.exec(select(Score.extraction_id)).all())

    scored = 0
    alerts = 0
    for ex in extractions:
        if ex.id in existing_scores:
            continue
        res = score_extraction(session=session, extraction=ex, label_version_id=lv.id)
        scored += 1
        alerts += 1 if res.alert_created else 0

    return {"scored": scored, "alerts_created": alerts}


