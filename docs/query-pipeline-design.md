# Querying pipeline design — LangGraph orchestration

## Decision

LangGraph is the application-level orchestration layer. A chat UI, including OpenWebUI, may be
connected later as an optional client, but it does not decide tool order, data scope, or final
validation.

```text
Optional UI / API request
          |
          v
      LangGraph workflow
          |
          +-- Gmail retrieval (later, constrained)
          +-- candidate-profile extraction and validation
          +-- Nomic query embedding
          +-- Qdrant role retrieval
          +-- deterministic evidence ranking
          +-- constrained LLM explanation
          +-- human-review response
```

## Why not let a chat UI orchestrate the workflow?

OpenWebUI can expose tools and function schemas, but it is primarily a user interface. The
candidate-to-role use case needs a backend workflow that is explicit, testable, and able to
enforce non-negotiable rules regardless of prompt wording.

LangGraph does not make the model intrinsically smarter or faster. It makes control flow visible
and reliable: deterministic nodes can run before or after LLM nodes, failures can be handled,
and each state transition can be inspected.

## Graph state

```text
request_id
email_references             # IDs only; do not put raw email data in logs
candidate_text
candidate_profile            # schema-validated structured data
candidate_query_text
candidate_vector
retrieved_roles
ranked_role_matches
grounded_explanation
validation_errors
audit_events
```

## Nodes and responsibilities

| Node | Type | Responsibility | Important guardrail |
|---|---|---|---|
| `fetch_submissions` | Deterministic service | Fetch at most five approved Gmail submissions | Fixed label/query and hard limit; no whole-mailbox access. |
| `extract_candidate_text` | Deterministic service | Extract approved email and attachment text | Treat all email text as untrusted data. |
| `build_candidate_profile` | LLM + schema validation | Extract skills, responsibilities, projects, and experience | Missing facts remain unknown; exclude protected attributes. |
| `build_query_text` | Deterministic | Construct Nomic `search_query:` input | Prior job title is only one signal, not the query. |
| `retrieve_roles` | Deterministic service | Query Qdrant for top K ESCO role vectors | Retrieval is limited to the known index. |
| `rank_evidence` | Deterministic | Combine semantic retrieval with skill coverage | Ranking score is not a hiring probability. |
| `explain_matches` | Constrained LLM | Explain top matches and unverified gaps | May refer only to retrieved roles and source evidence. |
| `validate_response` | Deterministic | Check IDs, schema, score bounds, and citations | Cannot recommend a role that was not retrieved. |
| `human_review` | Human | Review output before an employment decision | System never makes a hiring decision. |

## Deliberate tool policy

The LLM must not freely choose every tool. Gmail access, embedding, vector search, ranking, and
validation are graph-controlled nodes. The LLM is used only where language understanding adds
value: extracting a profile from unstructured text and producing a grounded explanation after
retrieval.

## Query-time sequence

```text
candidate email/resume
  → validated candidate profile
  → Nomic search_query vector
  → Qdrant top 10 ESCO roles
  → deterministic skill/evidence ranking
  → constrained explanation for top 3–5 roles
  → human reviewer
```

## Evaluation before live candidate processing

Use a dedicated applications mailbox with consented test submissions. Each test should assert that:

- an AI/RAG profile retrieves AI/data-related occupations;
- role title mismatch does not prevent a relevant semantic match;
- missing essential skills are shown as gaps, not invented;
- only retrieved role IDs occur in the final answer;
- protected attributes never enter the retrieval text or score.
