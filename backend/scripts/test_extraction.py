from __future__ import annotations

import sys
from sqlmodel import Session, select

from backend.app.db import engine
from backend.app.models.paper import Paper
from backend.app.services.extraction_job import extract_for_paper


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m backend.scripts.test_extraction <paper_id>")
        return 2

    paper_id = int(sys.argv[1])

    with Session(engine) as session:
        paper = session.exec(select(Paper).where(Paper.id == paper_id)).first()
        if not paper:
            print(f"Paper {paper_id} not found")
            return 1

        print(f"Testing extraction for paper {paper_id} (PMID {paper.pmid})")
        print(f"Title: {paper.title}")
        print(f"Has abstract: {bool(paper.abstract)}")
        if paper.abstract:
            print(f"Abstract length: {len(paper.abstract)}")

        try:
            extraction = extract_for_paper(session=session, paper=paper)
            print(f"SUCCESS: Created extraction {extraction.id}")
            print(f"Adverse event: {extraction.adverse_event or extraction.meddra_term}")
            return 0
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

