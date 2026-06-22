"""Qdrant vector store service — semantic search over the legal knowledge base.

Wraps qdrant-client for search, upsert, and delete operations against
the legalcopilot_cases collection (33K+ vectors, 1536-dim, cosine).
"""

import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
)

from legalcopilot.config import settings

_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )
    return _client


def ensure_collection(
    collection_name: Optional[str] = None,
    dimensions: Optional[int] = None,
) -> None:
    """Create the collection if it doesn't exist."""
    collection_name = collection_name or settings.QDRANT_COLLECTION
    dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
    client = _get_client()

    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimensions,
                distance=Distance.COSINE,
            ),
        )


def search(
    query_vector: list[float],
    limit: int = 10,
    score_threshold: float = 0.0,
    collection_name: Optional[str] = None,
    filter_conditions: Optional[dict] = None,
) -> list[dict]:
    """Semantic search over the knowledge base.

    Args:
        query_vector: Query embedding (1536-dim).
        limit: Max results to return.
        score_threshold: Minimum cosine similarity.
        collection_name: Override default collection.
        filter_conditions: Optional Qdrant filter dict (e.g., {"court": "SGHC"}).

    Returns:
        List of dicts with id, score, and payload.
    """
    collection_name = collection_name or settings.QDRANT_COLLECTION
    client = _get_client()

    query_filter = None
    if filter_conditions:
        must_conditions = []
        # Build range condition for year_from/year_to on the "year" payload field
        year_range = {}
        for k, v in filter_conditions.items():
            if k == "year_from":
                year_range["gte"] = v
            elif k == "year_to":
                year_range["lte"] = v
            else:
                must_conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))
        if year_range:
            must_conditions.append(FieldCondition(key="year", range=Range(**year_range)))
        query_filter = Filter(must=must_conditions)

    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
    )

    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            "payload": hit.payload or {},
        }
        for hit in results
    ]


def upsert_vectors(
    vectors: list[dict],
    collection_name: Optional[str] = None,
) -> None:
    """Upsert vectors into the collection.

    Args:
        vectors: List of dicts with 'id' (optional), 'vector', and 'payload'.
        collection_name: Override default collection.
    """
    collection_name = collection_name or settings.QDRANT_COLLECTION
    client = _get_client()

    points = [
        PointStruct(
            id=v.get("id", str(uuid.uuid4())),
            vector=v["vector"],
            payload=v.get("payload", {}),
        )
        for v in vectors
    ]

    client.upsert(collection_name=collection_name, points=points)


def delete_vectors(
    ids: list[str],
    collection_name: Optional[str] = None,
) -> None:
    """Delete vectors by ID."""
    collection_name = collection_name or settings.QDRANT_COLLECTION
    client = _get_client()
    client.delete(collection_name=collection_name, points_selector=ids)
