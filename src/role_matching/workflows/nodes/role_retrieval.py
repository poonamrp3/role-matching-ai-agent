"""Retrieve the nearest active ESCO roles for local candidate query vectors."""

from __future__ import annotations

from typing import Any

from role_matching.tools.qdrant_role_search import QdrantRoleSearchTool, as_json_ready
from role_matching.workflows.schemas import MatchRequest
from role_matching.workflows.state import RoleMatchingState

BASELINE_ROLE_LIMIT = 10


def role_retrieval_node(state: RoleMatchingState) -> dict[str, Any]:
    """Perform deterministic Qdrant cosine search; scores are retrieval signals, not fit rates."""

    try:
        request = MatchRequest.model_validate(state["match_request"])
    except KeyError:
        return {
            "status": "failed",
            "validation_errors": [*state.get("validation_errors", []), "No MatchRequest is available."],
            "workflow_events": [*state.get("workflow_events", []), "Role retrieval was not started."],
        }

    candidate_vectors = state.get("candidate_vectors", [])
    if not candidate_vectors:
        return {
            "status": "failed",
            "role_matches": [],
            "baseline_role_matches": [],
            "validation_errors": [
                *state.get("validation_errors", []),
                "No candidate query vectors are available for role retrieval.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Role retrieval was not started."],
        }

    search_tool = QdrantRoleSearchTool()
    matches: list[dict[str, Any]] = []
    baseline_matches: list[dict[str, Any]] = []
    structured_matches: list[dict[str, Any]] = []
    baseline_vectors = {str(item["submission_id"]): item["vector"]
                        for item in state.get("baseline_candidate_vectors", [])}
    query_types = {str(item["submission_id"]): item.get("query_type")
                   for item in state.get("candidate_embedding_summary", [])}
    errors: list[dict[str, str]] = []
    for candidate in candidate_vectors:
        submission_id = str(candidate["submission_id"])
        try:
            results = search_tool.search_active_roles(
                vector=list(candidate["vector"]),
                limit=BASELINE_ROLE_LIMIT,
            )
            serialized_roles = [as_json_ready(result) for result in results]
            baseline_results = results
            if query_types.get(submission_id) == "structured":
                baseline_results = search_tool.search_active_roles(
                    vector=list(baseline_vectors[submission_id]), limit=BASELINE_ROLE_LIMIT)
                structured_matches.append({"submission_id": submission_id, "roles": serialized_roles})
            baseline_matches.append({"submission_id": submission_id,
                                     "roles": [as_json_ready(result) for result in baseline_results]})
            matches.append(
                {
                    "submission_id": submission_id,
                    "roles": serialized_roles[:request.roles_per_candidate],
                }
            )
        except Exception as error:
            errors.append({"submission_id": submission_id, "error": str(error)})

    if not matches:
        return {
            "status": "failed",
            "role_matches": [],
            "baseline_role_matches": [],
            "role_retrieval_errors": errors,
            "validation_errors": [
                *state.get("validation_errors", []),
                "No ESCO roles could be retrieved for the candidate vectors.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Role retrieval failed."],
        }

    return {
        "role_matches": matches,
        "baseline_role_matches": baseline_matches,
        "structured_role_matches": structured_matches,
        "role_retrieval_errors": errors,
        "workflow_events": [
            *state.get("workflow_events", []),
            f"Retrieved up to {BASELINE_ROLE_LIMIT} baseline active ESCO roles for {len(matches)} candidate(s); "
            f"retained up to {request.roles_per_candidate} for display.",
        ],
    }
