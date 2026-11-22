# Qdrant stage 2 — ESCO role-vector ingestion

## Purpose

Nomic creates vectors; Qdrant stores those vectors alongside structured role payloads and performs
nearest-neighbour search. The embedding model does not itself retain an index or return the most
similar ESCO roles.

## Input validation

Before creating the collection, `scripts/load_esco_vectors_to_qdrant.py` verifies that:

- the vector matrix is finite float32 with 512 dimensions;
- every row is L2-normalized;
- vector document IDs align exactly with the retrieval-document file;
- each retrieval document maps to a canonical role;
- duplicates are only removed when the role document and vector are exactly identical.

ESCO v1.2.1 has 3,043 occupation rows but four exact duplicate URIs. The loader retains one copy
of each, resulting in 3,039 indexed roles. It fails rather than silently overwriting if a duplicate
ID has different document content or vector values.

## Payload lifecycle metadata

Every Qdrant point receives:

```json
{
  "record_type": "taxonomy_reference",
  "index_status": "active",
  "source": "ESCO v1.2.1"
}
```

For ESCO, `index_status: active` means the reference role is included in the current searchable
index; it does not claim an employer has an open vacancy. Future organization job postings will
need separate `posting_status`, `posted_at`, and `expires_at` fields.

## Vector and payload indexes

The loader declares a keyword payload index for `index_status`. Embedded Qdrant local mode reports
that payload indexes have no effect, and the present 3,039-role prototype has no HNSW vector
segment (`indexed_vectors_count` is zero), so it uses exact vector search. This is acceptable at
the current scale. For a larger deployment, run Qdrant Server and configure its HNSW and payload
indexes; HNSW is a graph-based approximate-nearest-neighbour index that speeds up similarity
search as the collection grows.

## Run

```bash
cd /Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing
python scripts/load_esco_vectors_to_qdrant.py
```

The loader creates local persistent storage under `data/qdrant/` and writes an ingestion manifest
after checking the point count and querying the first vector with an `index_status = active`
filter.

## Inspect real similarity

The similarity demo uses two actual Nomic ESCO vectors and then asks Qdrant for the nearest active
role vectors:

```bash
python scripts/inspect_esco_vector_similarity.py
```

It defaults to comparing `data scientist` and `software developer`. The cosine score measures
semantic proximity in the embedding space; it is useful for ranking but is not a candidate-fit
percentage or an employment decision.
