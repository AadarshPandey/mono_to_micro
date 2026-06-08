# backend/ingestion/ast_parser.py
"""
AST Parser — Tree-sitter based static code analysis.

Parses source files to extract classes, methods, imports, and call edges.
Currently has full Java support; Python/C#/Go use a simpler fallback.
Used by job_runner and drift/scanner.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tree_sitter import Node

from backend.ingestion.language_registry import (
    detect_language,
    get_parser,
    supported_extensions,
)

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────


def parse_file(file_path: str, language: str | None = None) -> dict:
    """
    Parse a single source file and extract AST information.

    Returns dict with keys: file_path, language, classes, methods, imports, calls
    """
    path = Path(file_path)
    lang = language or detect_language(file_path)
    if lang is None:
        return {"file_path": file_path, "language": None, "classes": [], "methods": [], "imports": [], "calls": []}

    parser = get_parser(lang)
    source_bytes = path.read_bytes()
    tree = parser.parse(source_bytes)

    classes: list[dict] = []
    methods: list[dict] = []
    imports: list[dict] = []
    calls: list[dict] = []

    if lang == "java":
        _extract_java(tree.root_node, source_bytes, file_path, classes, methods, imports, calls)
    elif lang == "python":
        _extract_python(tree.root_node, source_bytes, file_path, classes, methods, imports, calls)
    else:
        # Generic fallback — extract identifiers from import-like nodes
        _extract_generic(tree.root_node, source_bytes, file_path, lang, classes, methods, imports, calls)

    return {
        "file_path": file_path,
        "language": lang,
        "classes": classes,
        "methods": methods,
        "imports": imports,
        "calls": calls,
    }


def parse_directory(dir_path: str, language: str | None = None) -> list[dict]:
    """Parse all supported source files in a directory tree."""
    root = Path(dir_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    results: list[dict] = []
    exts = supported_extensions()

    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in exts:
            file_lang = language or detect_language(str(path))
            if file_lang is not None:
                try:
                    result = parse_file(str(path), file_lang)
                    results.append(result)
                except Exception as exc:
                    logger.warning("Failed to parse %s: %s", path, exc)

    logger.info("Parsed %d files in %s", len(results), dir_path)
    return results


def extract_static_edges(ast_results: list[dict]) -> list[dict]:
    """
    Build a static edge list from parsed AST results.

    Returns list of dicts: {source_fqn, target_fqn, edge_type: "IMPORTS"|"CALLS"}
    """
    edges: list[dict] = []

    # Collect all known class names for resolving short names
    known_classes: dict[str, str] = {}  # short_name → fqn
    for result in ast_results:
        for cls in result.get("classes", []):
            fqn = cls.get("fqn", cls["name"])
            known_classes[cls["name"]] = fqn

    for result in ast_results:
        file_classes = [c["name"] for c in result.get("classes", [])]
        source_class = file_classes[0] if file_classes else Path(result["file_path"]).stem

        # Import edges
        for imp in result.get("imports", []):
            target = imp.get("target", "")
            # Try to resolve to a known class
            target_short = target.rsplit(".", 1)[-1] if "." in target else target
            target_fqn = known_classes.get(target_short, target)
            source_fqn = known_classes.get(source_class, source_class)
            if source_fqn != target_fqn:
                edges.append({
                    "source_fqn": source_fqn,
                    "target_fqn": target_fqn,
                    "edge_type": "IMPORTS",
                })

        # Call edges
        for call in result.get("calls", []):
            target = call.get("target", "")
            target_short = target.rsplit(".", 1)[-1] if "." in target else target
            target_fqn = known_classes.get(target_short, target)
            source_fqn = known_classes.get(source_class, source_class)
            if source_fqn != target_fqn:
                edges.append({
                    "source_fqn": source_fqn,
                    "target_fqn": target_fqn,
                    "edge_type": "CALLS",
                })

    # Deduplicate
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e["source_fqn"], e["target_fqn"], e["edge_type"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    logger.info("Extracted %d unique static edges", len(unique_edges))
    return unique_edges


# ── Java extractor ─────────────────────────────────────────────────────────


def _extract_java(
    root: Node,
    source: bytes,
    file_path: str,
    classes: list[dict],
    methods: list[dict],
    imports: list[dict],
    calls: list[dict],
) -> None:
    """Extract classes, methods, imports and calls from a Java AST."""
    package_name = ""

    for child in root.children:
        # Package declaration
        if child.type == "package_declaration":
            pkg_node = child.child_by_field_name("name") or _find_child_by_type(child, "scoped_identifier")
            if pkg_node:
                package_name = _node_text(pkg_node, source)

        # Import declaration
        elif child.type == "import_declaration":
            imp_path_node = _find_child_by_type(child, "scoped_identifier")
            if imp_path_node:
                imports.append({"target": _node_text(imp_path_node, source), "file_path": file_path})

        # Class declaration
        elif child.type == "class_declaration":
            _extract_java_class(child, source, file_path, package_name, classes, methods, calls)


def _extract_java_class(
    node: Node,
    source: bytes,
    file_path: str,
    package_name: str,
    classes: list[dict],
    methods: list[dict],
    calls: list[dict],
) -> None:
    """Extract a single Java class and its methods."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return

    class_name = _node_text(name_node, source)
    fqn = f"{package_name}.{class_name}" if package_name else class_name

    classes.append({
        "name": class_name,
        "fqn": fqn,
        "file_path": file_path,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    })

    # Walk class body for methods
    body = node.child_by_field_name("body")
    if body:
        for member in body.children:
            if member.type == "method_declaration":
                method_name_node = member.child_by_field_name("name")
                if method_name_node:
                    method_name = _node_text(method_name_node, source)
                    ret_node = member.child_by_field_name("type")
                    ret_type = _node_text(ret_node, source) if ret_node else "void"
                    methods.append({
                        "name": method_name,
                        "class_name": class_name,
                        "fqn": f"{fqn}#{method_name}",
                        "return_type": ret_type,
                        "file_path": file_path,
                    })

                # Extract method invocations inside the method body
                _find_method_calls(member, source, class_name, calls)


# ── Python extractor ──────────────────────────────────────────────────────


def _extract_python(
    root: Node,
    source: bytes,
    file_path: str,
    classes: list[dict],
    methods: list[dict],
    imports: list[dict],
    calls: list[dict],
) -> None:
    """Extract classes, methods, imports from a Python AST."""
    module_name = Path(file_path).stem

    for child in root.children:
        # import X / from X import Y
        if child.type in ("import_statement", "import_from_statement"):
            imp_text = _node_text(child, source)
            # Extract the module being imported
            parts = imp_text.replace("from ", "").replace("import ", "").split()
            if parts:
                imports.append({"target": parts[0].strip(","), "file_path": file_path})

        # Class definition
        elif child.type == "class_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                class_name = _node_text(name_node, source)
                classes.append({
                    "name": class_name,
                    "fqn": f"{module_name}.{class_name}",
                    "file_path": file_path,
                    "start_line": child.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                })

                # Extract methods inside class body
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "function_definition":
                            fn_name_node = member.child_by_field_name("name")
                            if fn_name_node:
                                fn_name = _node_text(fn_name_node, source)
                                methods.append({
                                    "name": fn_name,
                                    "class_name": class_name,
                                    "fqn": f"{module_name}.{class_name}#{fn_name}",
                                    "return_type": "Any",
                                    "file_path": file_path,
                                })


# ── Generic fallback extractor ─────────────────────────────────────────────


def _extract_generic(
    root: Node,
    source: bytes,
    file_path: str,
    language: str,
    classes: list[dict],
    methods: list[dict],
    imports: list[dict],
    calls: list[dict],
) -> None:
    """Minimal extractor for C#, Go, etc. — extracts class/struct/interface names."""
    module_name = Path(file_path).stem
    class_types = {"class_declaration", "struct_declaration", "interface_declaration",
                   "type_declaration", "type_spec"}

    def _walk(node: Node) -> None:
        if node.type in class_types:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _node_text(name_node, source)
                classes.append({
                    "name": name,
                    "fqn": f"{module_name}.{name}",
                    "file_path": file_path,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                })
        for child in node.children:
            _walk(child)

    _walk(root)


# ── Tree-sitter helpers ───────────────────────────────────────────────────


def _node_text(node: Node, source: bytes) -> str:
    """Extract the text of a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _find_child_by_type(node: Node, type_name: str) -> Node | None:
    """Find the first child of a node with the given type."""
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _find_method_calls(node: Node, source: bytes, context_class: str, calls: list[dict]) -> None:
    """Recursively find method_invocation nodes and record them as call edges."""
    if node.type == "method_invocation":
        # Try to get the object being called on
        obj_node = node.child_by_field_name("object")
        name_node = node.child_by_field_name("name")
        if name_node:
            target_name = _node_text(name_node, source)
            target_obj = _node_text(obj_node, source) if obj_node else ""
            target = f"{target_obj}.{target_name}" if target_obj else target_name
            calls.append({"source": context_class, "target": target})

    for child in node.children:
        _find_method_calls(child, source, context_class, calls)
