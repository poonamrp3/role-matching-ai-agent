"""Shared, serializable state for the top-level role-matching LangGraph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class RoleMatchingState(TypedDict, total=False):
    """State shared by workflow nodes; credentials are always excluded.

    Candidate documents are kept only in process memory for this local, non-checkpointed prototype
    and are deliberately omitted from terminal output and logs.
    """

    raw_prompt: str
    llm_connection_ok: bool
    available_models: list[str]
    query_intent: dict[str, Any]
    match_request: dict[str, Any]
    gmail_connection_ok: bool
    gmail_access_token_refreshed: bool
    submission_references: list[dict[str, str]]
    candidate_documents: list[dict[str, Any]]
    candidate_extraction_summary: list[dict[str, Any]]
    candidate_extraction_errors: list[dict[str, str]]
    candidate_vectors: list[dict[str, Any]]
    candidate_embedding_summary: list[dict[str, Any]]
    candidate_embedding_errors: list[dict[str, str]]
    role_matches: list[dict[str, Any]]
    role_retrieval_errors: list[dict[str, str]]
    response_plan: dict[str, Any]
    response_planning_error: str
    formatted_results: list[dict[str, Any]]
    assistant_message: str
    response_type: str
    status: Literal["pending", "completed", "needs_clarification", "failed"]
    validation_errors: list[str]
    workflow_events: list[str]
