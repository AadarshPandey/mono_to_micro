# backend/db/chroma_client.py
"""
ChromaDB Client — Embedded persistent client and collection management.

Provides a singleton ChromaDB client in embedded mode (no separate process)
with persistent storage. Used by embedder and rag_retriever.
"""

from __future__ import annotations

import logging

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Client management ─────────────────────────────────────────────────────

_client: ClientAPI | None = None


def get_chroma_client() -> ClientAPI:
    """Return the singleton ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        logger.info("ChromaDB client initialised at %s", settings.CHROMA_PERSIST_DIR)
    return _client


# ── Collection helpers ─────────────────────────────────────────────────────


def get_or_create_collection(name: str | None = None) -> Collection:
    """Get or create a ChromaDB collection by name (defaults to config value)."""
    collection_name = name or settings.CHROMA_COLLECTION_NAME
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection '%s' ready (%d documents)", collection_name, collection.count())
    return collection


def delete_collection(name: str | None = None) -> None:
    """Delete a ChromaDB collection by name."""
    collection_name = name or settings.CHROMA_COLLECTION_NAME
    client = get_chroma_client()
    try:
        client.delete_collection(name=collection_name)
        logger.info("Deleted ChromaDB collection '%s'", collection_name)
    except ValueError:
        logger.warning("Collection '%s' not found — nothing to delete", collection_name)


def get_collection(name: str | None = None) -> Collection:
    """Get an existing ChromaDB collection (raises if not found)."""
    collection_name = name or settings.CHROMA_COLLECTION_NAME
    client = get_chroma_client()
    return client.get_collection(name=collection_name)
