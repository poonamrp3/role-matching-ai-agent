"""Retrieve the nearest active ESCO roles for local candidate query vectors."""

from __future__ import annotations

from typing import Any

from role_matching.tools.qdrant_role_search import QdrantRoleSearchTool, as_json_ready
from role_matching.workflows.schemas import MatchRequest
from role_matching.workflows.state import RoleMatchingState


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
            "validation_errors": [
                *state.get("validation_errors", []),
                "No candidate query vectors are available for role retrieval.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Role retrieval was not started."],
        }

    search_tool = QdrantRoleSearchTool()
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for candidate in candidate_vectors:
        submission_id = str(candidate["submission_id"])
        try:
            results = search_tool.search_active_roles(
                vector=list(candidate["vector"]),
                limit=request.roles_per_candidate,
            )
            matches.append(
                {
                    "submission_id": submission_id,
                    "roles": [as_json_ready(result) for result in results],
                }
            )
        except Exception as error:
            errors.append({"submission_id": submission_id, "error": str(error)})

    if not matches:
        return {
            "status": "failed",
            "role_matches": [],
            "role_retrieval_errors": errors,
            "validation_errors": [
                *state.get("validation_errors", []),
                "No ESCO roles could be retrieved for the candidate vectors.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Role retrieval failed."],
        }

    return {
        "role_matches": matches,
        "role_retrieval_errors": errors,
        "workflow_events": [
            *state.get("workflow_events", []),
            f"Retrieved up to {request.roles_per_candidate} active ESCO role(s) for {len(matches)} candidate(s).",
        ],
    }
