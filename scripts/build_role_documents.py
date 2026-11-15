#!/usr/bin/env python3
"""Build normalized, retrieval-ready role documents from the ESCO CSV export.

This is the data-preparation stage of the indexing pipeline. It does not call an
embedding model or write to a vector database; those belong to the next stage.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({clean(value) for value in values if clean(value)}, key=str.casefold)


def split_labels(value: str | None) -> list[str]:
    """ESCO stores alternative labels as newline-separated text."""
    return unique_sorted((value or "").splitlines())


def build_documents(source_dir: Path) -> tuple[list[dict], dict]:
    occupations = read_csv(source_dir / "occupations_en.csv")
    skills = read_csv(source_dir / "skills_en.csv")
    relations = read_csv(source_dir / "occupationSkillRelations_en.csv")

    skill_by_uri = {row["conceptUri"]: row for row in skills}
    links_by_occupation: dict[str, list[dict[str, str]]] = defaultdict(list)
    for relation in relations:
        links_by_occupation[relation["occupationUri"]].append(relation)

    documents: list[dict] = []
    missing_skill_definitions = 0
    for occupation in occupations:
        role_uri = occupation["conceptUri"]
        essential: list[str] = []
        optional: list[str] = []
        skill_records: list[dict[str, str]] = []

        for link in links_by_occupation.get(role_uri, []):
            label = clean(link["skillLabel"])
            skill = skill_by_uri.get(link["skillUri"])
            if not skill:
                missing_skill_definitions += 1
            skill_records.append(
                {
                    "uri": link["skillUri"],
                    "label": label,
                    "relation_type": link["relationType"],
                    "skill_type": link["skillType"],
                    "description": clean(skill.get("description") if skill else ""),
                }
            )
            if link["relationType"] == "essential":
                essential.append(label)
            elif link["relationType"] == "optional":
                optional.append(label)

        title = clean(occupation["preferredLabel"])
        description = clean(occupation["description"]) or clean(occupation["definition"]) or clean(occupation["scopeNote"])
        aliases = split_labels(occupation.get("altLabels"))
        essential_skills = unique_sorted(essential)
        optional_skills = unique_sorted(optional)
        text = "\n".join(
            part for part in [
                f"Role: {title}",
                f"Alternative titles: {', '.join(aliases)}" if aliases else "",
                f"Description: {description}" if description else "",
                f"Essential skills: {', '.join(essential_skills)}" if essential_skills else "",
                f"Optional skills: {', '.join(optional_skills)}" if optional_skills else "",
            ] if part
        )
        documents.append(
            {
                "id": role_uri.rsplit("/", maxsplit=1)[-1],
                "source": "ESCO v1.2.1",
                "role_uri": role_uri,
                "title": title,
                "alternative_titles": aliases,
                "isco_group": occupation["iscoGroup"],
                "description": description,
                "essential_skills": essential_skills,
                "optional_skills": optional_skills,
                "skills": skill_records,
                "index_text": text,
            }
        )

    documents.sort(key=lambda document: (document["title"].casefold(), document["id"]))
    manifest = {
        "source": "ESCO dataset v1.2.1, English CSV classification",
        "source_files": ["occupations_en.csv", "skills_en.csv", "occupationSkillRelations_en.csv"],
        "role_document_count": len(documents),
        "source_occupation_count": len(occupations),
        "source_skill_count": len(skills),
        "source_relation_count": len(relations),
        "relations_missing_skill_definition": missing_skill_definitions,
        "roles_without_skill_relations": sum(not document["skills"] for document in documents),
    }
    return documents, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("data/raw/esco"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    documents, manifest = build_documents(args.source_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    document_path = args.output_dir / "esco_roles.jsonl"
    manifest_path = args.output_dir / "esco_index_manifest.json"
    with document_path.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document, ensure_ascii=False) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(documents)} role documents to {document_path}")
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
