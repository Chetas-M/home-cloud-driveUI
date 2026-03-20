"""
Helpers for search indexing and result snippets.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional

from app.models import File as FileModel

MAX_INDEX_BYTES = 256 * 1024
MAX_MATCH_CONTEXT_CHARS = 180
TEXT_FILE_TYPES = {"text"}
TEXT_EXTENSIONS = {
    "txt", "md", "markdown", "json", "xml", "html", "htm", "css", "js", "jsx",
    "ts", "tsx", "py", "java", "cpp", "c", "h", "hpp", "csv", "log", "yaml",
    "yml", "ini", "toml", "env", "sql",
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def should_extract_text(filename: str, mime_type: Optional[str], file_type: str) -> bool:
    if file_type in TEXT_FILE_TYPES:
        return True
    if mime_type and mime_type.startswith("text/"):
        return True
    extension = os.path.splitext(filename or "")[1].lower().lstrip(".")
    return extension in TEXT_EXTENSIONS


def extract_text_content(
    storage_path: Optional[str],
    filename: str,
    mime_type: Optional[str],
    file_type: str,
) -> Optional[str]:
    if not storage_path or not os.path.exists(storage_path):
        return None
    if not should_extract_text(filename, mime_type, file_type):
        return None

    try:
        with open(storage_path, "rb") as handle:
            raw_bytes = handle.read(MAX_INDEX_BYTES)
    except OSError:
        return None

    text = raw_bytes.decode("utf-8", errors="ignore")
    text = normalize_whitespace(text)
    return text or None


def build_match_context(file: FileModel, query: str, path_segments: Optional[Iterable[str]] = None) -> Optional[str]:
    normalized_query = normalize_whitespace(query).lower()
    if not normalized_query:
        return None

    haystacks = [
        ("name", file.name or ""),
        ("path", " / ".join(path_segments or [])),
        ("type", file.type or ""),
        ("mime", file.mime_type or ""),
        ("content", file.content_index or ""),
    ]

    for label, text in haystacks:
        normalized_text = normalize_whitespace(text)
        if not normalized_text:
            continue

        match_index = normalized_text.lower().find(normalized_query)
        if match_index == -1:
            continue

        if label == "content":
            start = max(0, match_index - 60)
            end = min(len(normalized_text), match_index + len(normalized_query) + 80)
            snippet = normalized_text[start:end]
            if start > 0:
                snippet = f"...{snippet}"
            if end < len(normalized_text):
                snippet = f"{snippet}..."
            return snippet[:MAX_MATCH_CONTEXT_CHARS]

        return normalized_text[:MAX_MATCH_CONTEXT_CHARS]

    return None


def build_search_document(
    storage_path: Optional[str],
    filename: str,
    mime_type: Optional[str],
    file_type: str,
) -> Optional[str]:
    return extract_text_content(storage_path, filename, mime_type, file_type)
