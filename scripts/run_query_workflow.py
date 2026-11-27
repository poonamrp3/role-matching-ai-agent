#!/usr/bin/env python3
"""Run the top-level role-matching LangGraph from a terminal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from role_matching.workflows.graph import build_role_matching_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a recruiter command and retrieve bounded Gmail submission metadata."
    )
    parser.add_argument("prompt", nargs="*", help="Recruiter command to interpret.")
    parser.add_argument("--mode", choices=("baseline", "structured"), default="structured",
                        help="Baseline embeds full text; structured extracts a profile first.")
    parser.add_argument("--output", type=Path, help="Save JSON to a new file without overwriting an existing file.")
    arguments = parser.parse_args()
    if arguments.output and arguments.output.exists():
        parser.error("Output already exists; choose a new file")
    prompt = " ".join(arguments.prompt).strip() or input("Recruiter request: ").strip()

    result = build_role_matching_graph().invoke(
        {
            "raw_prompt": prompt,
            "retrieval_mode": arguments.mode,
            "status": "pending",
            "validation_errors": [],
            "workflow_events": [],
        }
    )
    safe_result = {
        "retrieval_mode": arguments.mode,
        "status": result.get("status"),
        "query_intent": result.get("query_intent"),
        "match_request": result.get("match_request"),
        "gmail_connection_ok": result.get("gmail_connection_ok"),
        "gmail_access_token_refreshed": result.get("gmail_access_token_refreshed"),
        "submission_references": result.get("submission_references", []),
        "candidate_extraction_summary": result.get("candidate_extraction_summary", []),
        "candidate_extraction_errors": result.get("candidate_extraction_errors", []),
        "candidate_profile_errors": result.get("candidate_profile_errors", []),
        "candidate_embedding_summary": result.get("candidate_embedding_summary", []),
        "candidate_embedding_errors": result.get("candidate_embedding_errors", []),
        "baseline_role_matches": result.get("baseline_role_matches", []),
        "structured_role_matches": result.get("structured_role_matches", []),
        "formatted_results": result.get("formatted_results", []),
        "role_retrieval_errors": result.get("role_retrieval_errors", []),
        "validation_errors": result.get("validation_errors", []),
        "workflow_events": result.get("workflow_events", []),
    }
    if arguments.output:
        with arguments.output.open("x", encoding="utf-8") as file:
            json.dump(safe_result, file, indent=2)
            file.write("\n")
        print(f"Saved {arguments.mode} workflow result to {arguments.output}")
    else:
        print(json.dumps(safe_result, indent=2))


if __name__ == "__main__":
    main()
