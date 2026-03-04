from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.app.db import get_session
from backend.app.models.label import LabelVersion
from backend.app.schemas.keytruda_label import KeytrudaLabel
from backend.app.services.label_import import import_keytruda_label

router = APIRouter(tags=["label"])


@router.get("/label/versions")
def list_label_versions(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    versions = session.exec(select(LabelVersion).order_by(LabelVersion.label_revision_date.desc())).all()
    return [
        {
            "id": v.id,
            "drug": v.drug,
            "brand_name": v.brand_name,
            "label_revision_date": str(v.label_revision_date),
            "label_source": v.label_source,
            "baseline_population": v.baseline_population,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


@router.post("/label/import_json")
def import_label_json(payload: KeytrudaLabel, session: Session = Depends(get_session)) -> dict[str, Any]:
    result = import_keytruda_label(session=session, payload=payload)
    if not result.get("created", False):
        raise HTTPException(status_code=409, detail="Label version already imported.")
    return result


