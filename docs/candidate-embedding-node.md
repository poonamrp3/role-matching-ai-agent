# Candidate embedding node

`workflows/nodes/candidate_embedding.py` creates vectors locally with `nomic-ai/nomic-embed-text-v1.5`.
It embeds both the original full text for the baseline and a query constructed from the validated
profile. Profile extraction failure is reported and does not silently fall back to full text.

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
