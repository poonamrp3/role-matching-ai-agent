"""Bounded local Qdrant search for active ESCO role vectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "qdrant"
DEFAULT_COLLECTION = "esco_roles_v1"
VECTOR_DIMENSIONS = 512
MAX_INTERNAL_ROLES = 10


@dataclass(frozen=True)
class RoleSearchResult:
    """A retrieved ESCO role and its cosine similarity to one candidate vector."""

    role_id: str
    title: str
    cosine_similarity: float
    description: str
    essential_skills: list[str]
    optional_skills: list[str]


class QdrantRoleSearchTool:
    """Search only active records in the local ESCO role collection."""

    def __init__(
        self,
        storage_path: Path = DEFAULT_STORAGE_PATH,
        collection: str = DEFAULT_COLLECTION,
    ) -> None:
        self.storage_path = storage_path
        self.collection = collection

    def search_active_roles(self, vector: list[float], limit: int) -> list[RoleSearchResult]:
        """Return nearest active ESCO role documents by Qdrant cosine similarity."""

        if not 1 <= limit <= MAX_INTERNAL_ROLES:
            raise ValueError(f"limit must be between 1 and {MAX_INTERNAL_ROLES}")
        query_vector = np.asarray(vector, dtype=np.float32)
        if query_vector.shape != (VECTOR_DIMENSIONS,) or not np.isfinite(query_vector).all():
            raise ValueError(f"Expected one finite {VECTOR_DIMENSIONS}-dimensional query vector")
        norm = float(np.linalg.norm(query_vector))
        if not np.isclose(norm, 1.0, atol=1e-5):
            raise ValueError("Query vector must be L2 normalized before Qdrant search")

        client = QdrantClient(path=str(self.storage_path))
        try:
            if not client.collection_exists(self.collection):
                raise RuntimeError(f"Qdrant collection '{self.collection}' does not exist")
            # Increase the point pool if chunks of the same occupation crowd out others.
            point_limit = limit * 8
            while True:
                points = client.query_points(
                    collection_name=self.collection,
                    query=query_vector.tolist(),
                    query_filter=Filter(
                        must=[FieldCondition(key="index_status", match=MatchValue(value="active"))]
                    ),
                    limit=point_limit,
                    with_payload=True,
                ).points
                results: list[RoleSearchResult] = []
                seen_role_ids: set[str] = set()
                for point in points:
                    payload = point.payload or {}
                    role_id = str(payload["parent_role_id"])
                    if role_id in seen_role_ids:
                        continue
                    seen_role_ids.add(role_id)
                    results.append(RoleSearchResult(
                        role_id=role_id,
                        title=str(payload["title"]),
                        cosine_similarity=float(point.score),
                        description=str(payload.get("description", "")),
                        essential_skills=list(payload.get("essential_skills", [])),
                        optional_skills=list(payload.get("optional_skills", [])),
                    ))
                    if len(results) == limit:
                        return results
                if len(points) < point_limit:
                    return results
                point_limit *= 2
        finally:
            client.close()


def as_json_ready(result: RoleSearchResult) -> dict[str, Any]:
    return asdict(result)
