from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from backend.app.models.alert import Alert
from backend.app.models.extraction import Extraction
from backend.app.models.paper import Paper
from backend.app.models.score import Score


def backdate_alerts_to_last_7_days(session: Session) -> dict[str, int]:
    """
    Backdate all existing alerts (and their related papers/extractions/scores)
    to have created_at timestamps spread over the last 7 days.

    Maintains chronological order: paper < extraction < score < alert.
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=7)

    # Get all alerts with their related records
    alerts = session.exec(select(Alert)).all()
    if not alerts:
        return {"alerts_backdated": 0, "papers_backdated": 0, "extractions_backdated": 0, "scores_backdated": 0}

    # Distribute alerts across 7 days (some days with more, some with fewer)
    # Use a weighted distribution: more recent days get slightly more alerts
    days_weights = [1.0, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7]  # Day 0 (today) gets most weight
    total_weight = sum(days_weights)
    day_assignments = []
    for i, alert in enumerate(alerts):
        # Weighted random day selection
        r = random.random() * total_weight
        day = 0
        cumsum = 0.0
        for d, w in enumerate(days_weights):
            cumsum += w
            if r <= cumsum:
                day = d
                break
        day_assignments.append(day)

    papers_updated = set()
    extractions_updated = set()
    scores_updated = set()

    for alert, day_offset in zip(alerts, day_assignments):
        # Alert timestamp: random time on that day
        alert_date = start_date + timedelta(days=day_offset)
        alert_hour = random.randint(8, 20)  # Business hours
        alert_minute = random.randint(0, 59)
        alert_created = alert_date.replace(hour=alert_hour, minute=alert_minute, second=random.randint(0, 59))

        # Get related score
        score = session.get(Score, alert.score_id)
        if not score:
            continue

        # Score should be 1-3 hours before alert
        score_created = alert_created - timedelta(hours=random.randint(1, 3), minutes=random.randint(0, 59))

        # Get related extraction
        extraction = session.get(Extraction, score.extraction_id)
        if not extraction:
            continue

        # Extraction should be 2-6 hours before score
        extraction_created = score_created - timedelta(hours=random.randint(2, 6), minutes=random.randint(0, 59))

        # Get related paper
        paper = session.get(Paper, extraction.paper_id)
        if not paper:
            continue

        # Paper should be 1-12 hours before extraction (ingested earlier)
        paper_created = extraction_created - timedelta(hours=random.randint(1, 12), minutes=random.randint(0, 59))

        # Update timestamps (only if not already updated)
        if paper.id not in papers_updated:
            paper.created_at = paper_created
            papers_updated.add(paper.id)

        if extraction.id not in extractions_updated:
            extraction.created_at = extraction_created
            extractions_updated.add(extraction.id)

        if score.id not in scores_updated:
            score.created_at = score_created
            scores_updated.add(score.id)

        alert.created_at = alert_created
        # updated_at should be >= created_at, but not too far in future
        if alert.status != "pending_review":
            # If reviewed, updated_at should be after created_at
            alert.updated_at = alert_created + timedelta(
                hours=random.randint(1, 24 * (7 - day_offset)), minutes=random.randint(0, 59)
            )
        else:
            # If still pending, updated_at can equal created_at
            alert.updated_at = alert_created

    session.commit()

    return {
        "alerts_backdated": len(alerts),
        "papers_backdated": len(papers_updated),
        "extractions_backdated": len(extractions_updated),
        "scores_backdated": len(scores_updated),
    }

