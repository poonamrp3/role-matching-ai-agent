"""Deterministic Gmail credential-readiness node.

This node decrypts the locally stored OAuth credential and refreshes it if Google marks the access
token expired. It does not list messages or expose OAuth material to graph state.
"""

from __future__ import annotations

import os
from typing import Any

from role_matching.tools.gmail_candidate_submissions import (
    GmailConnectionRequired,
    GmailCredentialStore,
)
from role_matching.workflows.state import RoleMatchingState


GMAIL_CONNECTION_ID_ENV = "GMAIL_CONNECTION_ID"
DEFAULT_GMAIL_CONNECTION_ID = "demo-applications-mailbox"


def gmail_connection_node(state: RoleMatchingState) -> dict[str, Any]:
    """Verify that a valid encrypted Gmail connection is available for later bounded retrieval."""

    connection_id = os.getenv(GMAIL_CONNECTION_ID_ENV, DEFAULT_GMAIL_CONNECTION_ID)
    try:
        result = GmailCredentialStore(connection_id=connection_id).load_with_status()
        event = (
            "Expired Gmail access token refreshed and encrypted token store updated."
            if result.access_token_refreshed
            else "Encrypted Gmail credentials loaded; existing access token remains valid."
        )
        return {
            "gmail_connection_ok": True,
            "gmail_access_token_refreshed": result.access_token_refreshed,
            "workflow_events": [*state.get("workflow_events", []), event],
        }
    except GmailConnectionRequired as error:
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
                "Gmail connection is unavailable; no mailbox data was accessed.",
            ],
        }
    except Exception as error:
        return {
            "gmail_connection_ok": False,
            "status": "needs_clarification",
            "response_type": "gmail_connection_unavailable",
            "assistant_message": (
                "I could not check the applications mailbox connection just now. Please send "
                "the request again in a moment."
            ),
            "validation_errors": state.get("validation_errors", []),
            "workflow_events": [
                *state.get("workflow_events", []),
                "Gmail credential check failed before mailbox retrieval.",
            ],
        }
