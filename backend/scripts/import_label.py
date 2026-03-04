from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.db import engine
from backend.app.schemas.keytruda_label import KeytrudaLabel
from backend.app.services.label_import import import_keytruda_label
from sqlmodel import Session


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m backend.scripts.import_label <path-to-label-json>")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 2

    payload_raw = json.loads(path.read_text(encoding="utf-8"))
    payload = KeytrudaLabel.model_validate(payload_raw)

    with Session(engine) as session:
        result = import_keytruda_label(session=session, payload=payload)
        print(json.dumps(result, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


