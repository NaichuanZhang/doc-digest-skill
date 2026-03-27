"""Strands tool definitions for document Q&A.

Tools operate on module-level document data set via set_document_data().
This follows the same pattern as adsgency's set_session_factory().
"""

from __future__ import annotations

from strands import tool

_document_data: dict | None = None


def set_document_data(data: dict) -> None:
    """Set the document data for tools to operate on."""
    global _document_data
    _document_data = data


@tool
def search_document(query: str) -> str:
    """Search through the document for content matching the query.

    Args:
        query: The search term or phrase to look for.

    Returns:
        Matching text excerpts with their section context.
    """
    if not _document_data:
        return "Error: No document loaded."

    results: list[str] = []
    query_lower = query.lower()

    for section in _document_data["sections"]:
        content = section["content"]
        if query_lower in content.lower():
            idx = content.lower().index(query_lower)
            start = max(0, idx - 200)
            end = min(len(content), idx + len(query) + 200)
            snippet = content[start:end]
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(content) else ""
            results.append(
                f"[Section: {section['title']}]\n{prefix}{snippet}{suffix}"
            )

    if not results:
        return f"No matches found for '{query}' in the document."
    return "\n\n---\n\n".join(results[:5])


@tool
def get_section(section_id: str) -> str:
    """Get the full content of a specific document section.

    Args:
        section_id: The section identifier (slug).

    Returns:
        The full section content in markdown format.
    """
    if not _document_data:
        return "Error: No document loaded."

    for section in _document_data["sections"]:
        if section["id"] == section_id:
            return f"## {section['title']}\n\n{section['content']}"

    available = [s["id"] for s in _document_data["sections"]]
    return f"Section '{section_id}' not found. Available sections: {available}"


@tool
def fact_check(claim: str, section_id: str = "") -> str:
    """Check a claim against the document content for consistency.

    Args:
        claim: The claim or statement to verify against the document.
        section_id: Optional section to focus the check on. If empty, checks all sections.

    Returns:
        Relevant document content to evaluate the claim against.
    """
    if not _document_data:
        return "Error: No document loaded."

    if section_id:
        sections = [
            s for s in _document_data["sections"] if s["id"] == section_id
        ]
        if not sections:
            sections = _document_data["sections"]
    else:
        sections = _document_data["sections"]

    context_parts = [
        f"[{s['title']}]: {s['content']}" for s in sections
    ]
    context = "\n\n".join(context_parts)
    # Truncate to avoid overwhelming the model
    context = context[:15000]

    return (
        f"Claim to verify: \"{claim}\"\n\n"
        f"Relevant document content:\n{context}\n\n"
        "Analyze whether this claim is supported, contradicted, or "
        "unaddressed by the document content above. Cite specific sections."
    )
