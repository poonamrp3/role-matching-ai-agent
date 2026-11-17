"""Deterministic, pre-LLM guardrails for recruiter requests.

These checks are intentionally simple and auditable. They stop clearly off-task or prompt-
injection-style input before it can reach the local LLM, Gmail, Qdrant, or candidate data.
"""

from __future__ import annotations


SAFE_CLARIFICATION_MESSAGE = (
    "I’m here to help with candidate-submission matching. You can ask me to process recent "
    "applications, retrieve role suggestions, or explain the ESCO skills associated with a "
    "suggested role."
)

_TASK_TERMS = ("candidate", "submission", "role", "match", "skill", "gmail", "application")
_INJECTION_TERMS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal instructions",
    "jailbreak",
)


def blocked_request_reason(prompt: str) -> str | None:
    """Return a safe reason when a prompt must not be sent to the LLM.

    This is not a content-moderation classifier. It is a narrow workflow boundary: requests
    outside the application's authorised role-matching functions are declined safely.
    """

    normalized = " ".join(prompt.lower().split())
    if any(term in normalized for term in _INJECTION_TERMS):
        return "Prompt-injection-style instruction detected."
    if not any(term in normalized for term in _TASK_TERMS):
        return "Request is outside the role-matching workflow."
    return None


def safe_guardrail_response(reason: str) -> str:
    """Return a calm, recruiter-facing response without exposing policy internals."""

    if "injection" in reason.lower():
        return (
            "I can’t change my workflow instructions or reveal internal configuration. "
            "I can help process candidate submissions, retrieve role suggestions, or explain "
            "the ESCO skills associated with a suggested role."
        )
    return SAFE_CLARIFICATION_MESSAGE
