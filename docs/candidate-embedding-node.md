# Candidate embedding node

`workflows/nodes/candidate_embedding.py` consumes the in-memory candidate text produced by the
previous node and creates vectors locally with `nomic-ai/nomic-embed-text-v1.5`.

It uses the query prefix:

```text
search_query: <candidate text>
```

Then it follows the same compatibility procedure used for the stored ESCO document vectors:

```text
raw Nomic vector -> layer normalization -> truncate to 512 dimensions -> L2 normalization
```

The resulting 512-dimensional, unit-length vector is kept only in `candidate_vectors` state for
the next Qdrant node. Terminal output reports dimensions, vector norm, and input-token count—not
the vector values or candidate text. Candidate text that exceeds the Nomic sequence limit is
rejected rather than silently truncated; a future chunking policy can handle such cases explicitly.
