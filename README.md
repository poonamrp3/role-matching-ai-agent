# Role Matching AI Agent

A representative, privacy-aware prototype for matching candidate application material to ESCO
occupations. It is designed as an interview demonstration of a controlled agentic workflow, not
as a production hiring decision system.

## Current capabilities

- Deterministic normalization of ESCO occupation, skill, and occupation-skill relation CSV files.
- One complete occupation per retrieval document, preserving title, description, essential skills,
  and optional skills.
- Local 512-dimensional Nomic embeddings with layer normalization, Matryoshka truncation, and L2
  normalization.
- Local Qdrant role index with cosine similarity, stable point IDs, provenance metadata, and
  `index_status: active` filtering.
- A bounded Gmail candidate-submission adapter that reads at most five messages from a configured
  submissions label.
- Encrypted local SQLite storage for Gmail OAuth token data. Tokens, OAuth client files, local
  vector databases, and generated data are excluded from Git.
- A LangGraph query-processing slice that turns a terminal recruiter command into a validated
  `MatchRequest` before any candidate-data tool is permitted to run.

## Deliberate workflow boundary

```text
Recruiter connects an applications mailbox once
  → LangGraph validates the recruiter request
  → bounded candidate-submission tool fetches approved messages
  → candidate text is extracted
  → a later LangGraph node constructs a candidate query profile
  → Nomic query embedding searches active ESCO roles in Qdrant
  → a human reviews grounded role suggestions
```

The system must not make employment decisions, treat cosine similarity as a hiring probability,
or use protected personal attributes for retrieval or ranking.

## Repository layout

```text
scripts/   Deterministic pipeline, embedding, Qdrant, Gmail, and inspection scripts
src/       Reusable tool implementations
docs/      Design decisions and implementation notes
```

The raw ESCO data, normalized records, vector matrix, local Qdrant database, and local Gmail token
database are reproducible local artifacts and intentionally excluded from version control.

## Key commands

```bash
# Build normalized role documents and retrieval documents after adding ESCO CSV files.
python scripts/build_role_documents.py
python scripts/build_retrieval_documents.py

# Generate local role embeddings.
python scripts/generate_local_embeddings.py --device cpu --batch-size 4

# Create the local Qdrant role index and inspect real similarity results.
python scripts/load_esco_vectors_to_qdrant.py
python scripts/inspect_esco_vector_similarity.py

# Validate a recruiter command through the first LangGraph slice.
python scripts/run_query_workflow.py "Process the latest five candidate submissions"
```

See the files in `docs/` for design rationale and Gmail setup instructions.

## Local Vue interface

The optional interview-demo UI is a local Vue frontend over a FastAPI boundary. It keeps private
Gmail and vector-processing data in the backend while presenting only formatted role suggestions.
See `docs/vue-ui-setup.md` for the two local launch commands.
