# Stage 4 design — ESCO role vector store

## Purpose

Qdrant is the vector database for the candidate-to-role agent. It does not generate embeddings.
It stores the 512-dimensional Nomic vectors produced in Stage 3 and retrieves the nearest role
vectors when the agent submits a candidate-profile vector.

```text
Candidate profile text --Nomic--> query vector
                                     |
                                     v
                         Qdrant cosine-similarity search
                                     |
                                     v
                    top matching ESCO role documents + metadata
```

## Local deployment decision

Use Qdrant's free local persistent mode for the prototype. The role vectors remain on this
machine and do not require a cloud account, Docker, or a paid API. Qdrant Cloud is an optional
later deployment option.

## Collection contract

| Field | Value | Reason |
|---|---|---|
| Collection name | `esco_roles_v1` | Versioned so a future embedding-model change can create a new collection safely. |
| Vector size | `512` | Matches the Stage 3 Nomic output. |
| Distance | Cosine | Vectors are L2-normalized; cosine compares semantic direction. |
| Point identity | UUID derived deterministically from `document_id` | Repeat indexing updates the same role instead of creating duplicates. |

## Qdrant point shape

```json
{
  "id": "deterministic UUID",
  "vector": [0.018, -0.294, "... 510 more values"],
  "payload": {
    "document_id": "esco-role:<role-id>:full",
    "parent_role_id": "<role-id>",
    "source": "ESCO v1.2.1",
    "role_uri": "original ESCO URI",
    "title": "data scientist",
    "alternative_titles": ["data expert"],
    "isco_group": "2511",
    "essential_skills": ["data engineering", "statistics"],
    "optional_skills": ["business intelligence"],
    "content_sha256": "source text fingerprint",
    "record_type": "taxonomy_reference",
    "index_status": "active"
  }
}
```

The source role text remains in the Stage 2 retrieval-document file. Qdrant carries the metadata
needed to identify, filter, and explain a retrieved role without treating the embedding itself as
the source of truth.

## Future update policy

ESCO is a reference taxonomy, not a live vacancy feed. Therefore it has source version and
content fingerprint metadata, not a fabricated job-expiry date.

```text
same role URI + same content hash  -> skip
same role URI + changed hash       -> re-embed and upsert, replacing its vector
new role URI                       -> embed and insert
new ESCO release                   -> re-run the source comparison
```

For actual organization vacancies later, create a separate `active_organization_roles_v1`
collection with genuine `posted_at`, `expires_at`, and `status` metadata. It should never be
mixed with ESCO reference records.
