# Result formatting node

`workflows/nodes/result_formatting.py` converts raw Qdrant role payloads into concise candidate
cards for a future UI or terminal response.

Each card includes only:

- submission ID, received time, and subject;
- ranked role title;
- cosine similarity labelled as `semantic_similarity`;
- ESCO role description; and
- the first five ESCO essential skills.

It deliberately omits raw candidate email and attachment text, the 512-dimensional candidate
vector, optional-skill lists, and any invented explanation. It includes a fixed human-review note:
semantic similarity is a retrieval signal, not a fit percentage or hiring decision.
