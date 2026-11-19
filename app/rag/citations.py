"""Server-side "Sources" for chat responses.

Citations list the documents retrieved from Azure AI Search and supplied to the
model. They are built only from retrieval metadata (title, page, URL), never
from model output, because retrieval does not prove which source the model
relied on and model-written source names can be invented.
"""
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

SOURCE_TAG_PATTERN = re.compile(r"[ \t]*\[Source:[^\]\n]*\]")


def _reference(doc: Dict[str, Any]) -> str:
    page = doc.get("page")
    url = (doc.get("url") or "").strip() if isinstance(doc.get("url"), str) else ""
    if page not in (None, ""):
        return f"page {page}"
    if url:
        return url
    return ""


def build_citations(documents: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """``{"title", "reference"}`` for each distinct retrieved document, in retrieval order.

    Documents without a title are skipped rather than given an invented name.
    ``reference`` is ``"page N"``, the document URL, or ``""`` when neither exists.
    """
    citations: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        title = (doc.get("title") or "").strip() if isinstance(doc.get("title"), str) else ""
        if not title:
            continue
        key = (title, _reference(doc))
        if key in seen:
            continue
        seen.add(key)
        citations.append({"title": title, "reference": key[1]})
    return citations


def validate_citations(
    citations: Iterable[Dict[str, Any]], documents: Iterable[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Keep only citations that correspond to a retrieved document."""
    allowed = {(c["title"], c["reference"]) for c in build_citations(documents)}
    valid: List[Dict[str, str]] = []
    for citation in citations or []:
        key = (str(citation.get("title", "")), str(citation.get("reference", "")))
        if key in allowed and {"title": key[0], "reference": key[1]} not in valid:
            valid.append({"title": key[0], "reference": key[1]})
    return valid


def strip_source_tags(text: str) -> str:
    """Remove ``[Source: ...]`` tags so internal labels never reach users."""
    cleaned = SOURCE_TAG_PATTERN.sub("", text)
    # Tidy spaces left before punctuation by a removed tag ("text [Source: x]." -> "text.")
    return re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
