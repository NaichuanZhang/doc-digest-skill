#!/usr/bin/env python3
"""Extract structured sections from PDF or Markdown documents.

Usage:
    python extract_document.py <input_file> <output_dir>

Output:
    <output_dir>/document_data.json
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:80]


def _parse_markdown_sections(md_text: str) -> list[dict[str, Any]]:
    """Split markdown text into sections based on headings."""
    lines = md_text.split("\n")
    sections: list[dict[str, Any]] = []
    current_title = ""
    current_level = 1
    current_lines: list[str] = []
    seen_slugs: set[str] = set()

    def _flush():
        content = "\n".join(current_lines).strip()
        if not content and not current_title:
            return
        title = current_title or "Introduction"
        slug = _slugify(title)
        # Ensure unique slugs
        base_slug = slug
        counter = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        sections.append({
            "id": slug,
            "title": title,
            "level": current_level,
            "content": content,
            "page_start": None,
            "word_count": len(content.split()),
        })

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            _flush()
            current_level = len(heading_match.group(1))
            current_title = heading_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    _flush()

    # If no headings found, create synthetic sections from paragraphs
    if not sections:
        return _create_synthetic_sections(md_text)

    return sections


def _create_synthetic_sections(text: str) -> list[dict[str, Any]]:
    """Create sections from paragraphs when no headings exist."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    sections: list[dict[str, Any]] = []
    current_content: list[str] = []
    current_word_count = 0
    section_num = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        words = len(para.split())
        current_content.append(para)
        current_word_count += words

        if current_word_count >= 500:
            # Use first line as title (truncated)
            first_line = current_content[0][:60].strip()
            if len(current_content[0]) > 60:
                first_line += "..."
            sections.append({
                "id": f"section-{section_num}",
                "title": f"Section {section_num}",
                "level": 2,
                "content": "\n\n".join(current_content),
                "page_start": None,
                "word_count": current_word_count,
            })
            current_content = []
            current_word_count = 0
            section_num += 1

    # Flush remaining
    if current_content:
        sections.append({
            "id": f"section-{section_num}",
            "title": f"Section {section_num}",
            "level": 2,
            "content": "\n\n".join(current_content),
            "page_start": None,
            "word_count": current_word_count,
        })

    return sections if sections else [{
        "id": "content",
        "title": "Content",
        "level": 1,
        "content": text.strip(),
        "page_start": None,
        "word_count": len(text.split()),
    }]


def _extract_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from markdown if present."""
    metadata: dict[str, Any] = {
        "title": "",
        "author": None,
        "date": None,
        "page_count": None,
        "source_type": "markdown",
        "source_file": "",
    }

    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                import yaml
                fm = yaml.safe_load(text[3:end])
                if isinstance(fm, dict):
                    metadata["title"] = fm.get("title", "")
                    metadata["author"] = fm.get("author")
                    metadata["date"] = fm.get("date")
            except Exception:
                pass

    return metadata


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text


def extract_pdf(file_path: str) -> dict[str, Any]:
    """Convert PDF to structured document data using pymupdf4llm."""
    try:
        import pymupdf4llm
        import pymupdf
    except ImportError:
        print("Error: pymupdf4llm is required for PDF extraction.")
        print("Install it with: pip install pymupdf4llm")
        sys.exit(1)

    doc = pymupdf.open(file_path)
    page_count = len(doc)

    # Extract metadata from PDF properties
    pdf_meta = doc.metadata or {}
    title = pdf_meta.get("title", "") or Path(file_path).stem
    author = pdf_meta.get("author") or None
    date = pdf_meta.get("creationDate") or None

    doc.close()

    # Convert to markdown (preserves structure, headings, tables)
    md_text = pymupdf4llm.to_markdown(file_path)

    sections = _parse_markdown_sections(md_text)

    # If title is still the filename, try to infer from first heading
    if title == Path(file_path).stem and sections:
        title = sections[0]["title"]

    return {
        "metadata": {
            "title": title,
            "author": author,
            "date": date,
            "page_count": page_count,
            "source_type": "pdf",
            "source_file": Path(file_path).name,
        },
        "sections": sections,
        "full_text": md_text,
    }


def extract_markdown(file_path: str) -> dict[str, Any]:
    """Parse markdown file into structured document data."""
    text = Path(file_path).read_text(encoding="utf-8")
    metadata = _extract_frontmatter(text)
    body = _strip_frontmatter(text)
    sections = _parse_markdown_sections(body)

    # Infer title from first heading if not in frontmatter
    if not metadata["title"] and sections:
        metadata["title"] = sections[0]["title"]
    if not metadata["title"]:
        metadata["title"] = Path(file_path).stem

    metadata["source_file"] = Path(file_path).name

    return {
        "metadata": metadata,
        "sections": sections,
        "full_text": body,
    }


def extract_document(file_path: str, output_dir: str) -> str:
    """Extract document and write document_data.json.

    Returns the path to the output JSON file.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    ext = path.suffix.lower()
    if ext == ".pdf":
        data = extract_pdf(file_path)
    elif ext in (".md", ".markdown"):
        data = extract_markdown(file_path)
    else:
        print(f"Error: Unsupported file type: {ext}")
        print("Supported formats: .pdf, .md, .markdown")
        sys.exit(1)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "document_data.json"
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Print summary
    meta = data["metadata"]
    print(f"Extracted: {meta['title']}")
    print(f"  Source: {meta['source_file']} ({meta['source_type']})")
    if meta.get("page_count"):
        print(f"  Pages: {meta['page_count']}")
    print(f"  Sections: {len(data['sections'])}")
    for s in data["sections"]:
        indent = "  " * s["level"]
        print(f"  {indent}{s['title']} ({s['word_count']} words)")
    print(f"\nOutput: {json_path}")

    return str(json_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_document.py <input_file> <output_dir>")
        sys.exit(1)

    extract_document(sys.argv[1], sys.argv[2])
