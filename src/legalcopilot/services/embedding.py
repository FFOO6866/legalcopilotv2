"""Embedding service — generates vector embeddings via Kaizen LlmClient.

Uses Kaizen's wire-layer provider abstraction (LlmDeployment.openai preset).
Model names come from .env per rules/env-models.md.
Supports text-embedding-3-small (1536 dimensions) by default.
"""

import asyncio
from typing import Optional

from kaizen.llm import LlmClient, LlmDeployment

from legalcopilot.config import settings

_client: Optional[LlmClient] = None


def _get_client() -> LlmClient:
    global _client
    if _client is None:
        deployment = LlmDeployment.openai(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
        _client = LlmClient.from_deployment(deployment)
    return _client


async def embed_text_async(text: str, model: Optional[str] = None) -> list[float]:
    """Generate embedding vector for a single text string (async)."""
    model = model or settings.EMBEDDING_MODEL
    vectors = await _get_client().embed([text], model=model)
    return vectors[0]


async def embed_batch_async(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    """Generate embeddings for a batch of texts (async)."""
    model = model or settings.EMBEDDING_MODEL
    return await _get_client().embed(texts, model=model)


def _run_async(coro):
    """Run an async coroutine, handling the case where an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def embed_text(text: str, model: Optional[str] = None) -> list[float]:
    """Generate embedding vector for a single text string (sync wrapper)."""
    return _run_async(embed_text_async(text, model))


def embed_batch(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    """Generate embeddings for a batch of texts (sync wrapper)."""
    return _run_async(embed_batch_async(texts, model))
