"""Shared data contracts used by role-matching workflow nodes."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SUPPORTED_ACTION = "match_candidate_submissions"
MAX_CANDIDATES = 5
MAX_ROLES_PER_CANDIDATE = 5
PresentationMode = Literal["titles_only", "concise", "detailed"]
CandidateField = Literal["display_name", "declared_role", "received_at", "attachment_count"]


class QueryIntent(BaseModel):
    """Untrusted LLM interpretation of a recruiter command.

    The application never sends this object straight to Gmail or Qdrant. It must first be
    converted into a validated ``MatchRequest``.
    """

    model_config = ConfigDict(extra="forbid")

    action: str | None = Field(default=None, description="Requested workflow action, if supported.")
    candidate_limit: int | None = Field(
        default=None,
        description="Number of candidate submissions requested, if stated.",
    )
    roles_per_candidate: int | None = Field(
        default=None,
        description="Number of roles requested for each candidate, if stated.",
    )
    received_after: date | None = Field(default=None)
    received_before: date | None = Field(default=None)
    require_attachment: bool | None = Field(default=None)
    presentation_preference: PresentationMode | None = Field(default=None)
    request_summary: str = Field(min_length=1, max_length=300)
    needs_clarification: bool = Field(
        description="True when the request is ambiguous or outside supported scope."
    )
    clarification_question: str | None = Field(default=None, max_length=300)


class MatchRequest(BaseModel):
    """Trusted request constructed only after deterministic policy validation."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["match_candidate_submissions"] = SUPPORTED_ACTION
    candidate_limit: int = Field(ge=1, le=MAX_CANDIDATES)
    roles_per_candidate: int = Field(ge=1, le=MAX_ROLES_PER_CANDIDATE)
    received_after: date | None = None
    received_before: date | None = None
    require_attachment: bool | None = None
    presentation_preference: PresentationMode | None = None
    request_summary: str = Field(min_length=1, max_length=300)


class ResponsePlan(BaseModel):
    """Field-level display plan produced from safe retrieval evidence only."""

    model_config = ConfigDict(extra="forbid")

    candidate_fields: list[CandidateField] = Field(default_factory=list, max_length=4)
    roles_to_show: int = Field(ge=1, le=MAX_ROLES_PER_CANDIDATE)
    description_max_chars: int = Field(ge=0, le=500)
    skills_per_role: int = Field(ge=0, le=MAX_ROLES_PER_CANDIDATE)
    include_similarity: bool
