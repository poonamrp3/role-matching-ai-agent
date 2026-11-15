#!/usr/bin/env python3
"""List and extract at most five messages from the configured candidate label."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from role_matching.tools.candidate_submissions import as_json_ready  # noqa: E402
from role_matching.tools.gmail_candidate_submissions import GmailCandidateSubmissionTool  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="Dedicated Gmail label containing demo applications")
    parser.add_argument("--connection-id", default="demo-applications-mailbox")
    args = parser.parse_args()
    tool = GmailCandidateSubmissionTool(label=args.label, connection_id=args.connection_id)
    submissions = tool.fetch_latest_submissions(limit=5)
    print("Submission references:")
    for submission in submissions:
        print(as_json_ready(submission))
    for submission in submissions:
        text = tool.extract_candidate_text(submission.submission_id)
        print({"submission_id": text.submission_id, "attachment_count": text.attachment_count,
               "character_count": len(text.candidate_text)})


if __name__ == "__main__":
    main()
