# backend/ingestion/embedder.py
"""
Embedder — Code chunking + embedding via text-embedding-004 + ChromaDB.

Chunks source files at the class level, embeds with Google's text-embedding-004,
and stores in ChromaDB. Used by job_runner.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.config import settings
from backend.db.chroma_client import get_or_create_collection

logger = logging.getLogger(__name__)


def embed_and_store(
    ast_results: list[dict],
    source_dir: str,
    job_id: str,
) -> int:
    """
    Chunk source code at the class level, embed, and store in ChromaDB.
    Returns the number of documents stored.
    """
    collection = get_or_create_collection()
    chunks = _build_chunks(ast_results, source_dir, job_id)

    if not chunks:
        logger.warning("No chunks to embed for job %s", job_id)
        return 0

    # Batch upsert into ChromaDB (ChromaDB handles embedding if function is set,
    # but we store raw documents and let retrieval do the embedding)
    batch_size = 50
    stored = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        ids = [c["id"] for c in batch]
        documents = [c["document"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        stored += len(batch)

    logger.info("Embedded and stored %d chunks for job %s", stored, job_id)
    return stored


def update_community_ids(job_id: str, communities: list[dict]) -> None:
    """
    Backfill community_id in ChromaDB metadata after Louvain clustering.
    """
    collection = get_or_create_collection()

    # Build class_id → community_id lookup
    class_to_community: dict[str, int] = {}
    for comm in communities:
        cid = comm["community_id"]
        for class_id in comm["class_ids"]:
            class_to_community[class_id] = cid

    # Fetch all docs for this job and update metadata
    results = collection.get(where={"job_id": job_id}, include=["metadatas"])

    if not results["ids"]:
        return

    for doc_id, metadata in zip(results["ids"], results["metadatas"]):
        class_name = metadata.get("class_name", "")
        community_id = class_to_community.get(doc_id, class_to_community.get(class_name, -1))
        if community_id != -1:
            metadata["community_id"] = community_id
            collection.update(ids=[doc_id], metadatas=[metadata])

    logger.info("Updated community IDs for %d chunks in job %s", len(results["ids"]), job_id)


def _build_chunks(
    ast_results: list[dict],
    source_dir: str,
    job_id: str,
) -> list[dict]:
    """
    Build class-level chunks from AST results.
    Each chunk = one class definition's source code.
    """
    chunks: list[dict] = []

    for result in ast_results:
        file_path = result.get("file_path", "")
        language = result.get("language", "unknown")
        classes = result.get("classes", [])

        if not classes:
            continue

        # Read the source file
        try:
            source_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
            source_lines = source_text.splitlines()
        except (FileNotFoundError, PermissionError) as exc:
            logger.warning("Cannot read source file %s: %s", file_path, exc)
            continue

        for cls in classes:
            start = cls.get("start_line", 1) - 1  # 0-indexed
            end = cls.get("end_line", len(source_lines))
            class_source = "\n".join(source_lines[start:end])

            # If class exceeds MAX_CHUNK_SIZE, split at method boundaries
            if len(class_source) > settings.MAX_CHUNK_SIZE:
                sub_chunks = _split_large_class(cls, class_source, file_path, language, job_id)
                chunks.extend(sub_chunks)
            else:
                fqn = cls.get("fqn", cls["name"])
                chunks.append({
                    "id": fqn,
                    "document": class_source,
                    "metadata": {
                        "file_path": file_path,
                        "class_name": cls["name"],
                        "language": language,
                        "job_id": job_id,
                        "community_id": -1,  # populated after Louvain
                        "line_count": end - start,
                    },
                })

    return chunks


def _split_large_class(
    cls: dict,
    source: str,
    file_path: str,
    language: str,
    job_id: str,
) -> list[dict]:
    """Split a large class into method-level chunks."""
    chunk_size = settings.MAX_CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP
    fqn = cls.get("fqn", cls["name"])
    chunks = []

    # Simple character-based splitting with overlap
    for i in range(0, len(source), chunk_size - overlap):
        chunk_text = source[i : i + chunk_size]
        chunk_id = f"{fqn}__part{len(chunks)}"
        chunks.append({
            "id": chunk_id,
            "document": chunk_text,
            "metadata": {
                "file_path": file_path,
                "class_name": cls["name"],
                "language": language,
                "job_id": job_id,
                "community_id": -1,
                "line_count": chunk_text.count("\n") + 1,
            },
        })

    return chunks
