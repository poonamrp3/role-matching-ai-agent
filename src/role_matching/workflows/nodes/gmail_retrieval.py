"""Bounded retrieval of candidate-submission message references from Gmail."""

from __future__ import annotations

import os
from typing import Any

from role_matching.tools.candidate_submissions import as_json_ready
from role_matching.tools.gmail_candidate_submissions import (
    GmailCandidateSubmissionTool,
    GmailConnectionRequired,
    GmailCredentialStore,
)
from role_matching.workflows.schemas import MatchRequest
from role_matching.workflows.state import RoleMatchingState


GMAIL_SUBMISSIONS_LABEL_ENV = "GMAIL_SUBMISSIONS_LABEL"
DEFAULT_GMAIL_SUBMISSIONS_LABEL = "CandidateSubmissions"
GMAIL_CONNECTION_ID_ENV = "GMAIL_CONNECTION_ID"
DEFAULT_GMAIL_CONNECTION_ID = "demo-applications-mailbox"


def gmail_retrieval_node(state: RoleMatchingState) -> dict[str, Any]:
    """Retrieve up to five references from the configured submissions label.

    This is intentionally metadata-only. Candidate email bodies and attachments are handled by a
    later extraction node, so they never enter this node's output or LangGraph state.
    """

    try:
        request = MatchRequest.model_validate(state["match_request"])
    except KeyError:
        return {
            "status": "failed",
            "validation_errors": [*state.get("validation_errors", []), "No MatchRequest is available."],
            "workflow_events": [*state.get("workflow_events", []), "Gmail retrieval was not started."],
        }

    label = os.getenv(GMAIL_SUBMISSIONS_LABEL_ENV, DEFAULT_GMAIL_SUBMISSIONS_LABEL)
    connection_id = os.getenv(GMAIL_CONNECTION_ID_ENV, DEFAULT_GMAIL_CONNECTION_ID)
    try:
        tool = GmailCandidateSubmissionTool(
            label=label,
            credential_store=GmailCredentialStore(connection_id=connection_id),
        )
        references = tool.fetch_latest_submissions(
            limit=request.candidate_limit,
            received_after=request.received_after,
            received_before=request.received_before,
            require_attachment=request.require_attachment,
        )
        if not references:
            date_description = (
                f" between {request.received_after.isoformat()} and {request.received_before.isoformat()}"
                if request.received_after and request.received_before
                else ""
            )
            return {
                "submission_references": [],
                "assistant_message": (
                    f"No candidate submissions were found{date_description} in the approved Gmail label. "
                    "No candidate content was opened."
                ),
                "workflow_events": [
                    *state.get("workflow_events", []),
                    "The bounded Gmail query returned no matching submission references.",
                ],
            }
        return {
            "submission_references": [as_json_ready(reference) for reference in references],
            "workflow_events": [
                *state.get("workflow_events", []),
                f"Retrieved {len(references)} submission reference(s) from the configured Gmail label.",
            ],
        }
    except GmailConnectionRequired:
        return {
            "gmail_connection_ok": False,
            "status": "needs_clarification",
            "response_type": "gmail_connection_required",
            "assistant_message": (
                "I need a secure connection to the approved applications mailbox before I can "
                "retrieve candidate submissions."
            ),
            "validation_errors": state.get("validation_errors", []),
            "workflow_events": [
                *state.get("workflow_events", []),
                "Gmail retrieval stopped because the connection needs reconnection.",
            ],
        }
    except Exception:
        return {
            "status": "needs_clarification",
            "response_type": "gmail_mailbox_unavailable",
            "assistant_message": (
                "I could not retrieve candidate submissions from the applications mailbox just "
                "now. Please send the request again in a moment."
            ),
            "validation_errors": state.get("validation_errors", []),
            "workflow_events": [*state.get("workflow_events", []), "Gmail retrieval node failed."],
        }
