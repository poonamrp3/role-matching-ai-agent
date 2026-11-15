#!/usr/bin/env python3
"""Run the first query-pipeline tool with fictional candidate submissions."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from role_matching.tools.candidate_submissions import LocalCandidateSubmissionTool, as_json_ready  # noqa: E402


def main() -> None:
    fixture = PROJECT_ROOT / "data" / "demo" / "synthetic_candidate_submissions.json"
    tool = LocalCandidateSubmissionTool(fixture)
    submissions = tool.fetch_latest_submissions(limit=5)
    print("Latest fictional submission references:")
    for submission in submissions:
        print(as_json_ready(submission))
    print("\nExtracted candidate-text summaries:")
    for submission in submissions:
        candidate_text = tool.extract_candidate_text(submission.submission_id)
        print({
            "submission_id": candidate_text.submission_id,
            "attachment_count": candidate_text.attachment_count,
            "character_count": len(candidate_text.candidate_text),
            "preview": candidate_text.candidate_text[:140] + "...",
        })


if __name__ == "__main__":
    main()
