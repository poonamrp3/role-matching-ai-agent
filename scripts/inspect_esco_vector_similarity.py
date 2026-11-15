#!/usr/bin/env python3
"""Compare two real ESCO Nomic vectors and search the loaded Qdrant collection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS_PATH = PROJECT_ROOT / "data" / "embeddings" / "esco_role_vectors.npz"
DOCUMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "esco_retrieval_documents.jsonl"
STORAGE_PATH = PROJECT_ROOT / "data" / "qdrant"
COLLECTION_NAME = "esco_roles_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-role", default="data scientist")
    parser.add_argument("--compare-role", default="software developer")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    with DOCUMENTS_PATH.open(encoding="utf-8") as file:
        documents = [json.loads(line) for line in file if line.strip()]
    with np.load(VECTORS_PATH, allow_pickle=False) as archive:
        vectors = archive["vectors"]
        vector_ids = archive["document_ids"].tolist()
    if vector_ids != [document["document_id"] for document in documents]:
        raise RuntimeError("Embedding and retrieval-document order do not align")

    title_to_index: dict[str, int] = {}
    for index, document in enumerate(documents):
        title_to_index.setdefault(document["metadata"]["title"].casefold(), index)
    query_index = find_title(title_to_index, args.query_role)
    comparison_index = find_title(title_to_index, args.compare_role)
    query_vector = vectors[query_index]
    comparison_vector = vectors[comparison_index]
    direct_similarity = float(np.dot(query_vector, comparison_vector))

    print("Direct cosine comparison of two stored Nomic vectors")
    print(f"  {documents[query_index]['metadata']['title']!r}")
    print(f"  {documents[comparison_index]['metadata']['title']!r}")
    print(f"  cosine similarity: {direct_similarity:.6f}")
    print("  Note: cosine similarity is a ranking signal, not a fit percentage or hiring probability.")

    client = QdrantClient(path=str(STORAGE_PATH))
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector.tolist(),
        query_filter=Filter(
            must=[FieldCondition(key="index_status", match=MatchValue(value="active"))]
        ),
        limit=args.limit,
        with_payload=True,
    ).points
    print(f"\nTop {len(results)} active Qdrant neighbours for {documents[query_index]['metadata']['title']!r}:")
    for rank, result in enumerate(results, start=1):
        print(f"  {rank}. {result.payload['title']} — {float(result.score):.6f}")


def find_title(title_to_index: dict[str, int], requested_title: str) -> int:
    index = title_to_index.get(requested_title.casefold())
    if index is None:
        examples = ", ".join(sorted(title_to_index)[:10])
        raise ValueError(f"Exact ESCO role title not found: {requested_title!r}. Example titles: {examples}")
    return index


if __name__ == "__main__":
    main()
