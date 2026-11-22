#!/usr/bin/env python3
"""Create search-ready ESCO role profiles for the embedding stage.

By default, each occupation is split into 350-word, labelled, context-preserving
chunks. Set ``--max-words-per-chunk 0`` to keep whole occupations for comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def make_embedding_sections(role: dict) -> list[str]:
    """Build labelled role sections so their meaning remains clear to the model."""
    sections = [f"Role title: {role['title']}"]
    if role["alternative_titles"]:
        sections.append(f"Alternative titles: {', '.join(role['alternative_titles'])}")
    if role["description"]:
        sections.append(f"Role description: {role['description']}")
    if role["essential_skills"]:
        sections.append(f"Essential skills: {', '.join(role['essential_skills'])}")
    if role["optional_skills"]:
        sections.append(f"Optional skills: {', '.join(role['optional_skills'])}")
    return sections


def make_embedding_text(role: dict) -> str:
    """Build the complete embedding text for one role."""
    return "\n".join(make_embedding_sections(role))


def word_count(text: str) -> int:
    return len(text.split())


def split_section(section: str, maximum_words: int) -> list[str]:
    """Split an oversized labelled section while repeating its label in every part."""
    if word_count(section) <= maximum_words:
        return [section]

    label, separator, content = section.partition(": ")
    if not separator:
        words = section.split()
        return [" ".join(words[start : start + maximum_words]) for start in range(0, len(words), maximum_words)]

    label_prefix = f"{label}:"
    available_words = maximum_words - word_count(label_prefix)
    if available_words < 1:
        raise ValueError("max-words-per-chunk is too small to retain section labels")
    words = content.split()
    return [
        f"{label_prefix} {' '.join(words[start : start + available_words])}"
        for start in range(0, len(words), available_words)
    ]


def chunk_embedding_text(role: dict, maximum_words: int) -> list[str]:
    """Return one full role or labelled chunks that each retain the role title."""
    if maximum_words == 0:
        return [make_embedding_text(role)]

    sections = make_embedding_sections(role)
    role_title = sections[0]
    if word_count(role_title) > maximum_words:
        raise ValueError("max-words-per-chunk is too small to retain the role title")

    chunks: list[str] = []
    current_sections = [role_title]
    current_words = word_count(role_title)
    for section in sections[1:]:
        for part in split_section(section, maximum_words - word_count(role_title)):
            part_words = word_count(part)
            if current_words + part_words <= maximum_words:
                current_sections.append(part)
                current_words += part_words
            else:
                chunks.append("\n".join(current_sections))
                current_sections = [role_title, part]
                current_words = word_count(role_title) + part_words
    chunks.append("\n".join(current_sections))
    return chunks


def percentile(sorted_values: list[int], fraction: float) -> int:
    return sorted_values[round((len(sorted_values) - 1) * fraction)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/esco_roles.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/esco_retrieval_documents.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/esco_retrieval_manifest.json"))
    parser.add_argument(
        "--max-words-per-chunk",
        type=int,
        default=350,
        help="Maximum words in each role chunk; 0 keeps each ESCO occupation intact.",
    )
    args = parser.parse_args()
    if args.max_words_per_chunk < 0:
        raise ValueError("max-words-per-chunk must be zero or a positive integer")

    roles = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    documents = []
    roles_split = 0
    for role in roles:
        chunks = chunk_embedding_text(role, args.max_words_per_chunk)
        roles_split += int(len(chunks) > 1)
        for chunk_index, embedding_text in enumerate(chunks):
            is_full_role = len(chunks) == 1
            documents.append({
                "document_id": f"esco-role:{role['id']}:full" if is_full_role else f"esco-role:{role['id']}:chunk:{chunk_index}",
                "parent_role_id": role["id"],
                "chunk_index": chunk_index,
                "chunk_type": "full_role" if is_full_role else "role_chunk",
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

    lengths = sorted(word_count(document["embedding_text"]) for document in documents)
    manifest = {
        "source_document": str(args.input),
        "source_role_count": len(roles),
        "retrieval_document_count": len(documents),
        "roles_split_into_chunks": roles_split,
        "chunking_policy": (
            "one complete ESCO occupation per search-ready role profile"
            if args.max_words_per_chunk == 0
            else f"labelled role chunks of at most {args.max_words_per_chunk} words, each retaining the role title"
        ),
        "word_count": {
            "min": lengths[0],
            "p50": percentile(lengths, 0.50),
            "p90": percentile(lengths, 0.90),
            "p95": percentile(lengths, 0.95),
            "max": lengths[-1],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document, ensure_ascii=False) + "\n")
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(documents)} search-ready role profiles to {args.output}")
    print(f"Wrote retrieval manifest to {args.manifest}")


if __name__ == "__main__":
    main()
