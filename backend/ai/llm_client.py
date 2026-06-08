# backend/ai/llm_client.py
"""
LLM Client — Gemini model + embedding initialisation.

Provides singleton LLM and embedding instances configured from settings.
Used by all chains and the embedder.
"""

from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Singleton instances ────────────────────────────────────────────────────

_llm: ChatGoogleGenerativeAI | None = None
_embeddings: GoogleGenerativeAIEmbeddings | None = None


def get_llm(temperature: float | None = None) -> ChatGoogleGenerativeAI:
    """
    Return a ChatGoogleGenerativeAI instance.

    Uses default temperature from settings unless overridden.
    The default instance is cached; custom-temperature instances are not.
    """
    global _llm
    temp = temperature if temperature is not None else settings.GEMINI_TEMPERATURE

    # Return cached default if temperature matches
    if _llm is not None and temp == settings.GEMINI_TEMPERATURE:
        return _llm

    instance = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        temperature=temp,
        max_output_tokens=settings.GEMINI_MAX_TOKENS,
        google_api_key=settings.GOOGLE_API_KEY,
    )

    # Cache only the default-temperature instance
    if temp == settings.GEMINI_TEMPERATURE:
        _llm = instance
        logger.info("LLM initialised: model=%s, temperature=%.1f", settings.GEMINI_MODEL, temp)

    return instance


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Return the singleton GoogleGenerativeAIEmbeddings instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            google_api_key=settings.GOOGLE_API_KEY,
        )
        logger.info("Embeddings initialised: model=%s", settings.GEMINI_EMBEDDING_MODEL)
    return _embeddings


def clear_cache() -> None:
    """Clear cached LLM and embedding instances (call when model/key changes)."""
    global _llm, _embeddings
    _llm = None
    _embeddings = None
    logger.info("LLM cache cleared — next call will create fresh instances")

