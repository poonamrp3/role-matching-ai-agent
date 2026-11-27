# Querying pipeline design — LangGraph orchestration

## Decision

LangGraph is the application-level orchestration layer. The Vue interface is a client of the
workflow; it does not decide tool order, mailbox scope, retrieval limits, or the final response
shape.

```text
Recruiter request
  → input guardrails and query processing
  → Gmail connection check or secure OAuth authorization
  → bounded Gmail retrieval
  → candidate-text extraction
  → LLM extracts and validates a structured candidate profile
  → local Nomic candidate embedding
  → Qdrant active-role retrieval
  → LLM response planning from safe retrieval evidence
  → deterministic result formatting
  → recruiter-facing response for human review
```

## Why LangGraph rather than a chat UI

A chat UI can collect prompts and display results, but it should not be responsible for deciding
which systems can be accessed or in what order. The candidate-to-role workflow needs an explicit,
inspectable backend flow that enforces Gmail scope, retrieval limits, validation, and privacy
boundaries regardless of prompt wording.

LangGraph makes these transitions visible and lets deterministic nodes run before or after LLM
nodes. Structured profile extraction sends candidate text to the configured LLM endpoint. The
endpoint may forward it to a remote provider. Gmail credentials, candidate vectors and unrestricted
Qdrant payloads are not sent to the LLM.

## Shared workflow state

```text
raw_prompt
query_intent
match_request
gmail_connection_ok
submission_references       # message ID, subject, and received time only
candidate_documents         # process memory only; never returned by the API
candidate_profiles          # process memory only; never returned by the API
candidate_vectors           # process memory only; never returned by the API
baseline_role_matches
structured_role_matches
role_matches
response_plan
formatted_results
workflow_events
```

## Nodes and responsibilities

| Node | Type | Responsibility | Key boundary |
|---|---|---|---|
| `query_processing` | LLM + schema validation | Converts the recruiter prompt into a bounded `MatchRequest` | Prompt injection and unsupported actions are stopped before tool access. |
| `gmail_connection` | Deterministic service | Loads and refreshes the encrypted local Gmail credential | If no connection exists, the API starts secure browser authorization and returns a natural-language response. |
| `gmail_retrieval` | Deterministic service | Retrieves up to five references from the fixed submissions label | Date and attachment filters come only from validated request fields. |
| `candidate_text_extraction` | Deterministic service | Extracts approved email and supported attachment text | The backend keeps the extracted text in workflow memory. |
| `candidate_profile` | LLM + schema validation | Extracts skills and experience into a structured profile | Candidate text is sent to the configured LLM; schema validation does not verify extracted facts. |
| `candidate_embedding` | Deterministic service | Creates a local Nomic `search_query` vector | The same embedding model and normalization policy are used as the role index. |
| `role_retrieval` | Deterministic service | Searches active ESCO role vectors in Qdrant | Cosine similarity ranks retrieval results; it is not a hiring score. |
| `response_planning` | LLM + schema validation | Chooses which safe fields to show for the recruiter request | Receives only safe role titles, field availability, and the validated request. |
| `result_formatting` | Deterministic service | Renders retrieved data according to the validated response plan | Cannot invent roles, skills, candidate facts, or scores. |

## Tool policy

The LLM does not freely select tools. Gmail access, embedding, vector search, and output
formatting are graph-controlled operations. LLM calls interpret the recruiter request, extract a
structured candidate profile and plan presentation. The presentation-planning call receives only
the limited post-retrieval context described above. Baseline mode bypasses profile extraction.

## Query-time sequence

```text
candidate email and supported attachment
  → extracted candidate text
  → LLM extracts a structured skills and experience profile
  → local Nomic `search_query` vector
  → Qdrant top-K active ESCO roles
  → field-level response plan
  → formatted role suggestions
  → human reviewer
```

## Current evaluation boundary

This prototype validates the controlled end-to-end workflow. Formal role-relevance metrics require
a labelled candidate-to-role evaluation set and human-review protocol; they are the next
evaluation step, not a performance claim of the current demonstration.
