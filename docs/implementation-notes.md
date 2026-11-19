# Candidate-to-role agent — implementation notes

## Stage 1 — ESCO data preparation and normalization

### Goal

Convert the public ESCO occupation, skill, and occupation-to-skill relationship CSV files
into a consistent internal role-document format that is ready for further processing.

### What I did

1. Selected the English ESCO v1.2.1 classification export as the public occupational data source.
2. Used three source tables:
   - `occupations_en.csv` for occupation titles, descriptions, alternative labels, and ISCO groups;
   - `occupationSkillRelations_en.csv` for occupation-to-skill links and their `essential` or
     `optional` relationship type;
   - `skills_en.csv` for skill metadata and descriptions.
3. Wrote `scripts/build_role_documents.py` to join and normalize those records.
4. Produced one JSONL role document per ESCO occupation in `data/processed/esco_roles.jsonl`.
5. Produced `data/processed/esco_index_manifest.json` to retain source information and data
   quality counts.

### Methods used

| Method | Implementation | Reason |
|---|---|---|
| CSV ingestion | Python standard-library `csv.DictReader` with UTF-8 BOM handling | Reads the published files without changing their meaning. |
| Referential join | `occupationUri` joins to the occupation URI; `skillUri` joins to the skill URI | Uses ESCO's stable identifiers rather than unreliable text matching. |
| Whitespace normalization | Strip/collapse whitespace in text fields | Removes formatting noise while preserving content. |
| Alias parsing | Split ESCO alternative labels on line breaks | Makes aliases searchable and usable as structured metadata. |
| Skill classification | Use ESCO `relationType` to separate `essential` and `optional` skills | Preserves the source taxonomy's explicit distinction. |
| Deduplication and stable sorting | Deduplicate labels and sort case-insensitively | Gives repeatable output across runs. |
| Retrieval-text construction | Combine title, aliases, description, essential skills, and optional skills into `index_text` | Creates an embedding-ready text view while retaining structured fields. |

### Why deterministic processing is stronger here

ESCO is a structured, authoritative dataset with documented columns and stable URIs. The
transformation is a known database-style operation, not an ambiguous language-understanding
task. A deterministic pipeline is therefore the stronger first choice because it is:

- **Reproducible:** the same input files always produce the same normalized documents.
- **Auditable:** every output field can be traced to a source CSV field or an explicit rule.
- **Accurate:** it uses ESCO's URI relationships rather than asking a model to guess which
  skill belongs to which occupation.
- **Testable:** row counts, missing joins, and role-to-skill coverage can be asserted automatically.
- **Cost- and latency-efficient:** no model invocation is required for a rule-based join.
- **Safe for a high-impact domain:** no generative model silently changes source classifications
  before candidate-to-role matching begins.

An LLM is valuable later for genuinely ambiguous inputs—for example, proposing a mapping for an
unknown vendor CSV, summarizing a long custom job description, or routing records with missing
fields. It should propose a mapping that is then schema-validated and reviewed; it should not
replace the deterministic ESCO join.

### Output structure

Each line of `data/processed/esco_roles.jsonl` is one independent JSON document:

```json
{
  "id": "ESCO occupation UUID",
  "source": "ESCO v1.2.1",
  "role_uri": "original occupation URI",
  "title": "data scientist",
  "alternative_titles": ["data expert"],
  "isco_group": "2511",
  "description": "Source role description",
  "essential_skills": ["data engineering", "statistics"],
  "optional_skills": ["business intelligence"],
  "skills": [{"uri": "...", "label": "...", "relation_type": "essential"}],
  "index_text": "Embedding-ready derived text"
}
```

`index_text` is a derived retrieval field. The original structured fields remain the source of
truth for filters, evidence, and later explanation.

### Validation completed

| Check | Result |
|---|---:|
| Source occupations | 3,043 |
| Source skills | 13,960 |
| Source occupation-to-skill relations | 126,051 |
| Normalized role documents | 3,043 |
| Relations with missing skill definitions | 0 |
| Roles without skill relations | 0 |

## Stage 2 — Retrieval-document design and chunking

### Goal

Create the exact text units that will later be embedded and searched. A retrieval document is
not merely a raw CSV row: it is a deliberately constructed semantic unit with the information a
matching query needs.

### Decision made

Use **one complete ESCO occupation as one retrieval document**. Each document contains the role
title, alternative titles, description, essential skills, and optional skills.

I checked the role-document lengths against a 1,200-word chunking threshold. Every ESCO role was
substantially shorter than that threshold, so chunking was not necessary. Each role is already a
small, self-contained unit in which the title, description, and required skills belong together.
Keeping the full role as one retrieval document preserves that context during semantic search.

Section chunking can be introduced later if organization-specific role descriptions become much
longer or retrieval evaluation shows that it improves precision.

### Transformation

```text
Normalized ESCO role record
  → labelled embedding text
  → retrieval document with a stable parent-role reference
```

The new retrieval document holds `document_id`, `parent_role_id`, `chunk_index`, `chunk_type`,
`embedding_text`, a SHA-256 content fingerprint, and structured metadata. The fingerprint lets a
later indexer detect documents whose text has changed and needs re-embedding.

### Why this matters

- It establishes the semantic unit before selecting an embedding model.
- It preserves complete role context for reliable candidate-to-role matching.
- It creates stable identifiers and metadata for traceable search results.
- It makes the future index update process efficient and auditable.

## Stage 3 — Local embedding generation

### Goal

Convert each Stage 2 retrieval document into a fixed-length numerical vector, without requiring
a hosted API or sending role data outside the local machine.

### Model and embedding policy

- Model: `nomic-ai/nomic-embed-text-v1.5` running locally on CPU.
- Input prefix: `search_document:` because ESCO roles are index documents, not user queries.
- Vector size: 512 dimensions using the model's Matryoshka representation.
- Post-processing: layer normalization, truncation to 512 dimensions, then L2 normalization.

### Output

`scripts/generate_local_embeddings.py` writes:

- `data/embeddings/esco_role_vectors.npz`: document IDs paired with a float32 vector matrix;
- `data/embeddings/esco_embedding_manifest.json`: model identity, revision, dimensions, token
  check, batch size, input fingerprint, and generation time.

The vectors are then loaded into Qdrant in the next stage. The manifest is essential:
vectors produced with a different model, dimension, prefix, or preprocessing rule are not
directly comparable and must not be mixed in the same collection.

## Stage 4 — Vector-database ingestion and retrieval

Qdrant stores the Stage 3 vectors in a local persistent collection named `esco_roles_v1`. The
collection uses 512-dimensional cosine vectors and payload metadata containing the role identity,
ESCO source/version, skills, and content fingerprint.

### Stage 4.1 — Vector ingestion

The completed embedding matrix is loaded into a persistent local Qdrant collection named
`esco_roles_v1`. The ingestion loader validates the vector matrix and maps every vector back to a
retrieval document and canonical ESCO role. It removes four exact source duplicates by stable
document ID after verifying that both the documents and vectors are identical, producing 3,039
unique points.

Every point has `record_type: taxonomy_reference` and `index_status: active` in its payload.
The role-retrieval node filters to active points. Here, active means included in the current ESCO
reference index; it is not an assertion that a real-world vacancy is open.

## Stage 5 — Query orchestration and recruiter UI

LangGraph is the backend control plane for the completed query workflow. It controls input
guardrails, request validation, Gmail scope, candidate-text extraction, local Nomic embedding,
active-role retrieval in Qdrant, response planning, and deterministic result formatting. The Vue
UI is a client of this workflow; it does not decide tool order or data scope.

```text
Recruiter request
→ query processing and guardrails
→ Gmail connection check or secure OAuth authorization
→ bounded Gmail retrieval
→ candidate-text extraction
→ Nomic candidate embedding
→ Qdrant active-role retrieval
→ LLM response planning
→ deterministic result formatting
→ recruiter UI
```

## Stage 5.1 — Candidate-submission tool boundary

The query pipeline uses a provider-independent `CandidateSubmissionTool` contract. It exposes a
bounded listing operation and a separate extraction operation. The Gmail implementation follows
that contract, so LangGraph remains independent of Gmail-specific API details.

The Gmail adapter retrieves only messages from the configured `CandidateSubmissions` label and
never accepts an arbitrary mailbox search from recruiter text.
