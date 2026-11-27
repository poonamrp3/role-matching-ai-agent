# Role retrieval node

`workflows/nodes/role_retrieval.py` receives each local 512-dimensional, L2-normalized candidate
query vector and sends it to the local `esco_roles_v1` Qdrant collection.

The Qdrant tool applies this deterministic constraint:

```text
index_status = active
```

It retrieves up to ten distinct active roles into `baseline_role_matches` in workflow state. Each
entry is associated with a submission ID and includes the role ID, metadata, and cosine similarity.
When a structured profile was used, the full-text baseline is searched independently and the
structured-query top ten is held in `structured_role_matches`. The terminal runner includes both
lists in its JSON output; they are not automatically saved to disk or exposed by the API. The usual
`role_matches` is limited to `roles_per_candidate`, validated between
one and five, for downstream display. Because
the collection uses cosine distance and both candidate and role vectors are L2-normalized, Qdrant's
returned score is the cosine similarity. It is a semantic retrieval-ranking signal, not a hiring
probability, qualification percentage, or employment decision.

The output includes original ESCO role metadata stored alongside each vector: title, description,
essential skills, and optional skills. It does not attempt to decode the candidate vector.
