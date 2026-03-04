from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from backend.app.clients.pubmed import PubMedClient, last_24h_edat_window
from backend.app.models.paper import Paper
from backend.app.services.pubmed_parse import parse_pubmed_efetch_xml


RARE_AE_QUERY = (
    '("pembrolizumab" OR "Keytruda" OR "MK-3475") AND '
    '("adverse event" OR "toxicity" OR "safety" OR "side effect") AND '
    '("rare" OR "unusual" OR "atypical" OR "first report" OR "case report")'
)

RWE_QUERY = (
    '("pembrolizumab" OR "Keytruda") AND '
    '("real-world" OR "RWE" OR "retrospective" OR "observational" OR "registry" OR '
    '"claims data" OR "electronic health record")'
)


def _ingest_for_window(
    session: Session,
    client: PubMedClient,
    mindate: str,
    maxdate: str,
) -> dict[str, Any]:
    """
    Core ingest logic for a single edat window.
    """
    rare_pmids = client.esearch_pmids(RARE_AE_QUERY, mindate=mindate, maxdate=maxdate)
    rwe_pmids = client.esearch_pmids(RWE_QUERY, mindate=mindate, maxdate=maxdate)

    # Determine query types per PMID (PMIDs can appear in both).
    pmid_to_types: dict[str, set[str]] = {}
    for pmid in rare_pmids:
        pmid_to_types.setdefault(pmid, set()).add("rare_ae")
    for pmid in rwe_pmids:
        pmid_to_types.setdefault(pmid, set()).add("rwe")

    all_pmids = sorted(pmid_to_types.keys())
    if not all_pmids:
        return {"mindate": mindate, "maxdate": maxdate, "found": 0, "new": 0, "skipped": 0}

    # Dedup against DB
    existing = session.exec(select(Paper.pmid).where(Paper.pmid.in_(all_pmids))).all()
    existing_set = set(existing)

    new_pmids = [p for p in all_pmids if p not in existing_set]
    if not new_pmids:
        return {
            "mindate": mindate,
            "maxdate": maxdate,
            "found": len(all_pmids),
            "new": 0,
            "skipped": len(all_pmids),
        }

    xml = client.efetch_xml(new_pmids)
    parsed = parse_pubmed_efetch_xml(xml)
    pmid_to_meta = {p["pmid"]: p for p in parsed}

    created = 0
    for pmid in new_pmids:
        meta = pmid_to_meta.get(pmid, {"pmid": pmid})
        types = sorted(pmid_to_types.get(pmid, []))

        paper = Paper(
            pmid=pmid,
            query_type=",".join(types),
            title=meta.get("title"),
            abstract=meta.get("abstract"),
            journal=meta.get("journal"),
            doi=meta.get("doi"),
            pub_date=meta.get("pub_date"),
            mesh_terms_json=meta.get("mesh_terms_json"),
            publication_types_json=meta.get("publication_types_json"),
            raw_metadata_json=json.dumps(meta),
        )
        session.add(paper)
        created += 1

    session.commit()

    return {
        "mindate": mindate,
        "maxdate": maxdate,
        "found": len(all_pmids),
        "new": created,
        "skipped": len(all_pmids) - created,
        "by_query": {"rare_ae": len(rare_pmids), "rwe": len(rwe_pmids)},
    }


def ingest_pubmed_last_24h(session: Session, client: PubMedClient | None = None) -> dict[str, Any]:
    """
    Live ingestion: only the last 24 hours.
    """
    client = client or PubMedClient()
    mindate, maxdate = last_24h_edat_window()
    return _ingest_for_window(session=session, client=client, mindate=mindate, maxdate=maxdate)


def ingest_pubmed_last_7d_backfill(
    session: Session,
    client: PubMedClient | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Backfill ingestion: simulate that the system has been running for the last `days`
    by running one 24h edat window per day in the past.

    This is intended as a one-time or occasional backfill; it reuses the same dedup
    logic so existing PMIDs will not be duplicated.
    """
    client = client or PubMedClient()

    now = dt.datetime.now(dt.timezone.utc)

    per_day: list[dict[str, Any]] = []
    total_found = 0
    total_new = 0
    total_skipped = 0

    # For d=1..days, shift `now` back by d days and use the standard 24h window helper.
    # Example for days=7:
    #   d=1 → [now-48h, now-24h]  (yesterday)
    #   d=7 → [now-192h, now-168h] (7 days ago)
    for d in range(1, days + 1):
        shifted_now = now - dt.timedelta(days=d)
        mindate, maxdate = last_24h_edat_window(now_utc=shifted_now)
        try:
            summary = _ingest_for_window(session=session, client=client, mindate=mindate, maxdate=maxdate)
        except Exception as exc:  # pragma: no cover - defensive
            # Surface the error in the API response instead of raising a 500,
            # so we can see what went wrong with a specific window.
            summary = {
                "mindate": mindate,
                "maxdate": maxdate,
                "found": 0,
                "new": 0,
                "skipped": 0,
                "error": repr(exc),
            }

        per_day.append(summary)
        total_found += summary.get("found", 0)
        total_new += summary.get("new", 0)
        total_skipped += summary.get("skipped", 0)

    return {
        "days": days,
        "total_found": total_found,
        "total_new": total_new,
        "total_skipped": total_skipped,
        "per_day": per_day,
    }


