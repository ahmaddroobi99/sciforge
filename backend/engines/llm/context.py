"""
Builds the paper context block shared by every LLM stage.
"""
from backend import config
from backend.models import SourceDocument


def paper_is_truncated(doc: SourceDocument) -> bool:
    return len(doc.raw_text) > config.LLM_MAX_DOC_CHARS


def document_context(doc: SourceDocument) -> str:
    """Paper metadata, regex-extracted equations and full text, wrapped in <paper> tags."""
    lines = [f"FILENAME: {doc.filename}", f"PAGES: {doc.num_pages}"]
    if doc.equations:
        lines.append("EQUATIONS FOUND BY REGEX IN THE TEXT LAYER (may be incomplete or garbled):")
        lines += [f"  [{eq.id}, p.{eq.page}] {eq.latex}" for eq in doc.equations[:80]]
    text = doc.raw_text[: config.LLM_MAX_DOC_CHARS]
    if paper_is_truncated(doc):
        text += f"\n[... truncated at {config.LLM_MAX_DOC_CHARS} characters ...]"
    lines += ["", "FULL TEXT ('--- Page N ---' marks page starts where available):", text]
    return "<paper>\n" + "\n".join(lines) + "\n</paper>"
