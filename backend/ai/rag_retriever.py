# backend/ai/rag_retriever.py
"""
RAG Retriever — ChromaDB semantic search for code context.

Queries ChromaDB for the most relevant code chunks to inject into LLM prompts.
Used by boundary_chain, contract_chain, and code_chain.
"""

from __future__ import annotations

import logging

from backend.api.schemas import BoundaryProposal
from backend.config import settings
from backend.db.chroma_client import get_or_create_collection

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    job_id: str,
    n_results: int | None = None,
) -> list[str]:
    """
    Query ChromaDB for relevant code chunks.
    Returns list of code snippet strings.
    """
    collection = get_or_create_collection()
    top_k = n_results or settings.RAG_TOP_K

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={"job_id": job_id},
    )

    documents = results.get("documents", [[]])[0]
    logger.info("RAG retrieved %d chunks for query (job %s)", len(documents), job_id)
    return documents


def retrieve_for_boundary(
    boundary: BoundaryProposal | dict,
    job_id: str,
) -> str:
    """
    Retrieve relevant code context for a boundary proposal.
    Returns concatenated source snippets with file path headers.
    """
    if isinstance(boundary, dict):
        name = boundary.get("name", "")
        classes = boundary.get("classes", [])
    else:
        name = boundary.name
        classes = boundary.classes

    query = f"classes related to {name} {', '.join(classes)}"
    chunks = retrieve(query, job_id)
    return format_chunks(chunks)


def retrieve_for_classes(
    class_names: list[str],
    job_id: str,
) -> str:
    """Retrieve code context for a list of class names."""
    collection = get_or_create_collection()
    all_docs: list[str] = []

    for class_name in class_names:
        try:
            results = collection.get(
                ids=[class_name],
                include=["documents"],
            )
            if results["documents"]:
                all_docs.extend(results["documents"])
        except Exception:
            # Fall back to query-based retrieval
            results = collection.query(
                query_texts=[class_name],
                n_results=1,
                where={"job_id": job_id},
            )
            docs = results.get("documents", [[]])[0]
            all_docs.extend(docs)

    return format_chunks(all_docs)


def format_chunks(chunks: list[str]) -> str:
    """Format a list of code chunks into a single string with separators."""
    if not chunks:
        return "(No code context available)"

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"--- Code Chunk {i} ---\n{chunk}")

    return "\n\n".join(parts)
