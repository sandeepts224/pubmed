from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import httpx

from backend.app.core.settings import settings


class PubMedClient:
    """
    Minimal PubMed E-utilities client (esearch + efetch).
    """

    def __init__(self, http: Optional[httpx.Client] = None):
        self._http = http or httpx.Client(timeout=30.0)

    def esearch_pmids(self, term: str, mindate: str, maxdate: str, retmax: int = 200) -> list[str]:
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": str(retmax),
            "datetype": "edat",
            "mindate": mindate,
            "maxdate": maxdate,
        }
        if settings.pubmed_email:
            params["email"] = settings.pubmed_email
        if settings.pubmed_tool:
            params["tool"] = settings.pubmed_tool
        if settings.pubmed_api_key:
            # Optional: increases default E-utilities rate limit when provided.
            params["api_key"] = settings.pubmed_api_key

        r = self._http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=params)
        r.raise_for_status()
        data = r.json()
        return list(data.get("esearchresult", {}).get("idlist", []) or [])

    def efetch_xml(self, pmids: list[str]) -> str:
        if not pmids:
            return ""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        if settings.pubmed_email:
            params["email"] = settings.pubmed_email
        if settings.pubmed_tool:
            params["tool"] = settings.pubmed_tool
        if settings.pubmed_api_key:
            params["api_key"] = settings.pubmed_api_key

        r = self._http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=params)
        r.raise_for_status()
        return r.text


def last_24h_edat_window(now_utc: Optional[dt.datetime] = None) -> tuple[str, str]:
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(hours=24)
    # NCBI supports YYYY/MM/DD for mindate/maxdate with datetype=edat.
    return (start.strftime("%Y/%m/%d"), now.strftime("%Y/%m/%d"))


