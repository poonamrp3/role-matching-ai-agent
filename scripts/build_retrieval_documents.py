#!/usr/bin/env python3
"""Create the exact ESCO text units that will be embedded in the next stage.

The current ESCO role documents are small enough to keep one complete occupation as
one retrieval unit. This script preserves parent identifiers so selective section
chunking can be introduced later without breaking references.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def make_embedding_text(role: dict) -> str:
    """Build a labelled text representation so the embedding retains field meaning."""
    parts = [f"Role title: {role['title']}"]
    if role["alternative_titles"]:
        parts.append(f"Alternative titles: {', '.join(role['alternative_titles'])}")
    if role["description"]:
        parts.append(f"Role description: {role['description']}")
    if role["essential_skills"]:
        parts.append(f"Essential skills: {', '.join(role['essential_skills'])}")
    if role["optional_skills"]:
        parts.append(f"Optional skills: {', '.join(role['optional_skills'])}")
    return "\n".join(parts)


def percentile(sorted_values: list[int], fraction: float) -> int:
    return sorted_values[round((len(sorted_values) - 1) * fraction)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/esco_roles.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/esco_retrieval_documents.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/esco_retrieval_manifest.json"))
    args = parser.parse_args()

    roles = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    documents = []
    for role in roles:
        embedding_text = make_embedding_text(role)
        documents.append({
            "document_id": f"esco-role:{role['id']}:full",
            "parent_role_id": role["id"],
            "chunk_index": 0,
            "chunk_type": "full_role",
            "source": role["source"],
            "embedding_text": embedding_text,
            "content_sha256": hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
            "metadata": {
                "role_uri": role["role_uri"],
                "title": role["title"],
                "alternative_titles": role["alternative_titles"],
                "isco_group": role["isco_group"],
                "essential_skills": role["essential_skills"],
                "optional_skills": role["optional_skills"],
            },
        })

    lengths = sorted(len(document["embedding_text"].split()) for document in documents)
    manifest = {
        "source_document": str(args.input),
        "retrieval_document_count": len(documents),
        "chunking_policy": "one complete ESCO occupation per retrieval document",
        "rationale": "All source documents are below 1,200 words; title, description, and skills remain one semantic unit.",
        "word_count": {
            "min": lengths[0],
            "p50": percentile(lengths, 0.50),
            "p90": percentile(lengths, 0.90),
            "p95": percentile(lengths, 0.95),
            "max": lengths[-1],
        },
        "future_chunking_trigger": "Introduce section chunks only if source role documents exceed 1,200 words or retrieval evaluation shows loss of precision.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document, ensure_ascii=False) + "\n")
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(documents)} retrieval documents to {args.output}")
    print(f"Wrote retrieval manifest to {args.manifest}")


if __name__ == "__main__":
    main()
