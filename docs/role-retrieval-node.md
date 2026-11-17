# Role retrieval node

`workflows/nodes/role_retrieval.py` receives each local 512-dimensional, L2-normalized candidate
query vector and sends it to the local `esco_roles_v1` Qdrant collection.

The Qdrant tool applies this deterministic constraint:

```text
index_status = active
```

It retrieves no more than `roles_per_candidate`, which is validated between one and five. Because
the collection uses cosine distance and both candidate and role vectors are L2-normalized, Qdrant's
returned score is the cosine similarity. It is a semantic retrieval-ranking signal, not a hiring
probability, qualification percentage, or employment decision.

The output includes original ESCO role metadata stored alongside each vector: title, description,
essential skills, and optional skills. It does not attempt to decode the candidate vector.
