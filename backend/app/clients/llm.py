from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.settings import settings


class ClaudeClient:
    """
    Minimal Anthropics Claude messages client for extraction and reasoning.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._stub = bool(settings.claude_stub)
        self.api_key = api_key or settings.claude_api_key

        if not self._stub:
            if not self.api_key:
                raise RuntimeError("Claude API key is not configured")
            self._http = httpx.Client(
                base_url="https://api.anthropic.com/v1",
                timeout=60.0,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
        else:
            self._http = None

    def create_message(self, model: str, system: str, user: str, max_tokens: int = 1024) -> Dict[str, Any]:
        if self._stub:
            # Deterministic stubbed response: a plausible extraction JSON as text content.
            fake = {
                "adverse_event": "Myasthenia gravis",
                "meddra_term": "Myasthenia gravis",
                "incidence_pct": 0.24,
                "sample_size": 4200,
                "population": "Adult solid tumor patients treated with pembrolizumab",
                "subgroup_risk": "thymoma history",
                "study_type": "retrospective_cohort",
                "data_source": "EHR",
                "severity": "Grade 3-4 in 70% of cases",
                "time_to_onset_days": 21,
                "combination": "pembrolizumab monotherapy",
                "authors_claim_novel": True,
                "confidence": 0.9,
            }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(fake),
                    }
                ]
            }

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": user,
                }
            ],
        }
        resp = self._http.post("/messages", json=payload)
        if resp.status_code >= 400:
            # Log raw error body for debugging (truncated to avoid huge prints).
            print(
                f"[CLAUDE HTTP ERROR] status={resp.status_code} body={resp.text[:1000]}",
                flush=True,
            )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def message_text_content(message: Dict[str, Any]) -> str:
        """
        Extract plain text from a Claude messages response (first text block).
        """
        content: List[Dict[str, Any]] = message.get("content", [])
        for block in content:
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                return block["text"]
        return ""


