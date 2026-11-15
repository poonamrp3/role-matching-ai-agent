# ESCO indexing pipeline — stage 1: document preparation

This stage joins the English ESCO classification tables into one normalized role document per
occupation. It deliberately makes no embedding-model or vector-database calls.

```text
occupations_en.csv ───────────┐
occupationSkillRelations_en.csv ├─> build_role_documents.py ─> esco_roles.jsonl
skills_en.csv ─────────────────┘                                  │
                                                                  └─> next: chunk, embed, upsert
```

Run it from the project root:

```bash
python scripts/build_role_documents.py
```

It writes:

- `data/processed/esco_roles.jsonl`: one role document per ESCO occupation;
- `data/processed/esco_index_manifest.json`: reproducibility counts and source metadata.

Each document carries the ESCO role URI and ISCO group, role description, alternative titles,
essential and optional skill lists, detailed skill metadata, and a prebuilt `index_text` field.
