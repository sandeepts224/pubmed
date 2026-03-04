from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    t = "".join(el.itertext()).strip()
    return t or None


def _collect_texts(parent: ET.Element | None, xpath: str) -> list[str]:
    if parent is None:
        return []
    vals: list[str] = []
    for el in parent.findall(xpath):
        t = _text(el)
        if t:
            vals.append(t)
    return vals


def parse_pubmed_efetch_xml(xml_text: str) -> list[dict[str, Any]]:
    """
    Parses efetch XML into a list of dicts keyed by pmid + common metadata.

    Note: PubMed XML can be messy; we keep fields best-effort and store raw per-article XML later if desired.
    """
    if not xml_text.strip():
        return []

    root = ET.fromstring(xml_text)
    articles: list[dict[str, Any]] = []

    for pubmed_article in root.findall(".//PubmedArticle"):
        medline = pubmed_article.find("MedlineCitation")
        article = medline.find("Article") if medline is not None else None

        pmid = _text(medline.find("PMID") if medline is not None else None)
        if not pmid:
            continue

        title = _text(article.find("ArticleTitle") if article is not None else None)

        abstract_el = article.find("Abstract") if article is not None else None
        abstract_texts = _collect_texts(abstract_el, "AbstractText") if abstract_el is not None else []
        abstract = "\n".join(abstract_texts) if abstract_texts else None

        journal_el = article.find("Journal") if article is not None else None
        journal = _text(journal_el.find("Title") if journal_el is not None else None)

        pub_date = None
        pub_date_el = journal_el.find("JournalIssue/PubDate") if journal_el is not None else None
        if pub_date_el is not None:
            year = _text(pub_date_el.find("Year"))
            month = _text(pub_date_el.find("Month"))
            day = _text(pub_date_el.find("Day"))
            # Keep raw-ish; normalize later.
            pub_date = "-".join([p for p in [year, month, day] if p]) or None

        # DOI
        doi = None
        for aid in article.findall("ELocationID") if article is not None else []:
            if aid.attrib.get("EIdType") == "doi":
                doi = _text(aid)
                if doi:
                    break

        # MeSH terms
        mesh_list = _collect_texts(medline.find("MeshHeadingList") if medline is not None else None, "MeshHeading/DescriptorName")

        # Publication types
        pub_types = _collect_texts(article.find("PublicationTypeList") if article is not None else None, "PublicationType")

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "doi": doi,
                "pub_date": pub_date,
                "mesh_terms_json": json.dumps(mesh_list),
                "publication_types_json": json.dumps(pub_types),
            }
        )

    return articles


