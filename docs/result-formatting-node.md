# Result formatting node

`workflows/nodes/result_formatting.py` converts retrieved Qdrant role payloads into concise
candidate cards for the Vue recruiter UI.

Each card includes only:

- the candidate fields permitted by the response plan;
- ranked role title; and
- ESCO descriptions, essential skills, and cosine similarity only when the response plan permits
  them.

Cosine similarity is hidden by default and appears only in the UI's **Programmatic details**
section when it was requested.

It deliberately omits raw candidate email and attachment text, the 512-dimensional candidate
vector, optional-skill lists, and any invented explanation. It includes a fixed human-review note:
semantic similarity is a retrieval signal, not a fit percentage or hiring decision.
