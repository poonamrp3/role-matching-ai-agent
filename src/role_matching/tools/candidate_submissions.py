"""A provider-independent candidate-submission tool and local demo implementation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
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

    def fetch_latest_submissions(self, limit: int = MAX_SUBMISSIONS_PER_REQUEST) -> list[SubmissionReference]: ...

    def extract_candidate_text(self, submission_id: str) -> CandidateText: ...


class LocalCandidateSubmissionTool:
    """Read fictional submissions from JSON while developing the workflow safely."""

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path
        self._submissions = self._load_fixture()

    def fetch_latest_submissions(self, limit: int = MAX_SUBMISSIONS_PER_REQUEST) -> list[SubmissionReference]:
        if not 1 <= limit <= MAX_SUBMISSIONS_PER_REQUEST:
            raise ValueError(f"limit must be between 1 and {MAX_SUBMISSIONS_PER_REQUEST}")
        newest_first = sorted(
            self._submissions,
            key=lambda submission: self._parse_timestamp(submission["received_at"]),
            reverse=True,
        )
        return [
            SubmissionReference(
                submission_id=submission["submission_id"],
                received_at=submission["received_at"],
                subject=submission["subject"],
            )
            for submission in newest_first[:limit]
        ]

    def extract_candidate_text(self, submission_id: str) -> CandidateText:
        submission = next((item for item in self._submissions if item["submission_id"] == submission_id), None)
        if submission is None:
            raise KeyError(f"Unknown submission_id: {submission_id}")
        sections = ["EMAIL BODY:\n" + self._required_text(submission, "email_body", submission_id)]
        attachments = submission.get("attachments", [])
        for attachment in attachments:
            filename = attachment.get("filename", "unnamed attachment")
            text = self._required_text(attachment, "text", submission_id)
            sections.append(f"ATTACHMENT: {filename}\n{text}")
        return CandidateText(
            submission_id=submission_id,
            candidate_text="\n\n".join(sections),
            attachment_count=len(attachments),
        )

    def _load_fixture(self) -> list[dict]:
        with self.fixture_path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Candidate-submission fixture must contain a JSON array")
        seen_ids: set[str] = set()
        for submission in data:
            for field in ("submission_id", "received_at", "subject", "email_body"):
                self._required_text(submission, field, "fixture")
            self._parse_timestamp(submission["received_at"])
            submission_id = submission["submission_id"]
            if submission_id in seen_ids:
                raise ValueError(f"Duplicate submission_id: {submission_id}")
            seen_ids.add(submission_id)
        return data

    @staticmethod
    def _required_text(record: dict, field: str, context: str) -> str:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing non-empty {field!r} in {context}")
        return value.strip()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid ISO-8601 timestamp: {value!r}") from error


def as_json_ready(value: SubmissionReference | CandidateText) -> dict:
    return asdict(value)
