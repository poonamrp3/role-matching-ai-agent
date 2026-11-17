# LangGraph query-processing node

## Position in the system graph

The top-level system graph is `src/role_matching/workflows/graph.py`. It currently contains one
node: `query_processing`, implemented in `src/role_matching/workflows/nodes/query_processing.py`.
It turns a terminal-provided recruiter command into a validated `MatchRequest`.

```text
top-level graph
  -> query_processing node
       (verify LLM -> understand prompt -> validate request)
```

The internal steps are ordinary functions rather than a nested graph because they are currently a
simple sequence. The query-processing node does not access Gmail, read candidate material, create
embeddings, or query Qdrant yet.

`verify_llm_connection` is a deterministic preflight node. It verifies the local model proxy and
configured model before the LLM sees the prompt. `understand_query` is the only LLM node in this
first slice. It returns a `QueryIntent`, which is untrusted. `validate_match_request` applies the
application policy and creates the trusted request object only when it is valid.

## Why two request schemas?

The LLM is allowed to interpret language but is not trusted to set execution scope. Its
`QueryIntent` can include unsupported values, such as a candidate limit of ten. Deterministic
validation rejects those values instead of silently changing them. `MatchRequest` therefore has
only the allowed action and limits from one to five.

## Run

```bash
python scripts/run_query_workflow.py "Process the latest five candidate submissions and show five roles for each"
```

Expected successful shape:

```json
{
  "status": "completed",
  "match_request": {
    "action": "match_candidate_submissions",
    "candidate_limit": 5,
    "roles_per_candidate": 5
  }
}
```

An over-limit or ambiguous request returns `needs_clarification` and ends before any external
candidate-data tool can run.
