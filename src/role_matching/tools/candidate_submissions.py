"""Provider-independent contract for bounded candidate-submission access."""

from __future__ import annotations

from datetime import date
from dataclasses import asdict, dataclass
from typing import Protocol


MAX_SUBMISSIONS_PER_REQUEST = 5


@dataclass(frozen=True)
class SubmissionReference:
    """Listing metadata; raw résumé text is deliberately excluded."""

    submission_id: str
    received_at: str
    subject: str


@dataclass(frozen=True)
class CandidateText:
    """Approved email and attachment text for one submission."""

    submission_id: str
    candidate_text: str
    attachment_count: int


class CandidateSubmissionTool(Protocol):
    """The small provider-independent interface LangGraph will call."""

    def fetch_latest_submissions(
        self,
        limit: int = MAX_SUBMISSIONS_PER_REQUEST,
        received_after: date | None = None,
        received_before: date | None = None,
        require_attachment: bool | None = None,
    ) -> list[SubmissionReference]: ...

    def extract_candidate_text(self, submission_id: str) -> CandidateText: ...


def as_json_ready(value: SubmissionReference | CandidateText) -> dict:
    return asdict(value)
