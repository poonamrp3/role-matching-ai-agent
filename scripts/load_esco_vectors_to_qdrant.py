#!/usr/bin/env python3
"""Validate, deduplicate, and load local ESCO Nomic vectors into Qdrant.

The source ESCO CSV contains four exact duplicate occupation rows. This loader keeps one copy
when document ID, retrieval document, and vector are all identical; any conflicting duplicate
causes the run to fail rather than silently overwriting a role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VECTORS = PROJECT_ROOT / "data" / "embeddings" / "esco_role_vectors.npz"
DEFAULT_RETRIEVAL = PROJECT_ROOT / "data" / "processed" / "esco_retrieval_documents.jsonl"
DEFAULT_ROLES = PROJECT_ROOT / "data" / "processed" / "esco_roles.jsonl"
DEFAULT_STORAGE = PROJECT_ROOT / "data" / "qdrant"
COLLECTION_NAME = "esco_roles_v1"
BATCH_SIZE = 128


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def role_payload(document: dict, role: dict, index_status: str) -> dict:
    """Create the searchable role payload; embedding text itself is intentionally not stored."""

    metadata = document["metadata"]
    return {
        "document_id": document["document_id"],
        "parent_role_id": document["parent_role_id"],
        "chunk_index": document["chunk_index"],
        "chunk_type": document["chunk_type"],
        "record_type": "taxonomy_reference",
        "index_status": index_status,
        "source": document["source"],
        "role_uri": metadata["role_uri"],
        "title": metadata["title"],
        "alternative_titles": metadata["alternative_titles"],
        "description": role["description"],
        "isco_group": metadata["isco_group"],
        "essential_skills": metadata["essential_skills"],
        "optional_skills": metadata["optional_skills"],
        "content_sha256": document["content_sha256"],
    }


def unique_records(
    document_ids: list[str], vectors: np.ndarray, documents: list[dict], roles_by_id: dict[str, dict]
) -> tuple[list[tuple[str, np.ndarray, dict]], int]:
    retrieval_ids = [document["document_id"] for document in documents]
    if document_ids != retrieval_ids:
        raise ValueError("Vector document IDs do not align exactly with retrieval-document IDs")
    if len(document_ids) != len(vectors):
        raise ValueError("Vector ID count does not match vector row count")

    unique: dict[str, tuple[np.ndarray, dict]] = {}
    duplicates_dropped = 0
    for document_id, vector, document in zip(document_ids, vectors, documents, strict=True):
        role = roles_by_id.get(document["parent_role_id"])
        if role is None:
            raise ValueError(f"No canonical role found for {document_id}")
        if document_id in unique:
            previous_vector, previous_document = unique[document_id]
            identical_document = previous_document == document
            identical_vector = np.array_equal(previous_vector, vector)
            if not (identical_document and identical_vector):
                raise ValueError(f"Conflicting duplicate document ID: {document_id}")
            duplicates_dropped += 1
            continue
        unique[document_id] = (vector, document)

    return [
        (document_id, vector, document)
        for document_id, (vector, document) in unique.items()
    ], duplicates_dropped


def point_id(document_id: str) -> str:
    """Stable UUID required for safe future upserts of the same retrieval document."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, document_id))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, default=DEFAULT_VECTORS)
    parser.add_argument("--retrieval-documents", type=Path, default=DEFAULT_RETRIEVAL)
    parser.add_argument("--canonical-roles", type=Path, default=DEFAULT_ROLES)
    parser.add_argument("--storage-path", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--index-status", default="active", choices=("active", "inactive"))
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild an existing collection with this exact name.",
    )
    args = parser.parse_args()

    documents = load_jsonl(args.retrieval_documents)
    roles = load_jsonl(args.canonical_roles)
    roles_by_id = {role["id"]: role for role in roles}
    with np.load(args.vectors, allow_pickle=False) as archive:
        document_ids = archive["document_ids"].tolist()
        vectors = archive["vectors"]

    if vectors.ndim != 2 or vectors.shape[1] != 512:
        raise ValueError(f"Expected 512-dimensional matrix; received shape {vectors.shape}")
    if vectors.dtype != np.float32 or not np.isfinite(vectors).all():
        raise ValueError("Vectors must be finite float32 values")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-5):
        raise ValueError("Vectors are not L2 normalized")

    records, duplicates_dropped = unique_records(document_ids, vectors, documents, roles_by_id)
    args.storage_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(args.storage_path))
    if client.collection_exists(args.collection):
        if not args.recreate:
            raise RuntimeError(
                f"Collection {args.collection!r} already exists. Use --recreate only when replacement is intended."
            )
        client.delete_collection(args.collection)

    client.create_collection(
        collection_name=args.collection,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )
    client.create_payload_index(
        collection_name=args.collection,
        field_name="index_status",
        field_schema="keyword",
    )

    for batch_start in range(0, len(records), BATCH_SIZE):
        batch = records[batch_start : batch_start + BATCH_SIZE]
        points = []
        for document_id, vector, document in batch:
            role = roles_by_id[document["parent_role_id"]]
            points.append(
                PointStruct(
                    id=point_id(document_id),
                    vector=vector.tolist(),
                    payload=role_payload(document, role, args.index_status),
                )
            )
        client.upsert(collection_name=args.collection, points=points, wait=True)
        print(f"Upserted {min(batch_start + len(batch), len(records))}/{len(records)} roles")

    count = client.count(collection_name=args.collection, exact=True).count
    if count != len(records):
        raise RuntimeError(f"Qdrant count mismatch: expected {len(records)}, found {count}")

    verification = client.query_points(
        collection_name=args.collection,
        query=records[0][1].tolist(),
        query_filter=Filter(
            must=[FieldCondition(key="index_status", match=MatchValue(value="active"))]
        ),
        limit=1,
        with_payload=True,
    ).points[0]
    if verification.payload["document_id"] != records[0][0]:
        raise RuntimeError("Verification query returned an unexpected point")

    vector_sha256 = hashlib.sha256(args.vectors.read_bytes()).hexdigest()
    manifest = {
        "collection": args.collection,
        "storage_path": str(args.storage_path.relative_to(PROJECT_ROOT)),
        "distance": "cosine",
        "vector_dimensions": 512,
        "input_vector_rows": len(document_ids),
        "indexed_unique_roles": len(records),
        "exact_source_duplicates_dropped": duplicates_dropped,
        "index_status": args.index_status,
        "vector_file_sha256": vector_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification": {
            "document_id": verification.payload["document_id"],
            "title": verification.payload["title"],
            "score": float(verification.score),
        },
    }
    manifest_path = args.storage_path / f"{args.collection}_ingestion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {count} active role vectors in {args.collection}")
    print(f"Wrote ingestion manifest to {manifest_path}")


if __name__ == "__main__":
    main()
