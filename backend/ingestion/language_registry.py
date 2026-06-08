# backend/ingestion/language_registry.py
"""
Language Registry — Maps language names to Tree-sitter grammars.

Provides parser factory and file-extension-based language auto-detection.
Used by ast_parser.
"""

from __future__ import annotations

import logging

import tree_sitter_c_sharp as ts_csharp
import tree_sitter_go as ts_go
import tree_sitter_java as ts_java
import tree_sitter_python as ts_python
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

# ── Language → Grammar mapping ─────────────────────────────────────────────

LANGUAGES: dict[str, Language] = {
    "java": Language(ts_java.language()),
    "python": Language(ts_python.language()),
    "csharp": Language(ts_csharp.language()),
    "go": Language(ts_go.language()),
}

# ── File extension → Language mapping ──────────────────────────────────────

EXTENSIONS: dict[str, str] = {
    ".java": "java",
    ".py": "python",
    ".cs": "csharp",
    ".go": "go",
}


def get_language(name: str) -> Language:
    """Return the Tree-sitter Language for a given language name."""
    lang = LANGUAGES.get(name.lower())
    if lang is None:
        raise ValueError(f"Unsupported language: {name!r}. Supported: {list(LANGUAGES.keys())}")
    return lang


def get_parser(name: str) -> Parser:
    """Return a Tree-sitter Parser configured for the given language."""
    parser = Parser(get_language(name))
    return parser


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension. Returns None if unsupported."""
    from pathlib import Path

    ext = Path(file_path).suffix.lower()
    return EXTENSIONS.get(ext)


def supported_extensions() -> set[str]:
    """Return the set of file extensions we can parse."""
    return set(EXTENSIONS.keys())
