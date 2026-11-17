#!/usr/bin/env python3
"""Run the top-level role-matching LangGraph from a terminal."""

from __future__ import annotations

import argparse
import json

from role_matching.workflows.graph import build_role_matching_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a recruiter command and retrieve bounded Gmail submission metadata."
    )
    parser.add_argument("prompt", nargs="*", help="Recruiter command to interpret.")
    arguments = parser.parse_args()
    prompt = " ".join(arguments.prompt).strip() or input("Recruiter request: ").strip()

    result = build_role_matching_graph().invoke(
        {
            "raw_prompt": prompt,
            "status": "pending",
            "validation_errors": [],
            "workflow_events": [],
        }
    )
    safe_result = {
        "status": result.get("status"),
        "query_intent": result.get("query_intent"),
        "match_request": result.get("match_request"),
        "gmail_connection_ok": result.get("gmail_connection_ok"),
        "gmail_access_token_refreshed": result.get("gmail_access_token_refreshed"),
        "submission_references": result.get("submission_references", []),
        "candidate_extraction_summary": result.get("candidate_extraction_summary", []),
        "candidate_extraction_errors": result.get("candidate_extraction_errors", []),
        "candidate_embedding_summary": result.get("candidate_embedding_summary", []),
        "candidate_embedding_errors": result.get("candidate_embedding_errors", []),
        "formatted_results": result.get("formatted_results", []),
        "role_retrieval_errors": result.get("role_retrieval_errors", []),
        "validation_errors": result.get("validation_errors", []),
        "workflow_events": result.get("workflow_events", []),
    }
    print(json.dumps(safe_result, indent=2))


if __name__ == "__main__":
    main()
