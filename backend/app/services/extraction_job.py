from __future__ import annotations

import json
from typing import Any, Dict

from sqlmodel import Session, select

from backend.app.clients.llm import ClaudeClient
from backend.app.core.settings import settings
from backend.app.models.extraction import Extraction
from backend.app.models.paper import Paper


EXTRACTION_SYSTEM_PROMPT = (
    "You are a pharmacovigilance assistant. "
    "Given a PubMed abstract about pembrolizumab (Keytruda), "
    "extract structured safety signal fields as JSON. "
    "Do NOT judge contradiction vs the FDA label; only extract."
)


def _build_extraction_user_prompt(title: str | None, abstract: str | None) -> str:
    parts = []
    if title:
        parts.append(f"TITLE:\n{title}\n")
    if abstract:
        parts.append(f"ABSTRACT:\n{abstract}\n")
    body = "\n".join(parts) or "No abstract text was provided."

    instructions = """
Read the abstract and return ONLY a JSON object with these keys:
- adverse_event (string or null)
- meddra_term (string or null; closest MedDRA PT if you can infer, else null)
- incidence_pct (number in percent, e.g. 0.24 for 0.24%, or null)
- sample_size (integer or null)
- population (short free-text description or null)
- subgroup_risk (short description of any higher-risk subgroup, or null)
- study_type (one of: case_report, case_series, retrospective_cohort, prospective_cohort, registry_study, clinical_trial, other)
- data_source (e.g. 'EHR', 'claims', 'registry', 'trial', or null)
- severity (brief description or null)
- time_to_onset_days (number of days or null; convert from weeks/months if given)
- combination (string listing drugs in combination if relevant, else null)
- authors_claim_novel (true/false if authors say this is first/not previously described; else false)
- confidence (0 to 1, float)

Return ONLY valid JSON, no comments or explanation.
"""
    return body + "\n\n" + instructions.strip()


def extract_for_paper(session: Session, paper: Paper, client: ClaudeClient | None = None) -> Extraction:
    if not paper.abstract:
        raise ValueError("Paper has no abstract; cannot run extraction.")

    client = client or ClaudeClient()
    prompt = _build_extraction_user_prompt(paper.title, paper.abstract)

    resp = client.create_message(
        model=settings.claude_extraction_model,
        system=EXTRACTION_SYSTEM_PROMPT,
        user=prompt,
        max_tokens=8000,
    )
    text = ClaudeClient.message_text_content(resp).strip()

    # Debug: log if Claude returned empty or unexpected response
    if not text:
        print(
            f"[EXTRACTION DEBUG] pmid={paper.pmid} id={paper.id}: Claude returned empty text. "
            f"Response structure: {json.dumps(resp, indent=2)[:500]}",
            flush=True,
        )
        raise ValueError("Claude returned empty response (no text content)")

    # Try to extract JSON if Claude wrapped it in markdown code blocks
    if text.startswith("```"):
        # Extract JSON from markdown code block
        lines = text.split("\n")
        json_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                json_lines.append(line)
        if json_lines:
            text = "\n".join(json_lines).strip()

    try:
        data: Dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"[EXTRACTION DEBUG] pmid={paper.pmid} id={paper.id}: Failed to parse JSON. "
            f"Claude response (first 500 chars): {text[:500]}",
            flush=True,
        )
        raise ValueError(f"Claude did not return valid JSON: {exc}") from exc

    ex = Extraction(
        paper_id=paper.id,
        adverse_event=data.get("adverse_event"),
        meddra_term=data.get("meddra_term"),
        incidence_pct=data.get("incidence_pct"),
        sample_size=data.get("sample_size"),
        population=data.get("population"),
        subgroup_risk=data.get("subgroup_risk"),
        study_type=data.get("study_type"),
        data_source=data.get("data_source"),
        severity=data.get("severity"),
        time_to_onset_days=data.get("time_to_onset_days"),
        combination=data.get("combination"),
        authors_claim_novel=data.get("authors_claim_novel"),
        confidence=data.get("confidence"),
        raw_llm_json=json.dumps(resp),
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


def run_extraction_for_unprocessed_papers(session: Session, limit: int = 5) -> dict[str, int]:
    """
    Find papers without extractions and run Claude-based extraction for a small batch.
    """
    # Papers with no existing extraction
    subq = select(Extraction.paper_id)
    papers = session.exec(
        select(Paper)
        .where(Paper.id.not_in(subq))
        .order_by(Paper.created_at.desc())
        .limit(max(1, min(limit, 30)))
    ).all()

    if not papers:
        return {"processed": 0}

    client = ClaudeClient()
    processed = 0
    errors = 0
    for p in papers:
        # Skip if no abstract; we can later add a fallback using title + MeSH, but for now require abstract.
        if not p.abstract:
            continue
        try:
            extract_for_paper(session=session, paper=p, client=client)
            processed += 1
        except Exception as exc:
            # In this environment, external LLM calls can fail (network/proxy).
            # Log the error so we can see exactly why Claude failed.
            print(
                f"[EXTRACTION ERROR] pmid={p.pmid} id={p.id}: {type(exc).__name__}: {exc}",
                flush=True,
            )
            errors += 1
            continue

    return {"processed": processed, "errors": errors}


