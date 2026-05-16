"""Heading-aware Markdown chunking for stable mem0 upserts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from scripts.cleanup_text import cleanup_text


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class MarkdownChunk:
    stable_id: str
    repo: str
    path: str
    heading: str
    heading_path: tuple[str, ...]
    content: str
    metadata: dict[str, object]


def chunk_markdown(
    text: str,
    *,
    tenant: str,
    repo: str,
    path: str,
    tags: tuple[str, ...] = (),
) -> list[MarkdownChunk]:
    """Split Markdown by headings while preserving hierarchy metadata."""
    cleaned = cleanup_text(text)
    sections: list[tuple[tuple[str, ...], list[str]]] = []
    current_heading: tuple[str, ...] = ("Document",)
    current_lines: list[str] = []
    hierarchy: list[str] = []

    for line in cleaned.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
            level = len(match.group(1))
            title = match.group(2).strip()
            hierarchy = hierarchy[: level - 1]
            hierarchy.append(title)
            current_heading = tuple(hierarchy)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    chunks: list[MarkdownChunk] = []
    heading_counts: dict[str, int] = {}
    for heading_path, lines in sections:
        content = "\n".join(lines).strip()
        if not content:
            continue

        heading = " > ".join(heading_path)
        occurrence = heading_counts.get(heading, 0) + 1
        heading_counts[heading] = occurrence
        stable_id = stable_chunk_id(repo=repo, path=path, heading=heading, occurrence=occurrence)
        metadata = {
            "tenant": tenant,
            "repo": repo,
            "path": path,
            "type": infer_document_type(path),
            "heading": heading,
            "heading_occurrence": occurrence,
            "heading_path": list(heading_path),
            "tags": list(tags),
            "source": "github",
        }
        chunks.append(
            MarkdownChunk(
                stable_id=stable_id,
                repo=repo,
                path=path,
                heading=heading,
                heading_path=heading_path,
                content=content,
                metadata=metadata,
            )
        )

    return chunks


def stable_chunk_id(*, repo: str, path: str, heading: str, occurrence: int = 1) -> str:
    suffix = "" if occurrence <= 1 else f":{occurrence}"
    raw = f"{repo}:{path}:{heading}{suffix}".encode()
    return sha256(raw).hexdigest()


def infer_document_type(path: str) -> str:
    lower = path.lower()
    if "/adr/" in lower or lower.startswith("adr/") or "/adrs/" in lower:
        return "adr"
    if lower.endswith("readme.md"):
        return "readme"
    if lower.startswith("docs/") or "/docs/" in lower:
        return "doc"
    return "markdown"
